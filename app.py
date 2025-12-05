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
    """Check if task has important status
    
    Проверяет различные варианты полей (верхний/нижний регистр, camelCase)
    """
    # Bitrix24 может возвращать поля в разных форматах:
    # - Верхний регистр: STATUS, IMPORTANT
    # - camelCase: status, important
    # - REST API: status, important
    
    # Проверяем статус (разные варианты названий)
    status = (
        task_data.get("STATUS") or 
        task_data.get("status") or 
        task_data.get("Status") or 
        ""
    )
    
    # Проверяем поле IMPORTANT (разные варианты)
    important = (
        task_data.get("IMPORTANT") or 
        task_data.get("important") or 
        task_data.get("Important") or 
        ""
    )
    
    # Проверяем STATUS_ID
    status_id = (
        task_data.get("STATUS_ID") or 
        task_data.get("statusId") or 
        task_data.get("status_id") or 
        ""
    )
    
    # Проверка статуса на наличие слова "important" или "важно"
    if isinstance(status, str):
        status_lower = status.lower()
        if "important" in status_lower or "важно" in status_lower:
            return True
    
    # Проверка поля IMPORTANT
    if important:
        important_str = str(important).lower()
        if important_str in ["1", "true", "yes", "важно", "important", "y"]:
            return True
    
    # Проверка поля isImportant (из REST API)
    is_important = (
        task_data.get("isImportant") or 
        task_data.get("IS_IMPORTANT") or 
        task_data.get("is_important") or 
        ""
    )
    if is_important:
        if isinstance(is_important, bool) and is_important:
            return True
        important_str = str(is_important).lower()
        if important_str in ["1", "true", "yes", "важно", "important", "y"]:
            return True
    
    # Проверка STATUS_ID (статусы 2, 3 часто означают важные задачи)
    if status_id:
        if str(status_id) in ["2", "3"]:
            return True
    
    # Если статус = 2 (выполняется) и приоритет высокий - считаем важной
    if str(status) == "2" or str(status_id) == "2":
        priority = (
            task_data.get("PRIORITY") or 
            task_data.get("priority") or 
            task_data.get("Priority") or 
            ""
        )
        try:
            priority_int = int(priority) if priority else 0
            if priority_int >= 2:  # Высокий или критический приоритет
                return True
        except (ValueError, TypeError):
            pass
    
    return False


def get_task_from_bitrix24(task_id: str, auth_data: Dict) -> Optional[Dict]:
    """Get full task data from Bitrix24 REST API
    
    Использует метод tasks.task.get для получения полных данных задачи.
    Поддерживает два формата авторизации:
    1. Входящий webhook: https://domain/rest/{user_id}/{token}/tasks.task.get
    2. Исходящий webhook: https://domain/rest/tasks.task.get?auth=token
    """
    if not task_id:
        return None
    
    domain = Config.BITRIX24_DOMAIN.replace("https://", "").replace("http://", "")
    
    # Пробуем разные варианты авторизации
    auth_methods = []
    
    # Метод 1: Входящий webhook токен из конфига (формат: user_id/token)
    if Config.BITRIX24_AUTH_TOKEN and "/" in Config.BITRIX24_AUTH_TOKEN:
        parts = Config.BITRIX24_AUTH_TOKEN.split("/")
        if len(parts) == 2:
            user_id, token = parts
            auth_methods.append({
                "type": "incoming",
                "url": f"https://{domain}/rest/{user_id}/{token}/tasks.task.get",
                "params": {"taskId": task_id}
            })
    
    # Метод 2: access_token из webhook (OAuth токен)
    access_token = auth_data.get("access_token")
    if access_token:
        auth_methods.append({
            "type": "oauth",
            "url": f"https://{domain}/rest/tasks.task.get",
            "params": {"auth": access_token, "taskId": task_id}
        })
    
    # Метод 3: application_token из webhook
    app_token = auth_data.get("application_token")
    if app_token:
        auth_methods.append({
            "type": "app_token",
            "url": f"https://{domain}/rest/tasks.task.get",
            "params": {"auth": app_token, "taskId": task_id}
        })
    
    # Метод 4: Токен из конфига (если не входящий)
    if Config.BITRIX24_AUTH_TOKEN and "/" not in Config.BITRIX24_AUTH_TOKEN:
        auth_methods.append({
            "type": "config_token",
            "url": f"https://{domain}/rest/tasks.task.get",
            "params": {"auth": Config.BITRIX24_AUTH_TOKEN, "taskId": task_id}
        })
    
    # Поля для выборки
    select_fields = [
        "ID", "TITLE", "DESCRIPTION", "STATUS", "subStatus",
        "DEADLINE", "CREATED_DATE", "CREATED_BY", "RESPONSIBLE_ID",
        "PRIORITY", "MARK", "IMPORTANT", "isImportant", "favorite"
    ]
    
    # Пробуем каждый метод авторизации
    for method in auth_methods:
        try:
            params = method["params"].copy()
            params["select"] = select_fields
            
            import sys
            sys.stderr.write(f"🔄 Trying auth method: {method['type']}\n")
            sys.stderr.write(f"   URL: {method['url']}\n")
            
            if method["type"] == "incoming":
                # Для входящего webhook используем POST с JSON
                response = requests.post(
                    method["url"],
                    json=params,
                    headers={"Content-Type": "application/json"},
                    timeout=10
                )
            else:
                # Для остальных методов используем GET с параметрами
                response = requests.get(method["url"], params=params, timeout=10)
            
            response.raise_for_status()
            result = response.json()
            
            # Проверяем наличие ошибки
            if result.get("error"):
                error_msg = result.get("error_description", result.get("error"))
                sys.stderr.write(f"❌ Auth method {method['type']} failed: {error_msg}\n")
                continue  # Пробуем следующий метод
            
            if result.get("result") and result["result"].get("task"):
                sys.stderr.write(f"✅ Successfully fetched task using {method['type']}\n")
                return result["result"]["task"]
            
        except Exception as e:
            import sys
            sys.stderr.write(f"❌ Error with auth method {method['type']}: {e}\n")
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_data = e.response.json()
                    sys.stderr.write(f"   Response: {json.dumps(error_data, indent=2, ensure_ascii=False)}\n")
                except:
                    sys.stderr.write(f"   Response text: {e.response.text[:200]}\n")
            continue  # Пробуем следующий метод
    
    import sys
    sys.stderr.write(f"❌ All auth methods failed for task {task_id}\n")
    return None


def is_task_urgent(task_data: Dict) -> bool:
    """Check if task is urgent based on priority or deadline"""
    # Check priority (поддерживаем разные форматы)
    priority = (
        task_data.get("PRIORITY") or 
        task_data.get("priority") or 
        task_data.get("Priority") or 
        ""
    )
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

    # Check deadline (поддерживаем разные форматы)
    deadline = (
        task_data.get("DEADLINE") or 
        task_data.get("deadline") or 
        task_data.get("Deadline") or 
        ""
    )
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
    
    Или из REST API (tasks.task.get):
    {
        'id': '123',
        'title': '...',
        'priority': '2',
        'createdBy': '488',
        'responsibleId': '488',
        'creator': {'id': '488', 'name': '...'},
        'responsible': {'id': '488', 'name': '...'},
        ...
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
    
    # Extract task fields (поддерживаем разные форматы: верхний регистр, camelCase)
    task_id = task.get("ID") or task.get("id") or ""
    title = task.get("TITLE") or task.get("title") or ""
    priority = task.get("PRIORITY") or task.get("priority") or ""
    deadline = task.get("DEADLINE") or task.get("deadline") or ""
    
    # Responsible (разные варианты)
    responsible_id = (
        task.get("RESPONSIBLE_ID") or 
        task.get("responsible_id") or 
        task.get("responsibleId") or 
        ""
    )
    responsible_name = (
        task.get("RESPONSIBLE_NAME") or 
        task.get("responsible_name") or 
        task.get("responsibleName") or 
        ""
    )
    
    # Если responsible_name не найден, но есть объект responsible
    if not responsible_name and "responsible" in task:
        responsible_obj = task.get("responsible", {})
        if isinstance(responsible_obj, dict):
            responsible_name = responsible_obj.get("name", "")
            if not responsible_id:
                responsible_id = responsible_obj.get("id", "")
    
    # Creator (разные варианты)
    creator_id = (
        task.get("CREATED_BY") or 
        task.get("created_by") or 
        task.get("createdBy") or 
        ""
    )
    creator_name = (
        task.get("CREATED_BY_NAME") or 
        task.get("created_by_name") or 
        task.get("createdByName") or 
        ""
    )
    
    # Если creator_name не найден, но есть объект creator
    if not creator_name and "creator" in task:
        creator_obj = task.get("creator", {})
        if isinstance(creator_obj, dict):
            creator_name = creator_obj.get("name", "")
            if not creator_id:
                creator_id = creator_obj.get("id", "")
    
    status = task.get("STATUS") or task.get("status") or ""
    
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
        
        # Get auth data from webhook
        auth_data = webhook_data.get("auth", {})
        
        # Get full task data from Bitrix24 REST API
        import sys
        sys.stderr.write(f"\n🔍 Fetching task {task_id} from Bitrix24...\n")
        sys.stderr.write(f"   Auth data available: {list(auth_data.keys())}\n")
        full_task_data = get_task_from_bitrix24(task_id, auth_data)
        
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

        # Get Telegram chat ID for responsible user (Исполнитель)
        # Уведомления отправляются ТОЛЬКО исполнителю задачи, а не всем
        sys.stderr.write(
            f"📤 Sending notification to RESPONSIBLE user (Исполнитель): {responsible_id}\n"
        )
        telegram_chat_id = get_telegram_chat_id(responsible_id)
        if not telegram_chat_id:
            msg = f"⚠️ No Telegram mapping found for responsible user {responsible_id}"
            print(msg)
            sys.stderr.write(f"{msg}\n")
            return jsonify(
                {"status": "ok", "message": "No Telegram mapping for responsible user"}
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

