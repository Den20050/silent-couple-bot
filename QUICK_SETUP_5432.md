# Быстрая настройка для PostgreSQL на порту 5432

PostgreSQL на сервере слушает на стандартном порту 5432.

## Настройка .env файла

Добавьте в ваш `.env` файл:

```env
# База данных на сервере через SSH туннель (порт 5432)
DATABASE_URL=postgresql+asyncpg://bot_user:your_password@localhost:5432/silent_couple_bot

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
- Порт в `DATABASE_URL` (5432) совпадает с портом PostgreSQL на сервере
- Бот автоматически создаст SSH туннель `localhost:5432 -> server:localhost:5432` при запуске
- **Убедитесь, что локальный PostgreSQL на Windows НЕ запущен на порту 5432**, иначе туннель не создастся

## Проверка локального PostgreSQL

Проверьте, не запущен ли локальный PostgreSQL на порту 5432:

```bash
python scripts/check_local_postgresql.py
```

Если локальный PostgreSQL запущен на 5432, остановите его:

```powershell
# Запустите PowerShell от имени администратора
Get-Service | Where-Object {$_.Name -like "*postgresql*"}
Stop-Service postgresql-x64-18  # замените на реальное имя службы
```

## Проверка подключения

```bash
# Проверка SSH туннеля и подключения к БД
python scripts/check_db_tunnel.py

# Проверка источника подключения (должно быть Linux/Ubuntu, не Windows)
python scripts/check_db_source.py
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
Creating SSH tunnel for PostgreSQL: root@91.222.237.94:22 -> localhost:5432 (remote: 5432)
SSH tunnel for PostgreSQL created automatically
```

## Если локальный PostgreSQL нужен

Если вам нужен локальный PostgreSQL на Windows, измените его порт на другой (например, 5434) в `postgresql.conf`, чтобы он не конфликтовал с туннелем к серверу.

