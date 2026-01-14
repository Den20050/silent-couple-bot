# Быстрый старт Webhook для 24policybot.ru

## Шаги для запуска

### 1. Настройте .env файл

```bash
cd /root/Silent-Couple-Bot
nano .env
```

Добавьте/обновите следующие строки:

```env
WEBHOOK_URL=https://24policybot.ru/webhook/telegram
WEBHOOK_PATH=/webhook/telegram
WEBHOOK_PORT=8443
WEBHOOK_SECRET_TOKEN=<сгенерируйте: openssl rand -hex 32>
```

### 2. Установите зависимости

```bash
pip3 install -r requirements.txt
pip3 install uvicorn[standard]
```

### 3. Установите systemd service

```bash
sudo cp deploy/webhook.service /etc/systemd/system/silent-couple-bot-webhook.service
sudo nano /etc/systemd/system/silent-couple-bot-webhook.service  # Проверьте пути
sudo systemctl daemon-reload
```

### 4. Запустите webhook сервер

```bash
sudo systemctl start silent-couple-bot-webhook
sudo systemctl enable silent-couple-bot-webhook
sudo systemctl status silent-couple-bot-webhook
```

### 5. Установите webhook в Telegram

```bash
cd /root/Silent-Couple-Bot
python3 scripts/set_webhook.py
```

### 6. Проверьте работу

```bash
# Проверьте статус
sudo systemctl status silent-couple-bot-webhook

# Проверьте логи
sudo journalctl -u silent-couple-bot-webhook -f

# Проверьте health endpoint
curl https://24policybot.ru/health

# Проверьте webhook статус
curl "https://api.telegram.org/bot${TG_BOT_TOKEN}/getWebhookInfo"
```

## Готово! 🎉

Бот теперь работает через webhook. Отправьте сообщение боту в Telegram и проверьте логи.

Подробная документация: `WEBHOOK_DEPLOYMENT.md`

