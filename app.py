"""Main Flask application for Bitrix24 webhook"""
from flask import Flask, request, jsonify
import json
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
    """Extract and normalize task data from Bitrix24 webhook"""
    # Bitrix24 webhook structure: data contains the task object
    task = webhook_data.get("data", {})
    
    if not task:
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
                        # Вариант 3: Форма-данные (form-data)
                        if request.form:
                            webhook_data = dict(request.form)
                            if Config.DEBUG:
                                print("✅ Parsed as form-data")
                        else:
                            # Вариант 4: Попробуем как query string в теле
                            try:
                                from urllib.parse import parse_qs
                                parsed = parse_qs(raw_data)
                                webhook_data = {k: v[0] if len(v) == 1 else v 
                                               for k, v in parsed.items()}
                                if Config.DEBUG:
                                    print("✅ Parsed as query string")
                            except Exception:
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
        
        # Extract task data
        task_data = extract_task_data(webhook_data)
        if not task_data:
            print("⚠️ No task data found in webhook")
            return jsonify({"status": "ok", "message": "No task data"}), 200
        
        task_id = task_data.get("id")
        creator_id = task_data.get("creator_id")
        responsible_id = task_data.get("responsible_id")
        
        if Config.DEBUG:
            print(f"\n🔍 Task ID: {task_id}")
            print(f"🔍 Creator ID: {creator_id}")
            print(f"🔍 Responsible ID: {responsible_id}")
        
        # Filter 1: Check if task is important
        if not is_task_important(webhook_data.get("data", {})):
            if Config.DEBUG:
                print("⏭️ Task is not important - skipping")
            return jsonify(
                {"status": "ok", "message": "Task not important"}
            ), 200

        # Filter 2: Check if creator is a leader
        if not is_leader(creator_id):
            if Config.DEBUG:
                print(
                    f"⏭️ Creator {creator_id} is not a leader - skipping"
                )
            return jsonify(
                {"status": "ok", "message": "Creator not a leader"}
            ), 200

        # Filter 3: Check if task is urgent
        if not is_task_urgent(webhook_data.get("data", {})):
            if Config.DEBUG:
                print("⏭️ Task is not urgent - skipping")
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

