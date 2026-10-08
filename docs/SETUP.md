# Инструкция по настройке проекта

## Шаг 1: Проверка PostgreSQL

Убедитесь, что PostgreSQL запущен и доступен:

```bash
# Проверьте, что PostgreSQL запущен
# Windows: проверьте в службах Windows
# Или через командную строку:
sc query postgresql-x64-15

# Или попробуйте подключиться через psql:
psql -h localhost -p 5433 -U user -d silent_couple_bot
```

## Шаг 2: Проверка подключения

Запустите скрипт проверки:

```bash
python scripts/check_db.py
```

Если подключение не удается:

1. **Проверьте, что PostgreSQL запущен**
   - Windows: Панель управления → Службы → найдите PostgreSQL
   - Или запустите через командную строку

2. **Проверьте параметры в .env**
   ```env
   DATABASE_URL=postgresql+asyncpg://user:password@localhost:5433/silent_couple_bot
   ```
   
   Убедитесь, что:
   - `user` - правильное имя пользователя
   - `password` - правильный пароль
   - `localhost:5433` - правильный хост и порт (5433 вместо стандартного 5432)
   - `silent_couple_bot` - имя базы данных (без опечаток)

3. **Проверьте права доступа**
   - Убедитесь, что пользователь имеет права на создание таблиц в БД

## Шаг 3: Создание миграций

После успешного подключения:

```bash
# Создайте первую миграцию
alembic revision --autogenerate -m "Initial migration"

# Примените миграции
alembic upgrade head
```

## Шаг 4: Загрузка картинок

```bash
# Получите ваш Telegram chat_id (отправьте сообщение @userinfobot)
# Загрузите картинки
python scripts/load_images.py <your_telegram_chat_id>
```

## Шаг 5: Запуск приложения

**Вариант 1: Единая точка входа (рекомендуется)**

```bash
# Запускает и бота, и worker одновременно
python run.py

# В отдельном терминале (опционально): Mini App
uvicorn src.mini_app.main:app --host 0.0.0.0 --port 8000
```

**Вариант 2: Раздельный запуск (для отладки)**

В разных терминалах:

```bash
# Терминал 1: Bot
python -m src.bot.main

# Терминал 2: Worker
python -m src.worker.main

# Терминал 3: Mini App
uvicorn src.mini_app.main:app --host 0.0.0.0 --port 8000
```

## Решение проблем

### Ошибка подключения к БД

1. Проверьте, что PostgreSQL запущен
2. Проверьте порт (5433 в вашем случае)
3. Проверьте имя пользователя и пароль
4. Убедитесь, что БД `silent_couple_bot` существует

### Ошибка при создании миграций

Если async режим не работает, попробуйте использовать sync режим:
- Измените `DATABASE_URL` в `.env`, убрав `+asyncpg`:
  ```
  DATABASE_URL=postgresql://user:password@localhost:5433/silent_couple_bot
  ```

### Ошибка при загрузке картинок

1. Убедитесь, что бот запущен и может отправлять вам сообщения
2. Начните диалог с ботом командой `/start`
3. Проверьте, что путь к картинкам правильный: `C:\Silent-Couple-Bot\image`

