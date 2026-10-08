# Перенос базы данных на сервер

Это руководство описывает процесс переноса базы данных PostgreSQL с локальной машины на удаленный сервер и настройку SSH туннеля для безопасного подключения.

## Содержание

1. [Подготовка сервера](#подготовка-сервера)
2. [Настройка PostgreSQL на сервере](#настройка-postgresql-на-сервере)
3. [Экспорт данных с локальной БД](#экспорт-данных-с-локальной-бд)
4. [Импорт данных на сервер](#импорт-данных-на-сервер)
5. [Настройка SSH туннеля](#настройка-ssh-туннеля)
6. [Проверка подключения](#проверка-подключения)
7. [Применение миграций](#применение-миграций)
8. [Устранение неполадок](#устранение-неполадок)

## Подготовка сервера

### Требования

- Ubuntu/Debian сервер с доступом по SSH
- PostgreSQL 12+ установлен и запущен
- Права root или sudo для настройки PostgreSQL

### Установка PostgreSQL (если не установлен)

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install postgresql postgresql-contrib

# Проверка версии
psql --version

# Запуск службы
sudo systemctl start postgresql
sudo systemctl enable postgresql
```

## Настройка PostgreSQL на сервере

### 1. Создание пользователя и базы данных

```bash
# Подключитесь к PostgreSQL как суперпользователь
sudo -u postgres psql

# В psql выполните:
CREATE USER bot_user WITH PASSWORD 'your_secure_password';
CREATE DATABASE silent_couple_bot OWNER bot_user;
GRANT ALL PRIVILEGES ON DATABASE silent_couple_bot TO bot_user;

# Для работы с таблицами (если Alembic создает таблицы)
ALTER USER bot_user CREATEDB;

# Выйдите из psql
\q
```

### 2. Настройка PostgreSQL для локального доступа

Отредактируйте `/etc/postgresql/<version>/main/postgresql.conf`:

```bash
sudo nano /etc/postgresql/15/main/postgresql.conf
```

Найдите и раскомментируйте/измените:

```conf
# Слушать только на localhost (безопаснее)
listen_addresses = 'localhost'

# Порт (по умолчанию 5432)
port = 5432
```

### 3. Настройка доступа (pg_hba.conf)

Отредактируйте `/etc/postgresql/<version>/main/pg_hba.conf`:

```bash
sudo nano /etc/postgresql/15/main/pg_hba.conf
```

Добавьте строку для локального доступа:

```
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             bot_user                                md5
host    all             bot_user        127.0.0.1/32            md5
```

### 4. Перезапуск PostgreSQL

```bash
sudo systemctl restart postgresql
```

### 5. Проверка подключения на сервере

```bash
# Проверьте подключение локально на сервере
psql -h localhost -U bot_user -d silent_couple_bot
```

## Экспорт данных с локальной БД

### 1. Экспорт структуры и данных

```bash
# С локальной машины экспортируйте БД
pg_dump -h localhost -U bot_user -d silent_couple_bot -F c -f silent_couple_bot_backup.dump

# Или в SQL формат (для просмотра)
pg_dump -h localhost -U bot_user -d silent_couple_bot -f silent_couple_bot_backup.sql
```

### 2. Экспорт только структуры (без данных)

```bash
pg_dump -h localhost -U bot_user -d silent_couple_bot --schema-only -f schema_only.sql
```

### 3. Экспорт только данных (без структуры)

```bash
pg_dump -h localhost -U bot_user -d silent_couple_bot --data-only -f data_only.sql
```

## Импорт данных на сервер

### Вариант 1: Через SSH туннель

```bash
# Создайте SSH туннель
ssh -L 5433:localhost:5432 root@your-server-ip

# В другом терминале импортируйте данные
pg_restore -h localhost -p 5433 -U bot_user -d silent_couple_bot silent_couple_bot_backup.dump
```

### Вариант 2: Прямая передача через SSH

```bash
# Экспорт и передача через SSH одной командой
pg_dump -h localhost -U bot_user -d silent_couple_bot -F c | \
  ssh root@your-server-ip "pg_restore -h localhost -U bot_user -d silent_couple_bot"
```

### Вариант 3: Загрузка файла на сервер

```bash
# Загрузите файл на сервер
scp silent_couple_bot_backup.dump root@your-server-ip:/tmp/

# Подключитесь к серверу
ssh root@your-server-ip

# Импортируйте данные
pg_restore -h localhost -U bot_user -d silent_couple_bot /tmp/silent_couple_bot_backup.dump
```

## Настройка SSH туннеля

### 1. Настройка SSH ключей (рекомендуется)

```bash
# На локальной машине создайте SSH ключ (если еще нет)
ssh-keygen -t rsa -b 4096 -C "your_email@example.com"

# Скопируйте публичный ключ на сервер
ssh-copy-id root@your-server-ip

# Проверьте подключение без пароля
ssh root@your-server-ip
```

### 2. Настройка переменных окружения

Отредактируйте `.env` файл:

```env
# База данных через SSH туннель
DATABASE_URL=postgresql+asyncpg://bot_user:your_secure_password@localhost:5432/silent_couple_bot

# SSH настройки для автоматического создания туннеля
DATABASE_SSH_HOST=your-server-ip
DATABASE_SSH_USER=root
DATABASE_SSH_PORT=22
```

### 3. Автоматическое создание туннеля

Бот автоматически создаст SSH туннель при запуске, если:
- `DATABASE_SSH_HOST` установлен в `.env`
- PostgreSQL недоступен локально
- SSH ключи настроены для автоматического подключения

## Проверка подключения

### 1. Проверка подключения с SSH туннелем

```bash
# Используйте специальный скрипт для проверки туннеля
python scripts/check_db_tunnel.py
```

Этот скрипт:
- Проверяет конфигурацию SSH
- Создает SSH туннель
- Проверяет подключение к БД через туннель
- Показывает статистику БД

### 2. Проверка подключения (общий скрипт)

```bash
# Общий скрипт проверки (автоматически использует туннель если нужно)
python scripts/check_db.py
```

### 3. Ручная проверка SSH туннеля

```bash
# Создайте туннель вручную
ssh -N -L 5432:localhost:5432 root@your-server-ip

# В другом терминале проверьте подключение
psql -h localhost -U bot_user -d silent_couple_bot
```

## Применение миграций

После переноса данных на сервер, убедитесь, что миграции применены:

```bash
# Проверьте текущую версию миграций
python scripts/check_migration_status.py

# Примените миграции (если нужно)
alembic upgrade head

# Или используйте скрипт
python scripts/run_migration.py
```

## Устранение неполадок

### Проблема: SSH туннель не создается

**Решение:**
1. Проверьте SSH подключение: `ssh root@your-server-ip`
2. Убедитесь, что SSH ключи настроены
3. Проверьте переменные окружения: `DATABASE_SSH_HOST`, `DATABASE_SSH_USER`, `DATABASE_SSH_PORT`
4. Проверьте логи бота (установите `LOG_LEVEL=DEBUG` в `.env`)

### Проблема: Подключение к БД не работает через туннель

**Решение:**
1. Проверьте, что PostgreSQL запущен на сервере: `sudo systemctl status postgresql`
2. Проверьте, что PostgreSQL слушает на localhost: `sudo netstat -tlnp | grep 5432`
3. Проверьте права пользователя: `psql -h localhost -U bot_user -d silent_couple_bot`
4. Проверьте `pg_hba.conf` на сервере

### Проблема: Порт уже занят

**Решение:**
1. Проверьте, что порт 5432 свободен: `netstat -an | grep 5432` (Windows) или `lsof -i :5432` (Linux/Mac)
2. Если порт занят другим процессом, остановите его или измените порт в `DATABASE_URL`

### Проблема: Миграции не применяются

**Решение:**
1. Проверьте версию Alembic: `python scripts/check_migration_status.py`
2. Убедитесь, что пользователь БД имеет права на создание таблиц
3. Проверьте логи миграций: `alembic current` и `alembic history`

### Проблема: Данные не импортировались

**Решение:**
1. Проверьте права пользователя: `GRANT ALL PRIVILEGES ON DATABASE silent_couple_bot TO bot_user;`
2. Проверьте, что база данных существует: `psql -h localhost -U bot_user -l`
3. Попробуйте импортировать снова с флагом `--clean`: `pg_restore --clean -h localhost -U bot_user -d silent_couple_bot backup.dump`

## Безопасность

### Рекомендации

1. **Используйте SSH ключи** вместо паролей для SSH подключения
2. **Ограничьте доступ к PostgreSQL** - слушайте только на localhost
3. **Используйте сильные пароли** для пользователя БД
4. **Регулярно делайте бэкапы** БД
5. **Не храните пароли в git** - используйте `.env` файл и добавьте его в `.gitignore`

### Настройка firewall

```bash
# На сервере настройте firewall (если используется)
sudo ufw allow 22/tcp  # SSH
# НЕ открывайте порт 5432 для внешнего доступа!
```

## Дополнительные ресурсы

- [Документация PostgreSQL](https://www.postgresql.org/docs/)
- [Документация SSH туннелей](https://www.ssh.com/academy/ssh/tunneling)
- [Документация Alembic](https://alembic.sqlalchemy.org/)

## Следующие шаги

После успешного переноса БД:

1. Обновите `.env` файл на всех машинах разработки
2. Протестируйте подключение с разных машин
3. Настройте автоматические бэкапы БД
4. Документируйте процесс для команды

