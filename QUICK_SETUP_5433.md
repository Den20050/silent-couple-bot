# Быстрая настройка для PostgreSQL на порту 5433

Если PostgreSQL на сервере слушает на порту 5433 (как показано в `sudo pg_lsclusters`), используйте эту конфигурацию.

## Настройка .env файла

Добавьте в ваш `.env` файл:

```env
# База данных на сервере через SSH туннель (порт 5433)
DATABASE_URL=postgresql+asyncpg://bot_user:your_password@localhost:5433/silent_couple_bot

# SSH настройки для автоматического создания туннеля
DATABASE_SSH_HOST=91.222.237.94
DATABASE_SSH_USER=root
DATABASE_SSH_PORT=22

# Redis на сервере через SSH туннель
REDIS_URL=redis://127.0.0.1:6379/0
REDIS_SSH_HOST=91.222.237.94
REDIS_SSH_USER=root
REDIS_SSH_PORT=22
```

**Важно:**
- Порт в `DATABASE_URL` (5433) должен совпадать с портом PostgreSQL на сервере
- Бот автоматически создаст SSH туннель `localhost:5433 -> server:localhost:5433` при запуске

## Проверка подключения

```bash
# Проверка SSH туннеля и подключения к БД
python scripts/check_db_tunnel.py

# Общая проверка подключения
python scripts/check_db.py
```

## Применение миграций

```bash
# Примените миграции (туннель создастся автоматически)
python scripts/run_migration.py
```

## Запуск бота

```bash
# Бот автоматически создаст SSH туннель при запуске
python run.py
```

В логах вы увидите:
```
Creating SSH tunnel for PostgreSQL: root@91.222.237.94:22 -> localhost:5433 (remote: 5433)
SSH tunnel for PostgreSQL created automatically
```

## Альтернативный вариант (если хотите использовать другой локальный порт)

Если хотите использовать порт 5432 локально, но подключаться к 5433 на сервере:

```env
DATABASE_URL=postgresql+asyncpg://bot_user:your_password@localhost:5432/silent_couple_bot
DATABASE_SSH_HOST=91.222.237.94
DATABASE_SSH_USER=root
DATABASE_SSH_PORT=22
DATABASE_REMOTE_PORT=5433  # Порт PostgreSQL на сервере
```

В этом случае туннель будет: `localhost:5432 -> server:localhost:5433`

