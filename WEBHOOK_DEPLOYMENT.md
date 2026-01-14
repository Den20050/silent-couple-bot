# Развертывание Webhook для Silent Couple Bot

## Текущая инфраструктура

✅ **Уже настроено:**
- Домен `24policybot.ru` зарегистрирован и делегирован NS-серверам Timeweb
- A-запись на внешний IP `91.222.237.94`
- Порты 22, 80, 443 открыты во внешнем firewall
- Nginx установлен и настроен
- Let's Encrypt сертификат выпущен для `24policybot.ru` + `www.24policybot.ru`
- PostgreSQL и Redis работают на сервере
- Nginx настроен:
  - 80-й порт → редирект на HTTPS
  - 443-й порт → SSL termination + проксирование `/webhook/telegram` на `127.0.0.1:8443`

## Архитектура

- **Локально (Windows)**: Разработка, бот в режиме polling
- **На сервере**: PostgreSQL, Redis, Nginx, Webhook сервер (для production)

## Что нужно сделать дальше

### 1. Скопируйте проект на сервер

**Вариант A: Через Git (рекомендуется)**

```bash
# На сервере
cd /root
git clone <your-repo-url> Silent-Couple-Bot
cd Silent-Couple-Bot
```

**Вариант B: Через SCP (если нет Git)**

```bash
# На локальной машине (Windows PowerShell)
scp -r C:\Silent-Couple-Bot root@91.222.237.94:/root/Silent-Couple-Bot
```

### 2. Настройте переменные окружения на сервере

**Важно:** На сервере `.env` файл должен быть настроен БЕЗ SSH туннелей, так как БД и Redis находятся локально на сервере.

Отредактируйте файл `.env` на сервере:

```bash
cd /root/Silent-Couple-Bot
cp env.example .env
nano .env
```

**Настройки для сервера (БЕЗ SSH туннелей):**

```env
# Telegram Bot
TG_BOT_TOKEN=your_bot_token

# База данных на сервере (локально, БЕЗ SSH туннеля)
DATABASE_URL=postgresql+asyncpg://bot_user:your_password@localhost:5432/silent_couple_bot
# НЕ указывайте DATABASE_SSH_HOST на сервере!

# Redis на сервере (локально, БЕЗ SSH туннеля)
REDIS_URL=redis://127.0.0.1:6379/0
# НЕ указывайте REDIS_SSH_HOST на сервере!

# Telegram Bot Webhook
WEBHOOK_URL=https://24policybot.ru/webhook/telegram
WEBHOOK_PATH=/webhook/telegram
WEBHOOK_PORT=8443
WEBHOOK_SECRET_TOKEN=your-secret-token-here  # Сгенерируйте: openssl rand -hex 32

# Robokassa Payment
ROBOKASSA_MERCHANT_LOGIN=your_merchant_login
ROBOKASSA_PASSWORD_1=your_password_1
ROBOKASSA_PASSWORD_2=your_password_2
ROBOKASSA_IS_PRODUCTION=false
ROBOKASSA_DOMAIN=robokassa.ru

# Admin
ADMIN_TG_ID=your_admin_tg_id
```

**Важно:** Сгенерируйте секретный токен для webhook:
```bash
openssl rand -hex 32
```

### 3. Установите зависимости на сервере

```bash
cd /root/Silent-Couple-Bot
pip3 install -r requirements.txt
pip3 install uvicorn[standard]
```

### 4. Проверьте конфигурацию Nginx

Убедитесь, что конфигурация Nginx правильная. Файл должен быть примерно таким:

```nginx
# /etc/nginx/sites-available/24policybot.ru

# Редирект HTTP на HTTPS
server {
    listen 80;
    server_name 24policybot.ru www.24policybot.ru;
    return 301 https://$server_name$request_uri;
}

# HTTPS сервер
server {
    listen 443 ssl http2;
    server_name 24policybot.ru www.24policybot.ru;

    # SSL сертификаты (Let's Encrypt)
    ssl_certificate /etc/letsencrypt/live/24policybot.ru/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/24policybot.ru/privkey.pem;

    # SSL настройки
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Проксирование Telegram webhook на локальный сервер
    location /webhook/telegram {
        proxy_pass http://127.0.0.1:8443;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Важно: передаем секретный токен от Telegram
        proxy_set_header X-Telegram-Bot-Api-Secret-Token $http_x_telegram_bot_api_secret_token;
        
        # Таймауты
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Проксирование Robokassa webhook (ResultURL)
    location /webhook/robokassa {
        proxy_pass http://127.0.0.1:8443;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # Таймауты для платежных уведомлений
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check endpoint (опционально)
    location /health {
        proxy_pass http://127.0.0.1:8443;
        proxy_set_header Host $host;
    }
}
```

Проверьте конфигурацию:
```bash
sudo nginx -t
```

Если все ОК, перезагрузите Nginx:
```bash
sudo systemctl reload nginx
```

### 5. Создайте systemd service

Скопируйте service файл:

```bash
sudo cp /root/Silent-Couple-Bot/deploy/webhook.service /etc/systemd/system/silent-couple-bot-webhook.service
```

Отредактируйте пути при необходимости:

```bash
sudo nano /etc/systemd/system/silent-couple-bot-webhook.service
```

Убедитесь, что:
- `WorkingDirectory=/root/Silent-Couple-Bot` (или правильный путь к проекту)
- `ExecStart=/usr/bin/python3 -m src.entrypoints.webhook` (или правильный путь к Python)

Перезагрузите systemd:
```bash
sudo systemctl daemon-reload
```

### 6. Запустите webhook сервер

```bash
# Запустите сервис
sudo systemctl start silent-couple-bot-webhook

# Проверьте статус
sudo systemctl status silent-couple-bot-webhook

# Включите автозапуск
sudo systemctl enable silent-couple-bot-webhook
```

### 7. Проверьте логи

```bash
# Просмотр логов в реальном времени
sudo journalctl -u silent-couple-bot-webhook -f

# Последние 100 строк
sudo journalctl -u silent-couple-bot-webhook -n 100 --no-pager
```

### 8. Проверьте доступность endpoints

```bash
# Проверка health check
curl https://24policybot.ru/health

# Проверка Robokassa webhook (должен вернуть ошибку, но не 404)
curl -X POST https://24policybot.ru/webhook/robokassa
```

### 9. Настройте ResultURL в личном кабинете Робокассы

1. Войдите в личный кабинет Робокассы
2. Перейдите в настройки магазина
3. Укажите ResultURL: `https://24policybot.ru/webhook/robokassa`
4. Сохраните настройки

## Обновление кода на сервере

После изменений в коде на локальной машине:

```bash
# На локальной машине: закоммитьте и запушьте изменения
git add .
git commit -m "Update code"
git push

# На сервере: обновите код
cd /root/Silent-Couple-Bot
git pull

# Перезапустите webhook сервер
sudo systemctl restart silent-couple-bot-webhook
```

## Troubleshooting

### Webhook сервер не запускается

1. Проверьте логи:
   ```bash
   sudo journalctl -u silent-couple-bot-webhook -n 50 --no-pager
   ```

2. Проверьте, что директория существует:
   ```bash
   ls -la /root/Silent-Couple-Bot
   ```

3. Проверьте, что Python может импортировать модуль:
   ```bash
   cd /root/Silent-Couple-Bot
   python3 -m src.entrypoints.webhook --help
   ```

4. Проверьте права доступа:
   ```bash
   sudo chown -R root:root /root/Silent-Couple-Bot
   ```

### Endpoint возвращает 404

1. Проверьте, что Nginx настроен для `/webhook/robokassa`
2. Проверьте, что webhook сервер запущен:
   ```bash
   sudo systemctl status silent-couple-bot-webhook
   ```
3. Проверьте, что порт 8443 слушается:
   ```bash
   sudo netstat -tlnp | grep 8443
   ```

### Ошибка подключения к БД или Redis

На сервере НЕ должны быть указаны SSH туннели в `.env`:
- НЕ указывайте `DATABASE_SSH_HOST`
- НЕ указывайте `REDIS_SSH_HOST`

Используйте прямые подключения:
- `DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/db`
- `REDIS_URL=redis://127.0.0.1:6379/0`

## Разница между локальной и серверной конфигурацией

**Локально (Windows):**
- БД и Redis на сервере → используйте SSH туннели
- `DATABASE_SSH_HOST=91.222.237.94`
- `REDIS_SSH_HOST=91.222.237.94`
- Бот работает в режиме polling

**На сервере:**
- БД и Redis локально → БЕЗ SSH туннелей
- НЕ указывайте `DATABASE_SSH_HOST`
- НЕ указывайте `REDIS_SSH_HOST`
- Webhook сервер работает на порту 8443
