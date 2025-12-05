# Руководство по деплою

## Быстрый старт

### 1. Клонирование/копирование проекта

```bash
# Если проект уже на сервере, перейдите в директорию
cd bitrix24_webhook

# Сделайте скрипт исполняемым
chmod +x deploy.sh
```

### 2. Автоматическая установка

```bash
# Запустите полную установку
./deploy.sh install
```

Скрипт выполнит:
- ✅ Проверку Python 3.8+
- ✅ Создание виртуального окружения
- ✅ Установку зависимостей
- ✅ Настройку .env файла (интерактивно)
- ✅ Создание user_mappings.json

### 3. Настройка маппингов

```bash
# Активируйте виртуальное окружение
source venv/bin/activate

# Добавьте руководителей
python manage_mappings.py add-leader <bitrix24_user_id>

# Добавьте Telegram маппинги
python manage_mappings.py add-telegram <bitrix24_user_id> <telegram_chat_id>

# Проверьте настройки
python manage_mappings.py list
```

### 4. Запуск сервиса

#### Вариант A: Ручной запуск (для тестирования)

```bash
./deploy.sh run
```

Сервис запустится в текущей сессии. Для остановки нажмите `Ctrl+C`.

#### Вариант B: Systemd service (для production)

```bash
# Установите systemd service
sudo ./deploy.sh install-service

# Запустите сервис
sudo systemctl start bitrix24-webhook

# Включите автозапуск
sudo systemctl enable bitrix24-webhook

# Проверьте статус
sudo systemctl status bitrix24-webhook

# Просмотр логов
sudo journalctl -u bitrix24-webhook -f
```

## Команды скрипта

| Команда | Описание |
|---------|----------|
| `./deploy.sh install` | Полная установка (проверка, venv, зависимости, .env, mappings) |
| `./deploy.sh setup-env` | Настроить только .env файл |
| `./deploy.sh setup-mappings` | Настроить только user_mappings.json |
| `./deploy.sh run` | Запустить сервис в текущей сессии |
| `./deploy.sh install-service` | Установить systemd service (требует sudo) |
| `./deploy.sh status` | Показать статус установки |
| `./deploy.sh help` | Показать справку |

## Примеры использования

### Первичная установка на новом сервере

```bash
# 1. Копируем проект на сервер
scp -r bitrix24_webhook user@server:/opt/

# 2. Подключаемся к серверу
ssh user@server

# 3. Переходим в директорию
cd /opt/bitrix24_webhook

# 4. Делаем скрипт исполняемым
chmod +x deploy.sh

# 5. Запускаем установку
./deploy.sh install

# 6. Настраиваем маппинги
source venv/bin/activate
python manage_mappings.py add-leader 123
python manage_mappings.py add-telegram 456 987654321

# 7. Устанавливаем systemd service
sudo ./deploy.sh install-service

# 8. Запускаем сервис
sudo systemctl start bitrix24-webhook
sudo systemctl enable bitrix24-webhook
```

### Обновление сервиса

```bash
# 1. Останавливаем сервис
sudo systemctl stop bitrix24-webhook

# 2. Обновляем код (git pull или копирование новых файлов)
git pull  # или scp новых файлов

# 3. Обновляем зависимости (если изменились)
source venv/bin/activate
pip install -r requirements.txt

# 4. Запускаем сервис
sudo systemctl start bitrix24-webhook
```

### Изменение конфигурации

```bash
# 1. Редактируем .env
nano .env

# 2. Перезапускаем сервис
sudo systemctl restart bitrix24-webhook

# 3. Проверяем логи
sudo journalctl -u bitrix24-webhook -f
```

## Требования к серверу

### Минимальные требования

- **OS**: Linux (Ubuntu 18.04+, Debian 10+, CentOS 7+) или macOS
- **Python**: 3.8 или выше
- **RAM**: 128 MB (минимум)
- **Диск**: 100 MB свободного места
- **Сеть**: Доступ к интернету (для Telegram API и Bitrix24)

### Рекомендуемые требования

- **OS**: Ubuntu 20.04+ или Debian 11+
- **Python**: 3.9+
- **RAM**: 256 MB+
- **Диск**: 500 MB+
- **Firewall**: Настроен для входящих соединений на порт webhook

## Настройка firewall

### Ubuntu/Debian (ufw)

```bash
# Разрешить порт 8080
sudo ufw allow 8080/tcp

# Проверить статус
sudo ufw status
```

### CentOS/RHEL (firewalld)

```bash
# Разрешить порт 8080
sudo firewall-cmd --permanent --add-port=8080/tcp
sudo firewall-cmd --reload

# Проверить статус
sudo firewall-cmd --list-ports
```

### iptables

```bash
# Разрешить порт 8080
sudo iptables -A INPUT -p tcp --dport 8080 -j ACCEPT

# Сохранить правила (Ubuntu/Debian)
sudo iptables-save > /etc/iptables/rules.v4
```

## Проверка работы

### 1. Health check

```bash
curl http://localhost:8080/health
```

Ожидаемый ответ:
```json
{"status":"ok","service":"bitrix24_webhook"}
```

### 2. Проверка логов

```bash
# Если запущен через systemd
sudo journalctl -u bitrix24-webhook -f

# Если запущен вручную
# Логи выводятся в консоль
```

### 3. Тестовый webhook

```bash
curl -X POST http://localhost:8080/webhook_tasks \
  -H "Content-Type: application/json" \
  -d '{
    "event": "OnTaskAdd",
    "data": {
      "ID": "123",
      "TITLE": "Test Task",
      "PRIORITY": "2",
      "STATUS": "2",
      "IMPORTANT": "1",
      "CREATED_BY": "789",
      "RESPONSIBLE_ID": "456"
    }
  }'
```

## Устранение проблем

### Проблема: Python не найден

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3 python3-pip python3-venv

# CentOS/RHEL
sudo yum install python3 python3-pip

# macOS
brew install python3
```

### Проблема: Порт занят

```bash
# Проверить, что использует порт
sudo lsof -i :8080
# или
sudo netstat -tulpn | grep 8080

# Изменить порт в .env
nano .env
# Измените PORT=8080 на другой порт
```

### Проблема: Сервис не запускается

```bash
# Проверить статус
sudo systemctl status bitrix24-webhook

# Посмотреть логи
sudo journalctl -u bitrix24-webhook -n 50

# Проверить права доступа
ls -la /opt/bitrix24_webhook
sudo chown -R user:user /opt/bitrix24_webhook
```

### Проблема: Виртуальное окружение не активируется

```bash
# Пересоздать venv
rm -rf venv
./deploy.sh install
```

## Безопасность

### Рекомендации

1. **Не храните .env в git**: Убедитесь, что `.env` в `.gitignore`
2. **Ограничьте доступ**: Используйте отдельного пользователя для сервиса
3. **Firewall**: Откройте только необходимые порты
4. **HTTPS**: Используйте reverse proxy (nginx) с SSL для production
5. **Логи**: Регулярно проверяйте логи на подозрительную активность

### Настройка nginx reverse proxy

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Мониторинг

### Проверка статуса

```bash
# Статус systemd service
sudo systemctl status bitrix24-webhook

# Использование ресурсов
ps aux | grep app.py
top -p $(pgrep -f app.py)
```

### Автоматическая проверка

Создайте cron job для проверки здоровья сервиса:

```bash
# Добавить в crontab
crontab -e

# Проверка каждые 5 минут
*/5 * * * * curl -f http://localhost:8080/health || systemctl restart bitrix24-webhook
```

## Резервное копирование

### Важные файлы для бэкапа

```bash
# .env файл с конфигурацией
cp .env .env.backup

# user_mappings.json с маппингами
cp user_mappings.json user_mappings.json.backup
```

### Автоматический бэкап

```bash
# Создать скрипт бэкапа
cat > /opt/backup_webhook.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/opt/backups/bitrix24_webhook"
mkdir -p $BACKUP_DIR
cp /opt/bitrix24_webhook/.env $BACKUP_DIR/.env.$(date +%Y%m%d)
cp /opt/bitrix24_webhook/user_mappings.json $BACKUP_DIR/mappings.$(date +%Y%m%d).json
# Хранить только последние 7 дней
find $BACKUP_DIR -name "*.env.*" -mtime +7 -delete
find $BACKUP_DIR -name "*.json" -mtime +7 -delete
EOF

chmod +x /opt/backup_webhook.sh

# Добавить в crontab (ежедневно в 2:00)
# 0 2 * * * /opt/backup_webhook.sh
```

