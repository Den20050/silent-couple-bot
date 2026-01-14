# ✅ Быстрое решение конфликта экземпляров бота

## Проблема решена!

Webhook был успешно удален. Теперь можно запускать бота локально.

## Что было сделано

1. ✅ Остановлены все процессы Python
2. ✅ Удален webhook из Telegram API
3. ✅ Бот готов к запуску в polling режиме

## Запуск бота

Теперь запустите бот:

```powershell
python run.py
```

**Ожидаемый результат:**
- ✅ Бот запускается без ошибок `TelegramConflictError`
- ✅ Polling работает корректно
- ✅ Бот отвечает на команды в Telegram

## Если проблема повторится

### Проверка webhook статуса

```powershell
# Используйте скрипт
.\scripts\check_and_delete_webhook.ps1

# Или вручную через Python
python scripts/set_webhook.py delete
```

### Проверка запущенных процессов

```powershell
Get-Process python -ErrorAction SilentlyContinue
```

Если есть процессы - остановите их:
```powershell
taskkill /f /im python.exe
```

## Важно помнить

**Для локальной разработки:**
- ✅ Используйте polling (`python run.py`)
- ✅ Webhook должен быть удален
- ✅ Запускайте только один экземпляр

**Для production на сервере:**
- ✅ Используйте webhook (`python -m src.entrypoints.webhook`)
- ✅ Webhook должен быть установлен
- ✅ Не запускайте локально одновременно

## Полезные скрипты

- `scripts/check_bot_status.ps1` - проверка статуса бота
- `scripts/stop_all_bots.ps1` - остановка всех процессов
- `scripts/check_and_delete_webhook.ps1` - проверка и удаление webhook
- `scripts/set_webhook.py delete` - удаление webhook через Python
