# Решение проблем

## ⚠️ Конфликт экземпляров бота (ВАЖНО!)

### Проблема: TelegramConflictError

**Симптомы:**
```
Failed to fetch updates - TelegramConflictError: Telegram server says - Conflict: terminated by other getUpdates request; make sure that only one bot instance is running
```

**Причина:** Запущено несколько экземпляров бота одновременно. Telegram API позволяет только **один** экземпляр бота использовать polling для одного токена.

**Быстрое решение:**

1. **Остановите все локальные экземпляры:**
   ```powershell
   # Windows PowerShell
   taskkill /f /im python.exe
   # Или нажмите Ctrl+C во всех терминалах с ботом
   ```

2. **Проверьте, не запущен ли бот на сервере:**
   ```bash
   ssh root@91.222.237.94
   sudo systemctl status silent-couple-bot-webhook
   ```
   Если запущен - остановите: `sudo systemctl stop silent-couple-bot-webhook`

3. **Удалите webhook (если был установлен):**
   ```bash
   curl -X POST "https://api.telegram.org/bot${TG_BOT_TOKEN}/deleteWebhook"
   ```

4. **Запустите только один экземпляр:**
   ```bash
   python run.py
   ```

**Правила:**
- ✅ Для разработки: запускайте только локально (`python run.py`)
- ✅ Для production: запускайте только на сервере (webhook)
- ❌ НЕ запускайте одновременно локально И на сервере
- ❌ НЕ запускайте несколько экземпляров локально

Подробнее: [TROUBLESHOOTING_CONFLICT.md](TROUBLESHOOTING_CONFLICT.md)

---

## Бот не отвечает на команды

### Проблема: Redis не запущен

**Симптомы:**
- Бот запускается, но не отвечает на команды
- Ошибка: "Error connecting to Redis"

**Решение:**

**Вариант 1: Локальный Redis через Docker (для разработки)**
```bash
# Убедитесь, что Docker Desktop запущен
docker-compose up -d redis

# Проверьте, что Redis запущен
docker ps | grep redis
```

**Вариант 2: Подключение к Redis на сервере**

Если Redis запущен на удаленном сервере, есть два способа подключения:

**2a. Прямое подключение (если Redis доступен извне)**
В `.env` укажите:
```env
REDIS_URL=redis://your-server-ip:6379/0
```
⚠️ Убедитесь, что порт 6379 открыт в firewall сервера.

**2b. Подключение через SSH туннель (рекомендуется для продакшена)**
В `.env` укажите:
```env
REDIS_URL=redis://127.0.0.1:6379/0
REDIS_SSH_HOST=your-server-ip
REDIS_SSH_USER=root
REDIS_SSH_PORT=22
```
Бот автоматически создаст SSH туннель при запуске, если Redis недоступен локально.

**Вариант 3: Использовать MemoryStorage (только для разработки)**
Бот автоматически использует MemoryStorage, если Redis недоступен.
- ✅ Работает без Docker и без сервера
- ⚠️ Состояние FSM теряется при перезапуске
- ⚠️ Не подходит для production

**Вариант 4: Установить Redis локально**
- Windows: скачайте Redis для Windows или используйте WSL
- Linux/Mac: `sudo apt install redis-server` или `brew install redis`

### Проверка подключений

Запустите скрипт проверки:
```bash
python scripts/test_bot.py
```

Должно показать:
- ✅ Бот подключен
- ✅ Redis подключен (или предупреждение, если используется MemoryStorage)
- ✅ База данных подключена

## Другие проблемы

### Бот не запускается

1. **Проверьте токен бота:**
   ```bash
   python scripts/test_bot.py
   ```

2. **Проверьте переменные окружения:**
   - Убедитесь, что файл `.env` существует
   - Проверьте, что все обязательные переменные заполнены

3. **Проверьте логи:**
   - При запуске бота должны быть логи
   - Ищите ошибки (ERROR level)

### Ошибки базы данных

**Симптомы:**
- Ошибка: "Database connection failed"
- Ошибка: "Connection refused" при подключении к PostgreSQL

**Решение:**

**Вариант 1: Локальная база данных (для разработки)**
```bash
# Убедитесь, что PostgreSQL запущен локально
# Windows: проверьте службы Windows
# Linux/Mac: sudo systemctl status postgresql
```

**Вариант 2: Подключение к PostgreSQL на сервере**

Если PostgreSQL запущен на удаленном сервере, есть два способа подключения:

**Подключение через SSH туннель (БД на сервере)**

База данных должна быть установлена на сервере (как и Redis). Бот автоматически создаст SSH туннель при запуске.

В `.env` укажите:
```env
DATABASE_URL=postgresql+asyncpg://bot_user:password@localhost:5432/silent_couple_bot
DATABASE_SSH_HOST=your-server-ip
DATABASE_SSH_USER=root
DATABASE_SSH_PORT=22
```

**Важно:**
- База данных должна быть установлена и настроена на сервере
- PostgreSQL на сервере должен слушать на localhost (127.0.0.1) для безопасности
- Бот автоматически создаст SSH туннель при запуске
- Для работы с разных ПК скопируйте `.env` на каждый ПК и настройте SSH ключи

Подробнее см. [DATABASE_SERVER_SETUP.md](DATABASE_SERVER_SETUP.md)

**Проверка подключения:**
1. **Проверьте подключение:**
   ```bash
   python scripts/check_db.py
   ```

2. **Проверьте права пользователя:**
   - Убедитесь, что `bot_user` имеет права на создание таблиц
   - См. `scripts/grant_permissions_db.sql`

3. **Проверьте SSH туннель:**
   - Убедитесь, что SSH-ключи настроены для автоматического подключения
   - Проверьте, что `DATABASE_SSH_HOST` указан правильно в `.env`

### Ошибки при загрузке картинок

1. **Бот должен быть запущен** и отвечать на команды
2. **Начните диалог с ботом** командой `/start`
3. **Проверьте chat_id** - используйте правильный ID

## Логи и отладка

### Включить подробные логи

В `.env` установите:
```env
LOG_LEVEL=DEBUG
```

### Просмотр логов бота

При запуске бота все логи выводятся в консоль в формате JSON.

### Типичные ошибки

**"Bot token is invalid"**
- Проверьте `TG_BOT_TOKEN` в `.env`
- Убедитесь, что токен правильный (от @BotFather)

**"Database connection failed"**
- Проверьте, что PostgreSQL запущен
- Проверьте `DATABASE_URL` в `.env`
- Запустите `python scripts/check_db.py`

**"Redis connection failed"**
- Бот будет работать с MemoryStorage (для разработки)
- Для production:
  - Если используете локальный Redis: запустите Redis (`docker-compose up -d redis`)
  - Если используете сервер: проверьте `REDIS_URL` и `REDIS_SSH_HOST` в `.env`
  - Проверьте подключение: `python scripts/check_redis.py`

