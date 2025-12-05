#!/bin/bash

# Bitrix24 Telegram Webhook - Deployment Script
# Скрипт для быстрого развертывания на любом сервере

set -e  # Остановка при ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Переменные
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/venv"
PYTHON_CMD="python3"
REQUIREMENTS_FILE="${SCRIPT_DIR}/requirements.txt"
ENV_FILE="${SCRIPT_DIR}/.env"
ENV_EXAMPLE="${SCRIPT_DIR}/env.example"
MAPPINGS_FILE="${SCRIPT_DIR}/user_mappings.json"
SERVICE_NAME="bitrix24-webhook"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# Проверка интерактивности терминала
if [ -t 0 ]; then
    INTERACTIVE=1
else
    INTERACTIVE=0
fi

# Функции для вывода
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Проверка прав root для systemd
check_root() {
    if [ "$EUID" -ne 0 ] && [ "$1" == "install-service" ]; then
        print_error "Для установки systemd сервиса нужны права root"
        print_info "Запустите: sudo $0 install-service"
        exit 1
    fi
}

# Проверка наличия Python
check_python() {
    print_info "Проверка наличия Python 3..."
    
    if ! command -v $PYTHON_CMD &> /dev/null; then
        print_error "Python 3 не найден!"
        print_info "Установите Python 3:"
        print_info "  Ubuntu/Debian: sudo apt-get install python3 python3-pip python3-venv"
        print_info "  CentOS/RHEL: sudo yum install python3 python3-pip"
        print_info "  macOS: brew install python3"
        exit 1
    fi
    
    PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
    print_success "Python найден: $PYTHON_VERSION"
    
    # Проверка версии (минимум 3.8)
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
        print_error "Требуется Python 3.8 или выше. Найдена версия: $PYTHON_VERSION"
        exit 1
    fi
}

# Создание виртуального окружения
create_venv() {
    print_info "Создание виртуального окружения..."
    
    if [ -d "$VENV_DIR" ]; then
        print_warning "Виртуальное окружение уже существует"
        if [ $INTERACTIVE -eq 1 ]; then
            read -p "Пересоздать? (y/N): " -n 1 -r
            echo
            if [[ $REPLY =~ ^[Yy]$ ]]; then
                rm -rf "$VENV_DIR"
                $PYTHON_CMD -m venv "$VENV_DIR"
                print_success "Виртуальное окружение пересоздано"
            fi
        else
            print_info "Пропуск пересоздания (неинтерактивный режим)"
        fi
    else
        $PYTHON_CMD -m venv "$VENV_DIR"
        print_success "Виртуальное окружение создано"
    fi
}

# Установка зависимостей
install_dependencies() {
    print_info "Установка зависимостей..."
    
    if [ ! -f "$REQUIREMENTS_FILE" ]; then
        print_error "Файл requirements.txt не найден!"
        exit 1
    fi
    
    source "${VENV_DIR}/bin/activate"
    pip install --upgrade pip > /dev/null 2>&1
    pip install -r "$REQUIREMENTS_FILE"
    
    print_success "Зависимости установлены"
}

# Настройка .env файла
setup_env() {
    print_info "Настройка файла .env..."
    
    if [ -f "$ENV_FILE" ]; then
        print_warning "Файл .env уже существует"
        if [ $INTERACTIVE -eq 1 ]; then
            read -p "Перезаписать? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                print_info "Пропуск настройки .env"
                return
            fi
        else
            print_info "Пропуск перезаписи .env (неинтерактивный режим, файл уже существует)"
            return
        fi
    fi
    
    if [ ! -f "$ENV_EXAMPLE" ]; then
        print_error "Файл env.example не найден!"
        exit 1
    fi
    
    cp "$ENV_EXAMPLE" "$ENV_FILE"
    print_success "Файл .env создан из шаблона"
    
    # Интерактивная настройка (только если терминал интерактивный)
    if [ $INTERACTIVE -eq 1 ]; then
        print_info "Настройка параметров .env..."
        
        read -p "Введите Telegram Bot Token (от @BotFather): " TELEGRAM_TOKEN
        if [ -n "$TELEGRAM_TOKEN" ]; then
            if [[ "$OSTYPE" == "darwin"* ]]; then
                # macOS
                sed -i '' "s|TELEGRAM_BOT_TOKEN=.*|TELEGRAM_BOT_TOKEN=${TELEGRAM_TOKEN}|" "$ENV_FILE"
            else
                # Linux
                sed -i "s|TELEGRAM_BOT_TOKEN=.*|TELEGRAM_BOT_TOKEN=${TELEGRAM_TOKEN}|" "$ENV_FILE"
            fi
        fi
        
        read -p "Введите порт для сервера [8080]: " PORT
        PORT=${PORT:-8080}
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|PORT=.*|PORT=${PORT}|" "$ENV_FILE"
        else
            sed -i "s|PORT=.*|PORT=${PORT}|" "$ENV_FILE"
        fi
        
        read -p "Включить режим отладки? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            DEBUG_VAL="true"
        else
            DEBUG_VAL="false"
        fi
        if [[ "$OSTYPE" == "darwin"* ]]; then
            sed -i '' "s|DEBUG=.*|DEBUG=${DEBUG_VAL}|" "$ENV_FILE"
        else
            sed -i "s|DEBUG=.*|DEBUG=${DEBUG_VAL}|" "$ENV_FILE"
        fi
        
        print_success "Файл .env настроен"
    else
        print_info "Пропуск интерактивной настройки .env (неинтерактивный режим)"
        print_warning "Проверьте параметры в файле .env при необходимости"
    fi
}

# Настройка user_mappings.json
setup_mappings() {
    print_info "Настройка файла user_mappings.json..."
    
    if [ -f "$MAPPINGS_FILE" ]; then
        print_warning "Файл user_mappings.json уже существует"
        if [ $INTERACTIVE -eq 1 ]; then
            read -p "Перезаписать? (y/N): " -n 1 -r
            echo
            if [[ ! $REPLY =~ ^[Yy]$ ]]; then
                print_info "Пропуск настройки user_mappings.json"
                return
            fi
        else
            print_info "Пропуск перезаписи user_mappings.json (неинтерактивный режим, файл уже существует)"
            return
        fi
    fi
    
    cat > "$MAPPINGS_FILE" << EOF
{
  "leaders": [],
  "telegram_chats": {}
}
EOF
    
    print_success "Файл user_mappings.json создан"
    print_info "Используйте manage_mappings.py для настройки маппингов:"
    print_info "  python manage_mappings.py add-leader <user_id>"
    print_info "  python manage_mappings.py add-telegram <user_id> <chat_id>"
}

# Проверка порта
check_port() {
    local PORT=$1
    print_info "Проверка доступности порта $PORT..."
    
    if command -v netstat &> /dev/null; then
        if netstat -tuln | grep -q ":$PORT "; then
            print_warning "Порт $PORT уже занят!"
            return 1
        fi
    elif command -v ss &> /dev/null; then
        if ss -tuln | grep -q ":$PORT "; then
            print_warning "Порт $PORT уже занят!"
            return 1
        fi
    elif command -v lsof &> /dev/null; then
        if lsof -i :$PORT &> /dev/null; then
            print_warning "Порт $PORT уже занят!"
            return 1
        fi
    fi
    
    print_success "Порт $PORT свободен"
    return 0
}

# Запуск сервиса
run_service() {
    print_info "Запуск сервиса..."
    
    source "${VENV_DIR}/bin/activate"
    
    # Получаем порты из .env
    if [ -f "$ENV_FILE" ]; then
        EXTERNAL_PORT=$(grep "^PORT=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'")
        EXTERNAL_PORT=${EXTERNAL_PORT:-8081}
    else
        EXTERNAL_PORT=8081
    fi
    
    # Внутренний порт для gunicorn
    INTERNAL_PORT=$((EXTERNAL_PORT + 1))
    
    check_port "$INTERNAL_PORT"
    
    print_info "Gunicorn запускается на внутреннем порту $INTERNAL_PORT"
    print_info "Внешний порт (nginx): $EXTERNAL_PORT"
    print_info "Для остановки нажмите Ctrl+C"
    print_info "Логи будут выводиться в консоль"
    echo
    
    cd "$SCRIPT_DIR"
    gunicorn --workers 3 --bind 127.0.0.1:${INTERNAL_PORT} --access-logfile access.log --error-logfile error.log --log-level info app:app
}

# Настройка nginx
setup_nginx() {
    print_info "Настройка nginx reverse proxy..."
    
    check_root "install-service"
    
    # Получаем порты из .env
    if [ -f "$ENV_FILE" ]; then
        EXTERNAL_PORT=$(grep "^PORT=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'")
        EXTERNAL_PORT=${EXTERNAL_PORT:-8081}
    else
        EXTERNAL_PORT=8081
    fi
    
    # Внутренний порт для gunicorn (всегда на 1 больше внешнего)
    INTERNAL_PORT=$((EXTERNAL_PORT + 1))
    
    NGINX_CONFIG="/etc/nginx/sites-available/${SERVICE_NAME}"
    NGINX_ENABLED="/etc/nginx/sites-enabled/${SERVICE_NAME}"
    
    # Проверка наличия nginx
    if ! command -v nginx &> /dev/null; then
        print_warning "Nginx не установлен. Пропуск настройки nginx."
        print_info "Установите nginx: sudo apt-get install nginx"
        return 1
    fi
    
    # Создание конфигурации nginx
    cat > "$NGINX_CONFIG" << EOF
server {
    listen ${EXTERNAL_PORT};
    server_name bookntrack.online www.bookntrack.online;

    location / {
        proxy_pass http://127.0.0.1:${INTERNAL_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
}
EOF
    
    # Создание симлинка
    ln -sf "$NGINX_CONFIG" "$NGINX_ENABLED"
    
    # Проверка конфигурации
    if nginx -t > /dev/null 2>&1; then
        systemctl reload nginx
        print_success "Nginx настроен: ${EXTERNAL_PORT} -> 127.0.0.1:${INTERNAL_PORT}"
    else
        print_error "Ошибка в конфигурации nginx!"
        nginx -t
        return 1
    fi
}

# Создание systemd service файла
create_systemd_service() {
    print_info "Создание systemd service файла..."
    
    check_root "install-service"
    
    # Получаем порты из .env
    if [ -f "$ENV_FILE" ]; then
        EXTERNAL_PORT=$(grep "^PORT=" "$ENV_FILE" | cut -d'=' -f2 | tr -d '"' | tr -d "'")
        EXTERNAL_PORT=${EXTERNAL_PORT:-8081}
    else
        EXTERNAL_PORT=8081
    fi
    
    # Внутренний порт для gunicorn
    INTERNAL_PORT=$((EXTERNAL_PORT + 1))
    
    # Получаем пользователя
    SERVICE_USER=${SUDO_USER:-$USER}
    if [ "$SERVICE_USER" == "root" ]; then
        SERVICE_USER="www-data"
    fi
    
    cat > "$SERVICE_FILE" << EOF
[Unit]
Description=Bitrix24 Telegram Webhook Service
After=network.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${SCRIPT_DIR}
Environment="PATH=${VENV_DIR}/bin"
ExecStart=${VENV_DIR}/bin/gunicorn --workers 3 --bind 127.0.0.1:${INTERNAL_PORT} --access-logfile ${SCRIPT_DIR}/access.log --error-logfile ${SCRIPT_DIR}/error.log --log-level info app:app
Restart=always
RestartSec=10
StandardOutput=append:${SCRIPT_DIR}/gunicorn.log
StandardError=append:${SCRIPT_DIR}/gunicorn.log

[Install]
WantedBy=multi-user.target
EOF
    
    systemctl daemon-reload
    print_success "Systemd service файл создан: $SERVICE_FILE"
    print_info "Gunicorn будет запущен на внутреннем порту: ${INTERNAL_PORT}"
    print_info "Nginx будет проксировать внешний порт: ${EXTERNAL_PORT}"
    print_info "Для управления сервисом используйте:"
    print_info "  sudo systemctl start ${SERVICE_NAME}"
    print_info "  sudo systemctl stop ${SERVICE_NAME}"
    print_info "  sudo systemctl enable ${SERVICE_NAME}  # автозапуск"
    print_info "  sudo systemctl status ${SERVICE_NAME}"
    print_info "  sudo journalctl -u ${SERVICE_NAME} -f  # просмотр логов"
}

# Показать статус
show_status() {
    print_info "Статус сервиса:"
    echo
    
    # Проверка виртуального окружения
    if [ -d "$VENV_DIR" ]; then
        print_success "✓ Виртуальное окружение установлено"
    else
        print_error "✗ Виртуальное окружение не найдено"
    fi
    
    # Проверка .env
    if [ -f "$ENV_FILE" ]; then
        print_success "✓ Файл .env существует"
        if grep -q "TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here" "$ENV_FILE" 2>/dev/null; then
            print_warning "⚠ Telegram Bot Token не настроен"
        else
            print_success "✓ Telegram Bot Token настроен"
        fi
    else
        print_error "✗ Файл .env не найден"
    fi
    
    # Проверка маппингов
    if [ -f "$MAPPINGS_FILE" ]; then
        print_success "✓ Файл user_mappings.json существует"
        LEADERS_COUNT=$(python3 -c "import json; f=open('$MAPPINGS_FILE'); d=json.load(f); print(len(d.get('leaders', [])))" 2>/dev/null || echo "0")
        CHATS_COUNT=$(python3 -c "import json; f=open('$MAPPINGS_FILE'); d=json.load(f); print(len(d.get('telegram_chats', {})))" 2>/dev/null || echo "0")
        print_info "  Руководителей: $LEADERS_COUNT"
        print_info "  Telegram маппингов: $CHATS_COUNT"
    else
        print_error "✗ Файл user_mappings.json не найден"
    fi
    
    # Проверка systemd service
    if [ -f "$SERVICE_FILE" ]; then
        print_success "✓ Systemd service установлен"
        if systemctl is-active --quiet "$SERVICE_NAME" 2>/dev/null; then
            print_success "✓ Сервис запущен"
        else
            print_warning "⚠ Сервис не запущен"
        fi
    else
        print_info "ℹ Systemd service не установлен"
    fi
}

# Показать справку
show_help() {
    cat << EOF
Bitrix24 Telegram Webhook - Deployment Script

Использование: $0 [команда]

Команды:
  install          - Полная установка (проверка, venv, зависимости, .env, mappings)
  setup-env         - Настроить только .env файл
  setup-mappings    - Настроить только user_mappings.json
  run               - Запустить сервис в текущей сессии
  install-service   - Установить systemd service (требует sudo)
  status            - Показать статус установки
  help              - Показать эту справку

Примеры:
  $0 install              # Полная установка
  $0 setup-env             # Настроить .env
  $0 run                   # Запустить сервис
  sudo $0 install-service # Установить systemd service

EOF
}

# Главная функция
main() {
    case "${1:-install}" in
        install)
            print_info "=== Установка Bitrix24 Telegram Webhook ==="
            check_python
            create_venv
            install_dependencies
            setup_env
            setup_mappings
            print_success "=== Установка завершена! ==="
            print_info "Следующие шаги:"
            print_info "1. Настройте маппинги: python manage_mappings.py"
            print_info "2. Запустите сервис: $0 run"
            print_info "3. Или установите systemd service: sudo $0 install-service"
            ;;
        setup-env)
            setup_env
            ;;
        setup-mappings)
            setup_mappings
            ;;
        run)
            if [ ! -d "$VENV_DIR" ]; then
                print_error "Виртуальное окружение не найдено!"
                print_info "Запустите сначала: $0 install"
                exit 1
            fi
            run_service
            ;;
        install-service)
            if [ ! -d "$VENV_DIR" ]; then
                print_error "Виртуальное окружение не найдено!"
                print_info "Запустите сначала: $0 install"
                exit 1
            fi
            setup_nginx
            create_systemd_service
            print_success "=== Сервис установлен! ==="
            print_info "Запустите сервис: sudo systemctl start ${SERVICE_NAME}"
            print_info "Включите автозапуск: sudo systemctl enable ${SERVICE_NAME}"
            ;;
        status)
            show_status
            ;;
        help|--help|-h)
            show_help
            ;;
        *)
            print_error "Неизвестная команда: $1"
            show_help
            exit 1
            ;;
    esac
}

# Запуск
main "$@"

