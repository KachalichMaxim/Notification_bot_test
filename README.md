# Bitrix24 Telegram Webhook Service

Webhook service that receives Bitrix24 task events and sends Telegram notifications for urgent tasks created by leaders/managers.

## Features

- Receives Bitrix24 webhook events (`OnTaskAdd`, `OnTaskUpdate`)
- Multi-level filtering:
  1. Task must have "important" status
  2. Task creator must be in leaders/top managers list
  3. Task must be urgent (high/critical priority OR deadline within 24h)
- Sends Telegram notifications to responsible users
- Configurable via `.env` file
- User mappings stored in JSON file

## Quick Start (Быстрый старт)

### Автоматическая установка

Используйте скрипт `deploy.sh` для автоматической настройки:

```bash
# Полная установка
./deploy.sh install

# Запуск сервиса
./deploy.sh run

# Установка systemd service (требует sudo)
sudo ./deploy.sh install-service
```

Скрипт автоматически:
- Проверит наличие Python 3.8+
- Создаст виртуальное окружение
- Установит зависимости
- Настроит .env файл
- Создаст user_mappings.json
- Проверит доступность порта

## Setup

### 1. Install Dependencies

```bash
cd bitrix24_webhook
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the example `.env` file and fill in your values:

```bash
cp env.example .env
```

Edit `.env` and set:
- `TELEGRAM_BOT_TOKEN`: Get from @BotFather on Telegram
- `BITRIX24_DOMAIN`: Your Bitrix24 portal domain (e.g., `your-portal.bitrix24.ru`)
- `BITRIX24_AUTH_TOKEN`: Your webhook auth token
- `WEBHOOK_URL`: Your webhook endpoint URL
- Other settings as needed

### 3. Set Up User Mappings

The service uses `user_mappings.json` to store:
- **Leaders list**: Bitrix24 user IDs who are leaders/managers (only their tasks trigger notifications)
- **Telegram mappings**: Bitrix24 user ID → Telegram chat ID

#### Initial Setup

Create `user_mappings.json`:

```json
{
  "leaders": ["123", "456"],
  "telegram_chats": {
    "123": "987654321",
    "456": "123456789"
  }
}
```

#### How to Get Telegram Chat IDs

1. Start a chat with your bot
2. Send a message to the bot
3. Visit: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
4. Find your chat ID in the response (look for `"chat":{"id":123456789}`)

#### How to Get Bitrix24 User IDs

1. Go to Bitrix24 user profile
2. Check the URL: `https://your-portal.bitrix24.ru/company/personal/user/123/` - the number is the user ID
3. Or use Bitrix24 REST API: `https://your-portal.bitrix24.ru/rest/user.get.json?auth=YOUR_AUTH_TOKEN`

### 4. Subscribe to Bitrix24 Events

You need to subscribe your webhook to Bitrix24 events. Use the PHP script provided in the Bitrix24 documentation or use the REST API directly:

```php
<?php
$webhook_url = 'http://bookntrack.online:8080/webhook_tasks';
$auth_token = 'gu3ckdtubvwpbnru6418p8wbdv1khsqq';
$bitrix24_domain = 'your-portal.bitrix24.ru';

$rest_endpoint = 'https://' . $bitrix24_domain . '/rest/event.bind.json';

// Subscribe to OnTaskAdd
$eventDataAdd = [
    'auth' => $auth_token,
    'event' => 'OnTaskAdd',
    'handler' => $webhook_url
];

// Subscribe to OnTaskUpdate
$eventDataUpdate = [
    'auth' => $auth_token,
    'event' => 'OnTaskUpdate',
    'handler' => $webhook_url
];

// Send requests (use cURL or similar)
?>
```

### 5. Run the Service

```bash
python app.py
```

Or with gunicorn for production:

```bash
gunicorn -w 4 -b 0.0.0.0:8080 app:app
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `WEBHOOK_URL` | Full webhook endpoint URL | `http://bookntrack.online:8080/webhook_tasks` |
| `PORT` | Server port | `8080` |
| `HOST` | Server host | `0.0.0.0` |
| `TELEGRAM_BOT_TOKEN` | Telegram bot token (required) | - |
| `BITRIX24_DOMAIN` | Bitrix24 portal domain | - |
| `BITRIX24_AUTH_TOKEN` | Webhook auth token | `gu3ckdtubvwpbnru6418p8wbdv1khsqq` |
| `URGENT_PRIORITY_THRESHOLD` | Minimum priority for urgent (2=high, 3=critical) | `2` |
| `URGENT_DEADLINE_HOURS` | Hours before deadline to consider urgent | `24` |
| `DEBUG` | Enable debug logging | `false` |

## Task Filtering Logic

The service only sends notifications when ALL conditions are met:

1. **Status Check**: Task has "important" status
   - Checks `STATUS`, `IMPORTANT`, or `STATUS_ID` fields
   
2. **Creator Check**: Task creator is in the leaders list
   - Checks `CREATED_BY` field against `user_mappings.json` leaders list
   
3. **Urgency Check**: Task is urgent
   - Priority >= `URGENT_PRIORITY_THRESHOLD` (default: 2 = high)
   - OR deadline within `URGENT_DEADLINE_HOURS` (default: 24 hours)

4. **Notification**: Sends to responsible user
   - Uses `RESPONSIBLE_ID` to find Telegram chat ID
   - Only sends if mapping exists

## Managing User Mappings

### Using Python

```python
from user_mapping import *

# Add a leader
add_leader("123")

# Add Telegram mapping
add_telegram_mapping("123", "987654321")

# Check if user is leader
if is_leader("123"):
    print("User is a leader")

# Get Telegram chat ID
chat_id = get_telegram_chat_id("123")
```

### Manual JSON Editing

Edit `user_mappings.json` directly:

```json
{
  "leaders": ["123", "456", "789"],
  "telegram_chats": {
    "123": "987654321",
    "456": "123456789",
    "789": "555666777"
  }
}
```

## Testing

### Health Check

```bash
curl http://localhost:8080/health
```

### Test Webhook (with debug mode)

1. Set `DEBUG=true` in `.env`
2. Create a test task in Bitrix24 that meets all criteria
3. Check logs for detailed information

### Debug Mode

When `DEBUG=true`, the service will:
- Print full webhook payload
- Show filtering decisions
- Display detailed error messages

## Troubleshooting

### Notifications not sending

1. Check that task meets all filtering criteria:
   - Important status
   - Creator is in leaders list
   - Urgent (priority or deadline)
   - Responsible user has Telegram mapping

2. Enable debug mode: `DEBUG=true` in `.env`

3. Check logs for error messages

### Telegram errors

- Verify `TELEGRAM_BOT_TOKEN` is correct
- Ensure bot has permission to send messages to the chat
- Check that chat ID is correct (must be numeric string)

### Bitrix24 webhook not received

- Verify webhook subscription is active
- Check that `WEBHOOK_URL` is accessible from internet
- Ensure firewall allows incoming connections on the port

## Deployment

### Production Setup

1. Use a process manager (systemd, supervisor, etc.)
2. Use gunicorn or uWSGI for production server
3. Set up reverse proxy (nginx) if needed
4. Configure SSL/TLS for HTTPS
5. Set `DEBUG=false` in production

### Example systemd Service

```ini
[Unit]
Description=Bitrix24 Telegram Webhook
After=network.target

[Service]
User=your-user
WorkingDirectory=/path/to/bitrix24_webhook
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/gunicorn -w 4 -b 0.0.0.0:8080 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

## Files

- `app.py`: Main Flask application
- `config.py`: Configuration loader
- `telegram_bot.py`: Telegram notification functions
- `user_mapping.py`: User mapping management
- `.env`: Environment variables (create from `.env.example`)
- `user_mappings.json`: User mappings (created automatically)
- `requirements.txt`: Python dependencies

## License

Internal use only.

