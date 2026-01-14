# Восстановление webhook (если бот должен работать на сервере)

## Текущая ситуация

✅ **Проверка показала:**
- Webhook НЕ установлен
- Конфликта polling нет (бот не запущен на другом ПК)
- Можно запускать локально в polling режиме

## Если нужно восстановить webhook

### Шаг 1: Настройте .env

Откройте `.env` и раскомментируйте/заполните:

```env
WEBHOOK_URL=https://24policybot.ru/webhook/telegram
WEBHOOK_PATH=/webhook/telegram
WEBHOOK_PORT=8443
WEBHOOK_SECRET_TOKEN=your-secret-token-here  # Сгенерируйте: openssl rand -hex 32
```

### Шаг 2: Восстановите webhook

```powershell
python scripts/restore_webhook_safely.py
```

Скрипт:
- ✅ Проверит текущий статус
- ✅ Проверит конфликт polling
- ✅ Установит webhook безопасно

### Шаг 3: Проверьте на сервере

```bash
ssh root@91.222.237.94
sudo systemctl status silent-couple-bot-webhook
```

Если сервис не запущен - запустите:
```bash
sudo systemctl start silent-couple-bot-webhook
sudo systemctl enable silent-couple-bot-webhook
```

### Шаг 4: Проверьте работу

1. Отправьте сообщение боту в Telegram
2. Проверьте логи на сервере:
   ```bash
   sudo journalctl -u silent-couple-bot-webhook -f
   ```

## Если webhook установлен

**Важно:**
- ✅ Бот должен работать на сервере через webhook
- ❌ НЕ запускайте бот локально в polling режиме
- ✅ Для разработки используйте другой токен или удалите webhook временно

## Если webhook НЕ нужен (локальная разработка)

Оставьте webhook удаленным и запускайте локально:
```powershell
python run.py
```

## Полезные команды

```powershell
# Проверить статус webhook
python scripts/check_webhook_status.py

# Проверить, запущен ли бот на другом ПК
python scripts/check_bot_running_elsewhere.py

# Тест конфликта polling
python scripts/test_bot_conflict.py

# Установить webhook
python scripts/set_webhook.py

# Удалить webhook
python scripts/set_webhook.py delete

# Безопасное восстановление webhook
python scripts/restore_webhook_safely.py
```
