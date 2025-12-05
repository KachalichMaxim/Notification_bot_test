"""Telegram bot integration for sending task notifications"""
import requests
from typing import Dict
from config import Config


def send_task_notification(
    chat_id: str, task_data: Dict, event_type: str = "new"
) -> bool:
    """
    Send task notification to Telegram chat
    
    Args:
        chat_id: Telegram chat ID
        task_data: Task data dictionary with fields:
            - id: Task ID
            - title: Task title
            - priority: Priority level (1=low, 2=high, 3=critical)
            - deadline: Deadline date/time (optional)
            - responsible_id: Responsible user ID
            - responsible_name: Responsible user name (optional)
            - creator_id: Creator user ID
            - creator_name: Creator name (optional)
            - link: Direct link to task
            - status: Task status
        event_type: "new" or "updated"
    
    Returns:
        True if sent successfully, False otherwise
    """
    if not Config.TELEGRAM_BOT_TOKEN:
        print("❌ TELEGRAM_BOT_TOKEN not configured")
        return False
    
    # Format priority
    priority_map = {
        "1": "Низкий",
        "2": "Высокий",
        "3": "Критический"
    }
    priority = task_data.get("priority", "")
    priority_text = priority_map.get(
        str(priority), f"Приоритет {priority}"
    )

    # Format deadline
    deadline = task_data.get("deadline", "")
    deadline_text = (
        f"Дедлайн: {deadline}" if deadline else "Дедлайн не установлен"
    )

    # Format responsible user
    responsible_name = task_data.get(
        "responsible_name",
        task_data.get("responsible_id", "Не назначен")
    )

    # Format creator
    creator_name = task_data.get(
        "creator_name", task_data.get("creator_id", "Неизвестен")
    )

    # Event type text
    event_text = (
        "🆕 Новая задача" if event_type == "new" else "🔄 Задача обновлена"
    )
    
    # Build message
    message = f"""{event_text}

📋 <b>{task_data.get('title', 'Без названия')}</b>

👤 Ответственный: {responsible_name}
👨‍💼 Создатель: {creator_name}
⚡ {priority_text}
📅 {deadline_text}
📊 Статус: {task_data.get('status', 'Не указан')}

🔗 <a href="{task_data.get('link', '#')}">Открыть задачу</a>
"""
    
    # Send message via Telegram Bot API
    url = Config.TELEGRAM_API_URL
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()

        if result.get("ok"):
            task_id = task_data.get('id')
            print(
                f"✅ Telegram notification sent to chat {chat_id} "
                f"for task {task_id}"
            )
            return True
        else:
            error_desc = result.get('description', 'Unknown error')
            print(f"❌ Telegram API error: {error_desc}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Error sending Telegram notification: {e}")
        return False

