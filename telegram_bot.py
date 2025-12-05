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

    # Format message according to requirements
    # Срочная задача (red ! sign emoji)
    urgent_emoji = "🔴"
    
    # Get creator name (first and last name)
    creator_name = task_data.get("creator_name", task_data.get("creator_id", "Неизвестен"))
    
    # Escape HTML special characters in text
    def escape_html(text):
        if not text:
            return ""
        return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    
    title = escape_html(task_data.get('title', 'Без названия'))
    creator = escape_html(creator_name)
    link = task_data.get('link', '#')
    
    # Different message format for new vs updated tasks
    if event_type == "new":
        # Build message for new task
        message = f"""{urgent_emoji} <b>Срочная задача</b>

От: {creator}

Наименование задачи: <b>{title}</b>

Детальная информация по ссылке: <a href=\"{link}\">Открыть задачу</a>
"""
    else:
        # Build message for updated task
        message = f"""{urgent_emoji} По срочной задаче поступило обновление

От: {creator}

Наименование задачи: <b>{title}</b>

Детальная информация по ссылке: <a href=\"{link}\">Открыть задачу</a>
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
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                error_desc = error_data.get('description', 'Unknown error')
                print(f"   Telegram API error: {error_desc}")
                print(f"   Full response: {error_data}")
            except:
                print(f"   Response text: {e.response.text[:200]}")
        return False

