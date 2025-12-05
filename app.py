"""Main Flask application for Bitrix24 webhook"""
from flask import Flask, request, jsonify
import json
import requests
from datetime import datetime
from typing import Dict, Optional
from config import Config
from telegram_bot import send_task_notification
from user_mapping import is_leader, get_telegram_chat_id

app = Flask(__name__)

# Validate configuration on startup
try:
    Config.validate()
except ValueError as e:
    print(f"Configuration error: {e}")


def is_task_important(task_data: Dict) -> bool:
    """Check if task has important status"""
    # Bitrix24 task status field - check various possible field names
    status = task_data.get("STATUS", "")
    important = task_data.get("IMPORTANT", "")

    # Check if status contains "important" or if IMPORTANT field is set
    if isinstance(status, str):
        if "important" in status.lower() or "важно" in status.lower():
            return True

    if isinstance(important, (str, int, bool)):
        important_str = str(important).lower()
        if important_str in ["1", "true", "yes", "важно", "important"]:
            return True

    # Also check STATUS_ID if available (common Bitrix24 pattern)
    status_id = task_data.get("STATUS_ID", "")
    if str(status_id) in ["2", "3"]:  # Common important status IDs
        return True

    return False


def get_task_from_bitrix24(task_id: str, auth_token: str) -> Optional[Dict]:
    """Get full task data from Bitrix24 REST API"""
    if not task_id or not auth_token:
        return None
    
    # Формируем URL для REST API
    # Используем входящий webhook токен для получения данных
    # Формат: https://domain/rest/USER_ID/TOKEN/tasks.task.get
    # Но у нас есть только исходящий токен, попробуем другой формат
    
    # Альтернатива: используем исходящий токен напрямую
    domain = Config.BITRIX24_DOMAIN.replace("https://", "").replace("http://", "")
    rest_url = f"https://{domain}/rest/tasks.task.get"
    
    params = {
        "auth": auth_token,
        "taskId": task_id,
        "select": [
            "ID", "TITLE", "DESCRIPTION", "STATUS", "subStatus",
            "DEADLINE", "CREATED_DATE", "RESPONSIBLE_ID", "CREATED_BY",
            "PRIORITY", "MARK", "IMPORTANT"
        ]
    }
    
    try:
        response = requests.get(rest_url, params=params, timeout=10)
        response.raise_for_status()
        result = response.json()
        
        if result.get("result") and result["result"].get("task"):
            return result["result"]["task"]
        return None
    except Exception as e:
        print(f"❌ Error fetching task from Bitrix24: {e}")
        import sys
        sys.stderr.write(f"❌ Error fetching task {task_id} from Bitrix24: {e}\n")
        return None


def is_task_urgent(task_data: Dict) -> bool:
    """Check if task is urgent based on priority or deadline"""
    # Check priority
    priority = task_data.get("PRIORITY", "")
    try:
        priority_int = int(priority) if priority else 0
        if priority_int >= Config.URGENT_PRIORITY_THRESHOLD:
            if Config.DEBUG:
                print(
                    f"🔍 Task is urgent due to priority: {priority_int}"
                )
            return True
    except (ValueError, TypeError):
        pass

    # Check deadline
    deadline = task_data.get("DEADLINE", "")
    if deadline:
        try:
            # Try parsing various date formats
            deadline_dt = None
            date_formats = [
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%SZ",
                "%Y-%m-%d",
                "%d.%m.%Y %H:%M:%S",
                "%d.%m.%Y"
            ]

            for fmt in date_formats:
                try:
                    deadline_dt = datetime.strptime(str(deadline), fmt)
                    break
                except ValueError:
                    continue

            if deadline_dt:
                now = datetime.now()
                time_diff = deadline_dt - now
                hours_until_deadline = time_diff.total_seconds() / 3600

                if 0 <= hours_until_deadline <= Config.URGENT_DEADLINE_HOURS:
                    if Config.DEBUG:
                        print(
                            f"🔍 Task is urgent due to deadline: "
                            f"{hours_until_deadline:.1f} hours"
                        )
                    return True
        except Exception as e:
            if Config.DEBUG:
                print(f"⚠️ Error parsing deadline '{deadline}': {e}")

    return False


def extract_task_data(webhook_data: Dict) -> Optional[Dict]:
    """Extract and normalize task data from Bitrix24 webhook
    
    Bitrix24 sends data in format:
    {
        'event': 'OnTaskAdd' or 'OnTaskUpdate',
        'data': {
            'FIELDS_BEFORE': {...} or undefined,
            'FIELDS_AFTER': {
                'ID': 123,
                'TITLE': '...',
                'PRIORITY': '2',
                ...
            },
            ...
        },
        'ts': '...',
        'auth': {...}
    }
    """
    # Get data section
    data_section = webhook_data.get("data", {})
    
    if not data_section:
        return None
    
    # Bitrix24 sends task fields in FIELDS_AFTER
    # FIELDS_BEFORE may be undefined for OnTaskAdd
    task = data_section.get("FIELDS_AFTER")
    
    # Fallback: if FIELDS_AFTER is not present, try direct data structure
    # (for backward compatibility or different event types)
    if not task or task == "undefined":
        task = data_section
    
    # If still no task data, return None
    if not task or task == "undefined" or (isinstance(task, str) and task.lower() == "undefined"):
        return None
    
    # Extract task fields (Bitrix24 field names)
    task_id = task.get("ID", task.get("id", ""))
    title = task.get("TITLE", task.get("title", ""))
    priority = task.get("PRIORITY", task.get("priority", ""))
    deadline = task.get("DEADLINE", task.get("deadline", ""))
    responsible_id = task.get(
        "RESPONSIBLE_ID", task.get("responsible_id", "")
    )
    responsible_name = task.get(
        "RESPONSIBLE_NAME", task.get("responsible_name", "")
    )
    creator_id = task.get("CREATED_BY", task.get("created_by", ""))
    creator_name = task.get(
        "CREATED_BY_NAME", task.get("created_by_name", "")
    )
    status = task.get("STATUS", task.get("status", ""))
    
    # Build task link (assuming standard Bitrix24 URL structure)
    bitrix24_domain = Config.BITRIX24_DOMAIN
    if bitrix24_domain:
        # Remove https:// if present
        domain = bitrix24_domain.replace(
            "https://", ""
        ).replace("http://", "")
        task_link = (
            f"https://{domain}/company/personal/user/"
            f"{responsible_id}/tasks/task/view/{task_id}/"
        )  # noqa: E501
    else:
        task_link = f"#task_{task_id}"
    
    return {
        "id": str(task_id),
        "title": str(title) if title else "Без названия",
        "priority": str(priority),
        "deadline": str(deadline) if deadline else "",
        "responsible_id": str(responsible_id),
        "responsible_name": (
            str(responsible_name) if responsible_name
            else str(responsible_id)
        ),
        "creator_id": str(creator_id),
        "creator_name": str(creator_name) if creator_name else str(creator_id),
        "status": str(status),
        "link": task_link,
        "raw_data": task  # Keep raw data for debugging
    }


@app.route("/webhook_tasks", methods=["POST", "GET"])
def webhook_tasks():
    """Handle Bitrix24 webhook events for tasks"""
    try:
        # Bitrix24 может отправлять данные как POST JSON или GET параметры
        if request.method == "GET":
            # Данные в GET параметрах (для некоторых типов событий)
            webhook_data = dict(request.args)
            if Config.DEBUG:
                print(f"\n{'='*60}")
                print(f"📥 Received GET webhook at {datetime.now()}")
                print(f"{'='*60}")
                print(f"GET params: {webhook_data}")
        else:
            # Данные в POST теле
            raw_data = request.get_data(as_text=True)
            
            if Config.DEBUG:
                print(f"\n{'='*60}")
                print(f"📥 Received POST webhook at {datetime.now()}")
                print(f"{'='*60}")
                print(f"Headers: {dict(request.headers)}")
                print(f"Content-Type: {request.content_type}")
                print(f"Raw data: {raw_data[:500]}...")  # Первые 500 символов
            
            # Пробуем разные форматы
            webhook_data = None
            
            # Вариант 1: JSON в теле запроса
            if request.is_json:
                webhook_data = request.get_json()
                if Config.DEBUG:
                    print("✅ Parsed as JSON from request.get_json()")
            else:
                # Вариант 2: JSON строка в raw_data
                if raw_data:
                    try:
                        webhook_data = json.loads(raw_data)
                        if Config.DEBUG:
                            print("✅ Parsed as JSON from raw_data")
                    except json.JSONDecodeError:
                        # Вариант 3: Форма-данные (form-data) или query string
                        # Bitrix24 отправляет данные как form-data с вложенными ключами
                        # например: data[FIELDS_AFTER][ID] = "12672"
                        if request.form:
                            # Преобразуем плоскую структуру form-data в вложенную
                            webhook_data = {}
                            for key, value in request.form.items():
                                # Обрабатываем вложенные ключи типа data[FIELDS_AFTER][ID]
                                keys = key.replace(']', '').split('[')
                                current = webhook_data
                                for i, k in enumerate(keys):
                                    if i == len(keys) - 1:
                                        # Последний ключ - значение
                                        current[k] = value
                                    else:
                                        # Промежуточные ключи - словари
                                        if k not in current:
                                            current[k] = {}
                                        current = current[k]
                            if Config.DEBUG:
                                print("✅ Parsed as form-data with nested keys")
                        else:
                            # Вариант 4: Попробуем как query string в теле
                            try:
                                from urllib.parse import parse_qs, unquote
                                parsed = parse_qs(raw_data)
                                webhook_data = {}
                                for key, value_list in parsed.items():
                                    value = value_list[0] if value_list else ""
                                    # Обрабатываем вложенные ключи
                                    keys = key.replace(']', '').split('[')
                                    current = webhook_data
                                    for i, k in enumerate(keys):
                                        if i == len(keys) - 1:
                                            current[k] = unquote(value) if value else ""
                                        else:
                                            if k not in current:
                                                current[k] = {}
                                            current = current[k]
                                if Config.DEBUG:
                                    print("✅ Parsed as query string with nested keys")
                            except Exception as e:
                                if Config.DEBUG:
                                    print(f"❌ Failed to parse as query string: {e}")
                                pass
            
            if webhook_data is None:
                print(f"❌ Could not parse request data")
                print(f"   Raw data: {raw_data[:200]}")
                return jsonify({"error": "Could not parse request data"}), 400
        
        if Config.DEBUG:
            parsed_json = json.dumps(
                webhook_data, indent=2, ensure_ascii=False
            )
            print(f"Parsed data: {parsed_json}")
            # Логируем в файл для отладки
            import sys
            sys.stderr.write(f"\n{'='*60}\n")
            sys.stderr.write(f"📥 Webhook data at {datetime.now()}\n")
            sys.stderr.write(f"{parsed_json}\n")
            sys.stderr.write(f"{'='*60}\n")
        
        # Extract task ID from webhook
        task_fields_after = webhook_data.get("data", {}).get("FIELDS_AFTER", {})
        if not task_fields_after or task_fields_after == "undefined":
            task_fields_after = webhook_data.get("data", {})
        
        task_id = task_fields_after.get("ID", task_fields_after.get("id", ""))
        
        if not task_id:
            print("⚠️ No task ID found in webhook")
            import sys
            sys.stderr.write("⚠️ No task ID found in webhook\n")
            return jsonify({"status": "ok", "message": "No task ID"}), 200
        
        # Get auth token from webhook
        auth_data = webhook_data.get("auth", {})
        auth_token = auth_data.get("application_token", Config.BITRIX24_AUTH_TOKEN)
        
        # Get full task data from Bitrix24 REST API
        import sys
        sys.stderr.write(f"\n🔍 Fetching task {task_id} from Bitrix24...\n")
        full_task_data = get_task_from_bitrix24(task_id, auth_token)
        
        if not full_task_data:
            sys.stderr.write(f"⚠️ Could not fetch task {task_id} from Bitrix24\n")
            return jsonify({"status": "ok", "message": "Could not fetch task data"}), 200
        
        sys.stderr.write(f"✅ Task data fetched: {json.dumps(full_task_data, indent=2, ensure_ascii=False)}\n")
        
        # Extract task data for processing
        task_data = extract_task_data({"data": {"FIELDS_AFTER": full_task_data}})
        if not task_data:
            sys.stderr.write("⚠️ Could not extract task data\n")
            return jsonify({"status": "ok", "message": "Could not extract task data"}), 200
        
        creator_id = task_data.get("creator_id")
        responsible_id = task_data.get("responsible_id")
        
        # Логируем в stderr для отладки
        sys.stderr.write(f"\n🔍 Task ID: {task_id}\n")
        sys.stderr.write(f"🔍 Creator ID: {creator_id}\n")
        sys.stderr.write(f"🔍 Responsible ID: {responsible_id}\n")
        sys.stderr.write(f"🔍 Task data: {json.dumps(task_data, indent=2, ensure_ascii=False)}\n")
        
        if Config.DEBUG:
            print(f"\n🔍 Task ID: {task_id}")
            print(f"🔍 Creator ID: {creator_id}")
            print(f"🔍 Responsible ID: {responsible_id}")
        
        # Filter 1: Check if task is important
        # Use full task data from REST API
        task_fields = full_task_data
        
        sys.stderr.write(f"🔍 Task fields for filtering: {json.dumps(task_fields, indent=2, ensure_ascii=False)}\n")
        
        if not is_task_important(task_fields):
            msg = "⏭️ Task is not important - skipping"
            print(msg)
            sys.stderr.write(f"{msg}\n")
            return jsonify(
                {"status": "ok", "message": "Task not important"}
            ), 200

        # Filter 2: Check if creator is a leader
        if not is_leader(creator_id):
            msg = f"⏭️ Creator {creator_id} is not a leader - skipping"
            print(msg)
            sys.stderr.write(f"{msg}\n")
            return jsonify(
                {"status": "ok", "message": "Creator not a leader"}
            ), 200

        # Filter 3: Check if task is urgent
        # Use task_fields from Filter 1
        if not is_task_urgent(task_fields):
            msg = "⏭️ Task is not urgent - skipping"
            print(msg)
            sys.stderr.write(f"{msg}\n")
            return jsonify(
                {"status": "ok", "message": "Task not urgent"}
            ), 200

        # Get Telegram chat ID for responsible user
        telegram_chat_id = get_telegram_chat_id(responsible_id)
        if not telegram_chat_id:
            print(
                f"⚠️ No Telegram mapping found for user {responsible_id}"
            )
            return jsonify(
                {"status": "ok", "message": "No Telegram mapping"}
            ), 200
        
        # Determine event type (OnTaskAdd or OnTaskUpdate)
        event = webhook_data.get("event", "")
        event_type = "new" if "Add" in event else "updated"

        # Send Telegram notification
        success = send_task_notification(
            telegram_chat_id, task_data, event_type
        )

        if success:
            print(
                f"✅ Notification sent for task {task_id} "
                f"to user {responsible_id}"
            )
            return jsonify(
                {"status": "ok", "message": "Notification sent"}
            ), 200
        else:
            print(f"❌ Failed to send notification for task {task_id}")
            return jsonify(
                {"status": "error", "message": "Failed to send notification"}
            ), 500

    except Exception as e:
        print(f"❌ Error processing webhook: {e}")
        import traceback
        print(traceback.format_exc())
        return jsonify({"error": "Internal server error"}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify({"status": "ok", "service": "bitrix24_webhook"}), 200


if __name__ == "__main__":
    print(
        f"🚀 Starting Bitrix24 Webhook Service on "
        f"{Config.HOST}:{Config.PORT}"
    )
    print(f"📡 Webhook URL: {Config.WEBHOOK_URL}")
    print(f"🔧 Debug mode: {Config.DEBUG}")
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)

