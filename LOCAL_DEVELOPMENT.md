# Локальная разработка и тестирование

## Текущая настройка

✅ **Готово для локальной разработки:**
- Webhook удален (не мешает polling)
- Конфликта нет (бот не запущен на другом ПК)
- SSH туннели настроены автоматически

## Запуск бота локально

### Простой запуск

```powershell
python run.py
```

Это запустит:
- ✅ Бот в polling режиме
- ✅ Worker (cron задачи) в отдельном процессе

### Что вы увидите

```
SSH tunnel for Redis created automatically
SSH tunnel for PostgreSQL created automatically
Starting Silent Couple Bot (Bot + Worker)
Worker process started (PID: ...)
Bot connected: @tish_ob_bot
Starting polling...
```

### Проверка работы

1. Откройте Telegram
2. Найдите бота @tish_ob_bot
3. Отправьте `/start`
4. Бот должен ответить

## Остановка бота

Нажмите `Ctrl+C` в терминале - бот и worker остановятся корректно.

## Важные моменты

### SSH туннели

Бот автоматически создает SSH туннели для:
- ✅ Redis (127.0.0.1:6379 → сервер:6379)
- ✅ PostgreSQL (localhost:5432 → сервер:5432)

Туннели закрываются автоматически при остановке бота.

### Режим работы

- **Локально:** Polling режим (`python run.py`)
- **На сервере:** Webhook режим (`python -m src.entrypoints.webhook`)

**Важно:** Не запускайте одновременно локально И на сервере!

### Переменные окружения

Убедитесь, что в `.env` указаны:
```env
ENVIRONMENT=dev
# WEBHOOK_URL не указан (закомментирован)

DATABASE_SSH_HOST=91.222.237.94
REDIS_SSH_HOST=91.222.237.94
```

## Troubleshooting

### Конфликт экземпляров

Если появилась ошибка `TelegramConflictError`:
1. Остановите все процессы: `taskkill /f /im python.exe`
2. Проверьте webhook: `python scripts/check_webhook_status.py`
3. Если webhook установлен - удалите: `python scripts/set_webhook.py delete`

### Проблемы с SSH туннелями

Если туннели не создаются:
1. Проверьте SSH ключи: `ssh root@91.222.237.94`
2. Убедитесь, что порты свободны локально
3. Проверьте настройки в `.env`:
   - `DATABASE_SSH_HOST`
   - `REDIS_SSH_HOST`

### Бот не отвечает

1. Проверьте логи в консоли
2. Проверьте подключение к Redis и БД
3. Проверьте токен бота: `python scripts/test_bot.py`

## Полезные команды

```powershell
# Проверить статус бота
python scripts/check_bot_running_elsewhere.py

# Проверить webhook
python scripts/check_webhook_status.py

# Остановить все процессы
.\scripts\stop_all_bots.ps1

# Проверить процессы Python
Get-Process python -ErrorAction SilentlyContinue
```

## Переключение на production

Когда будете готовы задеплоить на сервер:

1. Установите webhook:
   ```powershell
   # Укажите WEBHOOK_URL в .env
   python scripts/set_webhook.py
   ```

2. Запустите на сервере:
   ```bash
   ssh root@91.222.237.94
   sudo systemctl start silent-couple-bot-webhook
   ```

3. Остановите локальный бот (если запущен)

4. НЕ запускайте локально - используйте только webhook на сервере

Подробнее: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
