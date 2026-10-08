# Настройка базы данных на сервере для разработки с разных ПК

Это руководство описывает настройку PostgreSQL на сервере и подключение к нему с разных ПК разработчиков через SSH туннель.

## Общая схема

```
[ПК 1] ──SSH туннель──> [Сервер] ──> PostgreSQL (localhost:5433)
[ПК 2] ──SSH туннель──> [Сервер] ──> PostgreSQL (localhost:5433)
```

База данных находится на сервере, каждый ПК разработчика подключается к ней через SSH туннель (как и к Redis).

**Примечание:** PostgreSQL на сервере может слушать на стандартном порту 5432 или на нестандартном (например, 5433). Проверьте порт командой `sudo pg_lsclusters` на сервере.

## Шаг 1: Установка PostgreSQL на сервере

### 1.1. Подключитесь к серверу

```bash
ssh root@your-server-ip
```

### 1.2. Установите PostgreSQL

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install postgresql postgresql-contrib

# Проверьте версию
psql --version

# Запустите службу
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

## Шаг 2: Настройка PostgreSQL на сервере

### 2.1. Создайте пользователя и базу данных

```bash
# Подключитесь к PostgreSQL как суперпользователь
sudo -u postgres psql
```

В psql выполните:

```sql
-- Создайте пользователя
CREATE USER bot_user WITH PASSWORD 'your_secure_password';

-- Создайте базу данных
CREATE DATABASE silent_couple_bot OWNER bot_user;

-- Дайте права на создание таблиц (для миграций Alembic)
ALTER USER bot_user CREATEDB;

-- Дайте все права на базу данных
GRANT ALL PRIVILEGES ON DATABASE silent_couple_bot TO bot_user;

-- Выйдите из psql
\q
```

### 2.2. Проверьте порт PostgreSQL

Проверьте, на каком порту слушает PostgreSQL:

```bash
sudo pg_lsclusters
```

Вы увидите что-то вроде:
```
Ver Cluster Port Status Owner    Data directory
14  main    5433 online postgres /var/lib/postgresql/14/main
```

Запомните номер порта (в примере это 5433).

### 2.3. Настройте PostgreSQL для работы только на localhost

Отредактируйте конфигурацию PostgreSQL (замените 14 на вашу версию):

```bash
sudo nano /etc/postgresql/14/main/postgresql.conf
```

Найдите и убедитесь, что:

```conf
listen_addresses = 'localhost'
port = 5433  # или другой порт, который показал pg_lsclusters
```

### 2.4. Настройте доступ (pg_hba.conf)

```bash
sudo nano /etc/postgresql/15/main/pg_hba.conf
```

Добавьте строки для локального доступа:

```
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             bot_user                                md5
host    all             bot_user        127.0.0.1/32            md5
```

### 2.5. Перезапустите PostgreSQL

```bash
sudo systemctl restart postgresql
```

### 2.6. Проверьте подключение на сервере

```bash
# Проверьте подключение локально на сервере (замените 5433 на ваш порт)
psql -h localhost -p 5433 -U bot_user -d silent_couple_bot
```

## Шаг 3: Настройка на каждом ПК разработчика

### 3.1. Настройте SSH ключи (если еще не настроены)

На каждом ПК выполните:

```bash
# Создайте SSH ключ (если еще нет)
ssh-keygen -t rsa -b 4096

# Скопируйте публичный ключ на сервер
ssh-copy-id root@your-server-ip

# Проверьте подключение без пароля
ssh root@your-server-ip
```

### 3.2. Настройте .env файл на каждом ПК

Скопируйте `.env` файл на каждый ПК и настройте:

**Если PostgreSQL на сервере слушает на стандартном порту 5432:**
```env
# База данных на сервере через SSH туннель
DATABASE_URL=postgresql+asyncpg://bot_user:your_secure_password@localhost:5432/silent_couple_bot

# SSH настройки для автоматического создания туннеля
DATABASE_SSH_HOST=your-server-ip
DATABASE_SSH_USER=root
DATABASE_SSH_PORT=22
```

**Если PostgreSQL на сервере слушает на нестандартном порту (например, 5433):**
```env
# База данных на сервере через SSH туннель
# Порт в DATABASE_URL должен совпадать с портом на сервере
DATABASE_URL=postgresql+asyncpg://bot_user:your_secure_password@localhost:5433/silent_couple_bot

# SSH настройки для автоматического создания туннеля
DATABASE_SSH_HOST=your-server-ip
DATABASE_SSH_USER=root
DATABASE_SSH_PORT=22
```

**Или если хотите использовать другой локальный порт:**
```env
# Локальный порт может отличаться от порта на сервере
DATABASE_URL=postgresql+asyncpg://bot_user:your_secure_password@localhost:5432/silent_couple_bot

# SSH настройки
DATABASE_SSH_HOST=your-server-ip
DATABASE_SSH_USER=root
DATABASE_SSH_PORT=22

# Порт PostgreSQL на сервере (если отличается от порта в DATABASE_URL)
DATABASE_REMOTE_PORT=5433
```

**Redis на сервере через SSH туннель:**
```env
REDIS_URL=redis://127.0.0.1:6379/0
REDIS_SSH_HOST=your-server-ip
REDIS_SSH_USER=root
REDIS_SSH_PORT=22
```

**Важно:**
- `DATABASE_URL` всегда указывает на `localhost` - туннель создается автоматически
- Порт в `DATABASE_URL` должен совпадать с портом PostgreSQL на сервере (или используйте `DATABASE_REMOTE_PORT`)
- Используйте одинаковые учетные данные БД на всех ПК
- SSH ключи должны быть настроены на каждом ПК

## Шаг 4: Перенос данных с локальной БД (если нужно)

Если у вас уже есть данные в локальной БД, перенесите их на сервер:

### 4.1. Экспорт с локальной БД

На ПК с локальной БД:

```bash
pg_dump -h localhost -U bot_user -d silent_couple_bot -F c -f silent_couple_bot_backup.dump
```

### 4.2. Импорт на сервер

**Если PostgreSQL на сервере слушает на порту 5433:**

```bash
# Создайте SSH туннель (5433:localhost:5433 - локальный:удаленный)
ssh -L 5433:localhost:5433 root@your-server-ip

# В другом терминале импортируйте данные
pg_restore -h localhost -p 5433 -U bot_user -d silent_couple_bot silent_couple_bot_backup.dump
```

Или загрузите файл на сервер:

```bash
# Загрузите файл на сервер
scp silent_couple_bot_backup.dump root@your-server-ip:/tmp/

# Подключитесь к серверу
ssh root@your-server-ip

# Импортируйте данные (замените 5433 на ваш порт)
pg_restore -h localhost -p 5433 -U bot_user -d silent_couple_bot /tmp/silent_couple_bot_backup.dump
```

## Шаг 5: Применение миграций

После настройки подключения примените миграции:

```bash
# На любом ПК разработчика
python scripts/run_migration.py
```

Скрипт автоматически создаст SSH туннель и применит миграции.

## Шаг 6: Проверка подключения

### 6.1. Проверка SSH туннеля и БД

```bash
python scripts/check_db_tunnel.py
```

Этот скрипт:
- Проверит конфигурацию SSH
- Создаст SSH туннель
- Проверит подключение к БД
- Покажет статистику БД

### 6.2. Общая проверка подключения

```bash
python scripts/check_db.py
```

## Шаг 7: Запуск бота

Бот автоматически создаст SSH туннель при запуске:

```bash
python run.py
```

В логах вы увидите:
```
SSH tunnel for PostgreSQL created automatically
```

## Как это работает

1. **При запуске бота** (`run.py`):
   - Проверяется доступность PostgreSQL на `localhost:5432`
   - Если недоступен и `DATABASE_SSH_HOST` установлен, создается SSH туннель
   - Туннель перенаправляет `localhost:5432` на `localhost:5432` на сервере
   - Бот подключается к БД через туннель

2. **При завершении бота**:
   - SSH туннель автоматически закрывается

3. **На разных ПК**:
   - Каждый ПК создает свой SSH туннель к серверу
   - Все подключаются к одной и той же БД на сервере
   - Данные синхронизированы между всеми ПК

## Устранение неполадок

### Проблема: SSH туннель не создается

**Решение:**
1. Проверьте SSH подключение: `ssh root@your-server-ip`
2. Убедитесь, что SSH ключи настроены
3. Проверьте переменные в `.env`: `DATABASE_SSH_HOST`, `DATABASE_SSH_USER`, `DATABASE_SSH_PORT`
4. Проверьте логи бота (установите `LOG_LEVEL=DEBUG`)

### Проблема: Подключение к БД не работает

**Решение:**
1. Проверьте, что PostgreSQL запущен на сервере: `sudo systemctl status postgresql`
2. Проверьте подключение на сервере: `psql -h localhost -U bot_user -d silent_couple_bot`
3. Проверьте права пользователя БД
4. Проверьте `pg_hba.conf` на сервере

### Проблема: Порт 5432 уже занят

**Решение:**
1. Проверьте, что порт свободен: `netstat -an | grep 5432` (Windows) или `lsof -i :5432` (Linux/Mac)
2. Если порт занят локальным PostgreSQL, остановите его или измените порт в `DATABASE_URL`

### Проблема: Разные ПК видят разные данные

**Решение:**
- Убедитесь, что все ПК подключаются к одному серверу
- Проверьте `DATABASE_SSH_HOST` на всех ПК
- Убедитесь, что БД действительно на сервере, а не локально на каждом ПК

## Безопасность

1. **SSH ключи** - используйте SSH ключи вместо паролей
2. **Сильные пароли** - используйте сложные пароли для пользователя БД
3. **PostgreSQL на localhost** - PostgreSQL должен слушать только на localhost сервера
4. **Firewall** - не открывайте порт 5432 для внешнего доступа
5. **Бэкапы** - регулярно делайте бэкапы БД на сервере

## Следующие шаги

После настройки:

1. ✅ Все ПК разработчиков подключены к одной БД на сервере
2. ✅ SSH туннели создаются автоматически при запуске бота
3. ✅ Данные синхронизированы между всеми ПК
4. ✅ Можно разрабатывать и тестировать на разных ПК

