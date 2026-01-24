# Пошаговое развертывание на сервере

## Шаг 1: Подключитесь к серверу

```bash
ssh root@91.222.237.94
```

## Шаг 2: Клонируйте проект с GitHub

```bash
cd /root
git clone git@github.com:Den20050/silent-couple-bot.git
cd silent-couple-bot
```

**Если SSH ключ для GitHub не настроен на сервере**, используйте HTTPS:

```bash
git clone https://github.com/Den20050/silent-couple-bot.git
cd silent-couple-bot
```

## Шаг 3: Создайте .env файл на сервере

**ВАЖНО:** На сервере НЕ используйте SSH туннели, так как БД и Redis находятся локально!

```bash
cd /root/silent-couple-bot
cp env.example .env
nano .env
```

### Настройки для сервера (БЕЗ SSH туннелей):

```env
# Telegram Bot
TG_BOT_TOKEN=your_bot_token_here

# База данных на сервере (локально, БЕЗ SSH туннеля!)
DATABASE_URL=postgresql+asyncpg://bot_user:your_password@localhost:5432/silent_couple_bot
# НЕ указывайте DATABASE_SSH_HOST на сервере!

# Redis на сервере (локально, БЕЗ SSH туннеля!)
REDIS_URL=redis://127.0.0.1:6379/0
# НЕ указывайте REDIS_SSH_HOST на сервере!

# Telegram Bot Webhook
WEBHOOK_URL=https://24policybot.ru/webhook/telegram
WEBHOOK_PATH=/webhook/telegram
WEBHOOK_PORT=8443
WEBHOOK_SECRET_TOKEN=your-secret-token-here

# Robokassa Payment
ROBOKASSA_MERCHANT_LOGIN=your_merchant_login
ROBOKASSA_PASSWORD_1=your_password_1
ROBOKASSA_PASSWORD_2=your_password_2
ROBOKASSA_IS_PRODUCTION=false
ROBOKASSA_DOMAIN=robokassa.ru

# Admin
ADMIN_TG_ID=your_admin_tg_id

# Остальные настройки оставьте по умолчанию или настройте по необходимости
```

**Сгенерируйте секретный токен для webhook:**

```bash
openssl rand -hex 32
```

Скопируйте результат и вставьте в `WEBHOOK_SECRET_TOKEN`.

## Шаг 4: Установите зависимости

```bash
cd /root/silent-couple-bot

# Установите зависимости Python
pip3 install -r requirements.txt

# Установите uvicorn для webhook сервера
pip3 install uvicorn[standard]
```

## Шаг 5: Проверьте конфигурацию Nginx

Убедитесь, что Nginx настроен для `/webhook/robokassa`:

```bash
sudo nano /etc/nginx/sites-available/24policybot.ru
```

Должны быть два location блока:

```nginx
# Проксирование Telegram webhook
location /webhook/telegram {
    proxy_pass http://127.0.0.1:8443;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_set_header X-Telegram-Bot-Api-Secret-Token $http_x_telegram_bot_api_secret_token;
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
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
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

## Шаг 6: Создайте systemd service

```bash
cd /root/silent-couple-bot

# Скопируйте service файл
sudo cp deploy/webhook.service /etc/systemd/system/silent-couple-bot-webhook.service

# Проверьте содержимое
sudo nano /etc/systemd/system/silent-couple-bot-webhook.service
```

Убедитесь, что:
- `WorkingDirectory=/root/silent-couple-bot` (или правильный путь)
- `ExecStart=/usr/bin/python3 -m src.entrypoints.webhook`

Перезагрузите systemd:

```bash
sudo systemctl daemon-reload
```

## Шаг 7: Проверьте подключение к БД и Redis

```bash
cd /root/silent-couple-bot

# Проверьте подключение к PostgreSQL
psql -U bot_user -d silent_couple_bot -c "SELECT 1;"

# Проверьте подключение к Redis
redis-cli ping
```

Должно вернуть `PONG`.

## Шаг 8: Запустите webhook сервер

```bash
# Запустите сервис
sudo systemctl start silent-couple-bot-webhook

# Проверьте статус
sudo systemctl status silent-couple-bot-webhook

# Включите автозапуск
sudo systemctl enable silent-couple-bot-webhook
```

## Шаг 9: Проверьте логи

```bash
# Просмотр логов в реальном времени
sudo journalctl -u silent-couple-bot-webhook -f

# Последние 50 строк
sudo journalctl -u silent-couple-bot-webhook -n 50 --no-pager
```

Если видите ошибки, проверьте:
- Правильность путей в service файле
- Наличие всех зависимостей
- Правильность настроек в .env

## Шаг 10: Проверьте доступность endpoints

```bash
# Health check
curl https://24policybot.ru/health

# Robokassa webhook (должен вернуть ошибку, но не 404)
curl -X POST https://24policybot.ru/webhook/robokassa
```

Если получаете 404 - проверьте Nginx конфигурацию.  
Если получаете другую ошибку - проверьте логи webhook сервера.

## Шаг 11: Настройте ResultURL в Робокассе

1. Войдите в личный кабинет Робокассы
2. Перейдите в настройки магазина
3. Укажите ResultURL: `https://24policybot.ru/webhook/robokassa`
4. Сохраните настройки

## Обновление кода на сервере

После изменений в коде:

```bash
# На сервере
cd /root/silent-couple-bot
git pull
sudo systemctl restart silent-couple-bot-webhook
```

## Troubleshooting

### Webhook сервер не запускается

```bash
# Проверьте логи
sudo journalctl -u silent-couple-bot-webhook -n 100 --no-pager

# Проверьте, что директория существует
ls -la /root/silent-couple-bot

# Проверьте Python модуль
cd /root/silent-couple-bot
python3 -m src.entrypoints.webhook --help
```

### Ошибка подключения к БД

Убедитесь, что в `.env` НЕТ `DATABASE_SSH_HOST`:
```bash
grep DATABASE_SSH_HOST /root/silent-couple-bot/.env
```

Если выводит что-то - удалите эту строку!

### Ошибка подключения к Redis

Убедитесь, что в `.env` НЕТ `REDIS_SSH_HOST`:
```bash
grep REDIS_SSH_HOST /root/silent-couple-bot/.env
```

Если выводит что-то - удалите эту строку!

### Endpoint возвращает 404

1. Проверьте Nginx конфигурацию
2. Проверьте, что webhook сервер запущен
3. Проверьте порт 8443:
   ```bash
   sudo netstat -tlnp | grep 8443
   ```
