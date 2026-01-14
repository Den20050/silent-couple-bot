# Следующие шаги после настройки БД

## ✅ Выполнено:
- [x] Создана база данных `silent_couple_bot`
- [x] Выданы права пользователю `bot_user`
- [x] Создана и применена первая миграция
- [x] Все таблицы созданы в БД

## 📋 Что делать дальше:

### 1. Проверка таблиц в БД

Вы можете проверить созданные таблицы:
```bash
psql -h localhost -p 5433 -U bot_user -d silent_couple_bot
\dt
```

### 2. Загрузка картинок

**Важно**: Перед загрузкой картинок убедитесь, что:
- Бот запущен и может отправлять вам сообщения
- Начните диалог с ботом командой `/start`

```bash
# Получите ваш Telegram chat_id:
# - Отправьте сообщение боту @userinfobot
# - Или начните диалог с вашим ботом

# Загрузите картинки:
python scripts/load_images.py <your_telegram_chat_id>
```

Это загрузит все картинки из `image/morning/` и `image/evening/` в Telegram и сохранит file_id в БД.

### 3. Запуск приложения

**Вариант 1: Единая точка входа (рекомендуется)**

```bash
# Запускает и бота, и worker одновременно
python run.py

# В отдельном терминале (опционально): Mini App (FastAPI)
uvicorn src.mini_app.main:app --host 0.0.0.0 --port 8000
```

**Вариант 2: Раздельный запуск (для отладки)**

В **трех разных терминалах** запустите:

**Терминал 1: Bot**
```bash
python -m src.bot.main
```

**Терминал 2: Worker (cron jobs)**
```bash
python -m src.worker.main
```

**Терминал 3: Mini App (FastAPI)**
```bash
uvicorn src.mini_app.main:app --host 0.0.0.0 --port 8000
```

### 4. Настройка Telegram Bot

После запуска бота:
1. Настройте webhook (если используете webhook вместо polling):
   ```bash
   curl "https://api.telegram.org/bot${TG_BOT_TOKEN}/setWebhook?url=https://your-domain.com/webhook/telegram"
   ```

2. Установите команды бота:
   ```bash
   curl -X POST "https://api.telegram.org/bot${TG_BOT_TOKEN}/setMyCommands" \
     -d 'commands=[{"command":"start","description":"Начать"},{"command":"pay","description":"Оплатить"},{"command":"delete","description":"Удалить данные"},{"command":"link","description":"Привязать чат"}]'
   ```

### 5. Тестирование

1. Откройте Telegram и найдите вашего бота
2. Отправьте `/start`
3. Пройдите онбординг
4. Пригласите партнёра (или создайте тестовую пару)

## 🔧 Настройка переменных окружения

Убедитесь, что в `.env` заполнены все необходимые переменные:

```env
TG_BOT_TOKEN=your_bot_token_here

# Database - выберите один из вариантов:
# Вариант 1: Локальная база данных (для разработки)
DATABASE_URL=postgresql+asyncpg://bot_user:password@localhost:5432/silent_couple_bot

# Вариант 2: Прямое подключение к PostgreSQL на сервере
# DATABASE_URL=postgresql+asyncpg://bot_user:password@your-server-ip:5432/silent_couple_bot

# Вариант 3: Подключение через SSH туннель (рекомендуется для продакшена)
# DATABASE_URL=postgresql+asyncpg://bot_user:password@localhost:5432/silent_couple_bot
# DATABASE_SSH_HOST=your-server-ip
# DATABASE_SSH_USER=root
# DATABASE_SSH_PORT=22

# Redis - выберите один из вариантов:
# Вариант 1: Локальный Redis (для разработки)
REDIS_URL=redis://localhost:6379/0

# Вариант 2: Прямое подключение к Redis на сервере
# REDIS_URL=redis://your-server-ip:6379/0

# Вариант 3: Подключение через SSH туннель (рекомендуется для продакшена)
# REDIS_URL=redis://127.0.0.1:6379/0
# REDIS_SSH_HOST=your-server-ip
# REDIS_SSH_USER=root
# REDIS_SSH_PORT=22

MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
```

## 📝 Примечания

- **PostgreSQL**: 
  - Локально: Убедитесь, что PostgreSQL запущен и доступен на порту 5432
  - На сервере: См. варианты подключения выше. Для SSH туннеля настройте SSH-ключи для автоматического подключения
- **Redis**: 
  - Локально: Если используете Docker Compose, Redis уже запущен на порту 6379
  - На сервере: См. варианты подключения выше. Для SSH туннеля настройте SSH-ключи для автоматического подключения
- **MinIO**: Если используете Docker Compose, MinIO доступен на портах 9000 (API) и 9001 (Console)

## 🐛 Решение проблем

Если что-то не работает:
1. Проверьте логи в каждом терминале
2. Убедитесь, что все сервисы запущены
3. Проверьте подключение к БД: `python scripts/check_db.py`
4. Проверьте переменные окружения в `.env`

