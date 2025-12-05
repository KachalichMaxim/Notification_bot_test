#!/usr/bin/env python3
"""
Скрипт для подписки на события Bitrix24 через REST API
Использование: python subscribe_bitrix24.py
"""
import requests
import json
import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env
load_dotenv()

# Конфигурация из .env
WEBHOOK_URL = os.getenv(
    "WEBHOOK_URL", "http://bookntrack.online:8081/webhook_tasks"
)
AUTH_TOKEN = os.getenv("BITRIX24_AUTH_TOKEN", "")
BITRIX24_DOMAIN = os.getenv("BITRIX24_DOMAIN", "intranet.vedagent.ru")

# Формируем полный endpoint для вызова event.bind
REST_ENDPOINT = f'https://{BITRIX24_DOMAIN}/rest/event.bind.json'


def send_request(event_name, handler_url):
    """Отправить запрос на подписку события"""
    data = {
        'auth': AUTH_TOKEN,
        'event': event_name,
        'handler': handler_url
    }
    
    try:
        response = requests.get(REST_ENDPOINT, params=data, timeout=10)
        response.raise_for_status()
        result = response.json()
        return result
    except requests.exceptions.RequestException as e:
        print(f"❌ Ошибка при отправке запроса: {e}")
        return None


def main():
    print("=== Подписка на события Bitrix24 ===\n")
    
    # Проверка конфигурации
    if not AUTH_TOKEN:
        print("❌ ОШИБКА: BITRIX24_AUTH_TOKEN не найден в .env файле!")
        print("   Убедитесь, что файл .env существует и содержит BITRIX24_AUTH_TOKEN")
        return
    
    print(f"Webhook URL: {WEBHOOK_URL}")
    print(f"Bitrix24 Domain: {BITRIX24_DOMAIN}")
    print(f"Auth Token: {AUTH_TOKEN[:10]}...{AUTH_TOKEN[-5:]}\n")
    
    # Подписка на OnTaskAdd
    print("1. Подписка на OnTaskAdd...")
    result_add = send_request('OnTaskAdd', WEBHOOK_URL)
    if result_add:
        if result_add.get('result'):
            print("✅ Успешно подписан на OnTaskAdd")
            if 'error' in result_add:
                print(f"   ⚠️ Предупреждение: {result_add.get('error_description', '')}")
        elif result_add.get('error'):
            print(f"❌ Ошибка подписки на OnTaskAdd: {result_add.get('error_description', result_add.get('error'))}")
        else:
            print("❌ Неожиданный ответ от Bitrix24")
        print(f"   Полный ответ: {json.dumps(result_add, indent=2, ensure_ascii=False)}")
    else:
        print("❌ Не удалось получить ответ от Bitrix24")
    
    print()
    
    # Подписка на OnTaskUpdate
    print("2. Подписка на OnTaskUpdate...")
    result_update = send_request('OnTaskUpdate', WEBHOOK_URL)
    if result_update:
        if result_update.get('result'):
            print("✅ Успешно подписан на OnTaskUpdate")
            if 'error' in result_update:
                print(f"   ⚠️ Предупреждение: {result_update.get('error_description', '')}")
        elif result_update.get('error'):
            print(f"❌ Ошибка подписки на OnTaskUpdate: {result_update.get('error_description', result_update.get('error'))}")
        else:
            print("❌ Неожиданный ответ от Bitrix24")
        print(f"   Полный ответ: {json.dumps(result_update, indent=2, ensure_ascii=False)}")
    else:
        print("❌ Не удалось получить ответ от Bitrix24")
    
    print("\n=== Готово! ===")
    print(f"Теперь Bitrix24 будет отправлять события на: {WEBHOOK_URL}")
    print("\nСобытия:")
    print("- OnTaskAdd (создание задачи)")
    print("- OnTaskUpdate (обновление задачи)")
    print("\n💡 Для проверки создайте задачу в Bitrix24 и проверьте логи:")
    print("   tail -f ~/Notification_bot_test/access.log")


if __name__ == "__main__":
    main()

