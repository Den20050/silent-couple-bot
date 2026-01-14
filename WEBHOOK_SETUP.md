# Настройка Telegram Webhook

## Зачем нужен webhook?

Webhook позволяет:
- **Автоматически определять часовой пояс** пользователей по IP-адресу
- Более эффективно обрабатывать обновления (Telegram отправляет их напрямую)
- Лучше подходит для production окружения

## Требования

1. **Домен с SSL сертификатом** (HTTPS обязателен для Telegram webhook)
2. **Доступный порт** для webhook сервера (по умолчанию 8443)
3. **Настроенный reverse proxy** (nginx, traefik и т.д.) для проксирования запросов

## Быстрый старт

### 1. Обновите `.env` файл

```env
# Telegram Bot Webhook
WEBHOOK_URL=https://your-domain.com/webhook/telegram
WEBHOOK_PATH=/webhook/telegram
WEBHOOK_PORT=8443
WEBHOOK_SECRET_TOKEN=your-secret-token-here  # Рекомендуется для безопасности
```

### 2. Запустите webhook сервер

```bash
uvicorn src.bot.webhook_server:app --host 0.0.0.0 --port 8443
```

Или через `run.py` (если обновлен для поддержки webhook):

```bash
python run.py
```

### 3. Настройте webhook в Telegram

После запуска сервера установите webhook:

**Вариант 1: Используйте готовый скрипт (рекомендуется)**

```bash
python scripts/set_webhook.py
```

**Вариант 2: Через curl**

```bash
curl -X POST "https://api.telegram.org/bot${TG_BOT_TOKEN}/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-domain.com/webhook/telegram",
    "secret_token": "your-secret-token-here"
  }'
```

**Вариант 3: Через Python**

```python
import asyncio
from src.bot.webhook_server import set_webhook

asyncio.run(set_webhook())
```

### 4. Проверьте статус webhook

```bash
curl "https://api.telegram.org/bot${TG_BOT_TOKEN}/getWebhookInfo"
```

Должен вернуть информацию о текущем webhook.

## Настройка Nginx (пример)

```nginx
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location /webhook/telegram {
        proxy_pass http://localhost:8443;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## Переключение обратно на polling

Если нужно вернуться к polling:

```bash
curl -X POST "https://api.telegram.org/bot${TG_BOT_TOKEN}/deleteWebhook"
```

Или через Python:

```python
import asyncio
from src.bot.webhook_server import delete_webhook

asyncio.run(delete_webhook())
```

Затем запустите бота в режиме polling:

```bash
python -m src.bot.main
```

## Проверка работы

1. Отправьте сообщение боту в Telegram
2. Проверьте логи webhook сервера - должны быть записи о полученных обновлениях
3. Проверьте, что IP-адрес извлекается корректно (в логах должно быть "IP extracted from request")

## Troubleshooting

### Webhook не работает

1. Проверьте, что сервер доступен из интернета:
   ```bash
   curl https://your-domain.com/webhook/telegram
   ```

2. Проверьте SSL сертификат:
   ```bash
   curl -v https://your-domain.com/webhook/telegram
   ```

3. Проверьте логи webhook сервера

### IP-адрес не определяется

- Убедитесь, что reverse proxy передает заголовки `X-Real-IP` или `X-Forwarded-For`
- Проверьте настройки nginx/traefik для передачи IP

### Webhook возвращает 403

- Проверьте, что `WEBHOOK_SECRET_TOKEN` совпадает в `.env` и при установке webhook
- Убедитесь, что заголовок `X-Telegram-Bot-Api-Secret-Token` передается корректно
