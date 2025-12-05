# Как активировать подписку на события Bitrix24

## Метод 1: Автоматическая подписка через Python скрипт (Рекомендуется)

### Шаг 1: Убедитесь, что .env файл настроен

Проверьте, что в файле `.env` указаны правильные значения:

```bash
BITRIX24_DOMAIN=intranet.vedagent.ru
BITRIX24_AUTH_TOKEN=ваш_токен_здесь
WEBHOOK_URL=http://bookntrack.online:8081/webhook_tasks
```

**Важно:** Для подписки на события нужен **исходящий webhook токен** (Outgoing Webhook), а не входящий!

### Шаг 2: Запустите скрипт подписки

```bash
cd ~/Notification_bot_test
source venv/bin/activate
python subscribe_bitrix24.py
```

Скрипт автоматически подпишет ваш webhook на события:
- `OnTaskAdd` - создание задачи
- `OnTaskUpdate` - обновление задачи

### Шаг 3: Проверьте результат

Если подписка успешна, вы увидите:
```
✅ Успешно подписан на OnTaskAdd
✅ Успешно подписан на OnTaskUpdate
```

---

## Метод 2: Ручная подписка через REST API

### Вариант A: Использование curl

Выполните следующие команды:

```bash
# Подписка на OnTaskAdd
curl "https://intranet.vedagent.ru/rest/event.bind.json?auth=ВАШ_ТОКЕН&event=OnTaskAdd&handler=http://bookntrack.online:8081/webhook_tasks"

# Подписка на OnTaskUpdate
curl "https://intranet.vedagent.ru/rest/event.bind.json?auth=ВАШ_ТОКЕН&event=OnTaskUpdate&handler=http://bookntrack.online:8081/webhook_tasks"
```

Замените `ВАШ_ТОКЕН` на ваш исходящий webhook токен.

### Вариант B: Использование браузера

Откройте в браузере следующие URL (замените `ВАШ_ТОКЕН`):

1. Для OnTaskAdd:
```
https://intranet.vedagent.ru/rest/event.bind.json?auth=ВАШ_ТОКЕН&event=OnTaskAdd&handler=http://bookntrack.online:8081/webhook_tasks
```

2. Для OnTaskUpdate:
```
https://intranet.vedagent.ru/rest/event.bind.json?auth=ВАШ_ТОКЕН&event=OnTaskUpdate&handler=http://bookntrack.online:8081/webhook_tasks
```

Если подписка успешна, вы увидите JSON ответ:
```json
{
  "result": true
}
```

---

## Метод 3: Через веб-интерфейс Bitrix24 (если доступно)

1. Войдите в Bitrix24 как администратор
2. Перейдите в **Настройки** → **Настройки портала** → **Вебхуки**
3. Найдите раздел **Исходящие вебхуки** или **Outgoing Webhooks**
4. Создайте новый исходящий webhook с URL: `http://bookntrack.online:8081/webhook_tasks`
5. Выберите события: `OnTaskAdd`, `OnTaskUpdate`
6. Сохраните настройки

**Примечание:** Интерфейс может отличаться в зависимости от версии Bitrix24.

---

## Как получить исходящий webhook токен

### Способ 1: Через настройки Bitrix24

1. Войдите в Bitrix24 как администратор
2. Перейдите в **Настройки** → **Настройки портала** → **Вебхуки**
3. Создайте новый **Исходящий вебхук** (Outgoing Webhook)
4. Скопируйте сгенерированный токен
5. Укажите URL: `http://bookntrack.online:8081/webhook_tasks`
6. Выберите события: `OnTaskAdd`, `OnTaskUpdate`

### Способ 2: Через REST API (если есть права)

Если у вас есть доступ к REST API, вы можете создать webhook программно.

---

## Проверка активности подписки

### Способ 1: Проверка через REST API

```bash
curl "https://intranet.vedagent.ru/rest/event.get.json?auth=ВАШ_ТОКЕН"
```

Это покажет все активные подписки.

### Способ 2: Тестовая задача

1. Создайте тестовую задачу в Bitrix24:
   - Статус: **Важно**
   - Приоритет: **Высокий** (2) или **Критический** (3)
   - Создатель: Вы (ID: 488)

2. Проверьте логи webhook сервиса:
```bash
ssh bookntrack@89.169.173.221 "tail -f ~/Notification_bot_test/access.log"
```

3. Если подписка активна, вы увидите POST запрос от Bitrix24 в логах.

---

## Устранение проблем

### Ошибка: "401 Unauthorized"

**Причина:** Неправильный токен или токен не имеет прав на подписку.

**Решение:**
- Убедитесь, что используете **исходящий** webhook токен, а не входящий
- Проверьте, что токен активен в настройках Bitrix24
- Убедитесь, что токен имеет права на подписку на события

### Ошибка: "Invalid handler URL"

**Причина:** URL недоступен из Bitrix24 или неправильный формат.

**Решение:**
- Проверьте, что URL доступен из интернета: `curl http://bookntrack.online:8081/health`
- Убедитесь, что порт 8081 открыт в firewall
- Проверьте формат URL (должен начинаться с `http://` или `https://`)

### Подписка создана, но события не приходят

**Возможные причины:**
1. Подписка неактивна (проверьте через `event.get`)
2. URL недоступен из Bitrix24 (проверьте firewall)
3. События не соответствуют фильтрам (проверьте логи)

**Решение:**
1. Проверьте активность подписки: `curl "https://intranet.vedagent.ru/rest/event.get.json?auth=ВАШ_ТОКЕН"`
2. Проверьте доступность URL извне
3. Создайте тестовую задачу и проверьте логи

---

## Дополнительная информация

- **Документация Bitrix24:** https://dev.1c-bitrix.ru/rest_help/general/event_bind.php
- **Список событий:** https://dev.1c-bitrix.ru/api_help/tasks/events/index.php

---

## Быстрая проверка

После подписки выполните:

```bash
# 1. Проверьте подписки
curl "https://intranet.vedagent.ru/rest/event.get.json?auth=ВАШ_ТОКЕН"

# 2. Создайте тестовую задачу в Bitrix24

# 3. Проверьте логи
ssh bookntrack@89.169.173.221 "tail -20 ~/Notification_bot_test/access.log"
```

Если в логах появился POST запрос от Bitrix24 - подписка работает! ✅

