# Silent Couple Bot 3.0

Telegram-бот для пар с ежедневным обменом картинками «Доброе утро» / «Спокойной ночи».

## Технологический стек

- **Bot**: Python 3.11, aiogram 3, uvloop
- **Background**: arq (Redis) для cron-задач
- **Mini App**: FastAPI + static
- **БД**: PostgreSQL 15, SQLAlchemy 2.0, asyncpg
- **Migrations**: Alembic
- **Cache/Queue**: Redis 7
- **Object Storage**: MinIO (S3)
- **Monitoring**: Prometheus + Grafana + Loki (планируется)

## Структура проекта

```
silent_couple_bot/
├── src/
│   ├── entrypoints/   # Точки входа (bot, worker)
│   ├── bot/           # aiogram handlers, middlewares, validators
│   ├── worker/        # arq cron jobs, tasks, services
│   ├── mini_app/      # FastAPI + static
│   ├── db/            # SQLAlchemy models, repositories
│   ├── domain/        # Domain services (чистая бизнес-логика)
│   ├── services/      # Application services, messaging, telegram, payment
│   └── core/          # config, constants, logger, DI, protocols
├── tests/
├── scripts/           # load_images, daily_backup
├── alembic/           # Database migrations
├── docker-compose.yml
├── run.py             # Единая точка входа (bot + worker)
└── alembic.ini
```

## Быстрый старт

### 1. Требования

- Python 3.11+
- Docker и Docker Compose
- Telegram Bot Token (от @BotFather)
- YooKassa аккаунт (для платежей)

### 2. Клонирование и установка зависимостей

```bash
# Клонируйте репозиторий
git clone <repository-url>
cd Silent-Couple-Bot

# Создайте виртуальное окружение
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установите зависимости
pip install -r requirements.txt
```

### 3. Настройка переменных окружения

```bash
# Скопируйте пример конфигурации
cp .env.example .env

# Отредактируйте .env и заполните:
# - TG_BOT_TOKEN (токен от @BotFather)
# - DATABASE_URL (строка подключения к PostgreSQL)
# - DATABASE_SSH_HOST (IP сервера с БД, если БД на сервере)
# - REDIS_SSH_HOST (IP сервера с Redis, если Redis на сервере)
# - Остальные параметры можно оставить по умолчанию
```

### 4. Выбор варианта развертывания

**Вариант А: Локальная разработка (один ПК)**

```bash
# Запустите PostgreSQL, Redis и MinIO локально
docker-compose up -d

# Проверьте, что все сервисы запущены
docker-compose ps
```

**Вариант Б: Разработка с разных ПК (БД и Redis на сервере)**

База данных и Redis должны быть установлены на сервере. Бот автоматически создаст SSH туннели при запуске.

1. Установите PostgreSQL и Redis на сервере (см. [DATABASE_SERVER_SETUP.md](DATABASE_SERVER_SETUP.md))
2. Настройте `.env` на каждом ПК:
   ```env
   DATABASE_URL=postgresql+asyncpg://bot_user:password@localhost:5432/silent_couple_bot
   DATABASE_SSH_HOST=your-server-ip
   DATABASE_SSH_USER=root
   DATABASE_SSH_PORT=22
   
   REDIS_URL=redis://127.0.0.1:6379/0
   REDIS_SSH_HOST=your-server-ip
   REDIS_SSH_USER=root
   REDIS_SSH_PORT=22
   ```
3. Настройте SSH ключи на каждом ПК для автоматического подключения

### 5. Настройка базы данных

```bash
# Примените миграции (скрипт автоматически создаст SSH туннель если нужно)
python scripts/run_migration.py

# Или используйте alembic напрямую
alembic upgrade head
```

### 6. Загрузка картинок

```bash
# Получите ваш Telegram chat_id (отправьте сообщение @userinfobot)
# Загрузите картинки из папки image/ в Telegram и сохраните file_id в БД
python scripts/load_images.py <your_telegram_chat_id>
```

**Важно**: Скрипт отправляет картинки в ваш Saved Messages для получения file_id. 
Убедитесь, что бот может отправлять вам сообщения.

### 7. Запуск приложения

**Вариант 1: Единая точка входа (рекомендуется)**

```bash
# Запускает и бота, и worker одновременно
python run.py

# В отдельном терминале (опционально): Mini App (FastAPI)
uvicorn src.mini_app.main:app --host 0.0.0.0 --port 8000
```

**Вариант 2: Раздельный запуск (для отладки)**

В разных терминалах запустите:

```bash
# Терминал 1: Bot
python -m src.entrypoints.bot

# Терминал 2: Worker (cron jobs)
python -m src.entrypoints.worker

# Терминал 3: Mini App (FastAPI)
uvicorn src.mini_app.main:app --host 0.0.0.0 --port 8000
```

## Разработка

### Структура кода

- **`src/entrypoints/`** — точки входа (`bot.py`, `worker.py`)
- **`src/bot/`** — обработчики команд и callback'ов бота, middlewares, validators
- **`src/worker/`** — фоновые задачи (cron jobs через arq), tasks, services
- **`src/mini_app/`** — FastAPI приложение для Telegram Mini App
- **`src/db/`** — модели БД и репозитории (DAL pattern)
- **`src/domain/services/`** — чистая бизнес-логика (domain services)
- **`src/services/application/`** — application services (оркестрация бизнес-операций)
- **`src/services/messaging/`** — сервисы для отправки сообщений и UI
- **`src/services/telegram/`** — интеграция с Telegram API
- **`src/services/payment/`** — интеграция с платежными системами
- **`src/core/`** — конфигурация, логирование, константы, DI, протоколы

### Создание миграций

```bash
# Автогенерация миграции на основе изменений моделей
alembic revision --autogenerate -m "Description of changes"

# Применить миграции
alembic upgrade head

# Откатить последнюю миграцию
alembic downgrade -1
```

### Тестирование

```bash
# Запуск тестов
pytest

# С покрытием
pytest --cov=src --cov-report=html
```

### Форматирование кода

```bash
# Форматирование с black
black src/

# Сортировка импортов
isort src/

# Проверка типов
mypy src/
```

## Команды бота

- `/start` — начало работы, онбординг, выбор режима
- `/pay` — оплата подписки
- `/delete` — удаление всех данных (GDPR)
- `/link` — привязка общего чата (только для Chat Mode)

## Режимы работы

### Silent Mode (по умолчанию)
- Общение через изолированный чат с ботом
- Бот отправляет запрос → пользователь нажимает кнопку → партнёр получает картинку

### Chat Mode
- Интеграция в личный чат пары через Telegram Mini App
- Картинки отправляются напрямую в общий чат

## Архитектура

Проект следует принципам **SOLID** и **SoC (Separation of Concerns)** для обеспечения поддерживаемости и тестируемости.

### Архитектурные слои

1. **Entry Points** (`src/entrypoints/`) — точки входа (bot, worker)
2. **Bot Layer** (`src/bot/`) — handlers, middlewares, validators
3. **Application Services** (`src/services/application/`) — оркестрация бизнес-операций
4. **Domain Services** (`src/domain/services/`) — чистая бизнес-логика
5. **Infrastructure** (`src/db/repositories/`, `src/services/`) — доступ к данным и внешним сервисам

### Dependency Injection

- Используются протоколы (`MessengerProtocol`, `PaymentServiceProtocol`) для DI
- Container управляет зависимостями через `src/core/di/container.py`
- Middlewares внедряют зависимости в handlers

### Структура handlers

Каждый handler организован как пакет:
```
handlers/{handler_name}/
├── router.py              # Регистрация роутера
├── handlers/              # Обработчики событий (тонкие контроллеры)
├── use_cases/             # Use cases (бизнес-операции)
└── validators.py          # Валидация
```

**Подробнее**: См. [ARCHITECTURE.md](ARCHITECTURE.md) и [CONTRIBUTING.md](CONTRIBUTING.md)

### База данных

- **users** — пользователи (tg_id, consent, utc_offset)
- **pairs** — пары (uid_a, uid_b, mode, status)
- **daily_state** — состояние дня (pair_id, day, morning/evening initiator)
- **subscriptions** — подписки (pair_id, payer_id, period_end)
- **user_demo** — блок-лист демо (защита от повторного использования)
- **pics_pool** — пул картинок (file_id, type)

### Фоновые задачи (Worker)

- **morning_sender** — отправка утренних картинок (07:00-08:00 UTC)
- **evening_sender** — отправка вечерних картинок (21:00-22:00 UTC)
- **cleanup_old_data** — очистка старых данных (03:00 UTC)
- **dunning_notifications** — напоминания о просрочке (10:00 UTC)

## Безопасность

- Rate limiting на уровне бота (middleware)
- Проверка подписи Telegram initData для Mini App
- Circuit breaker для YooKassa API
- GDPR compliance: право на удаление данных

## Мониторинг

- Структурированное логирование (structlog → JSON)
- Prometheus метрики (планируется)
- Grafana дашборды (планируется)

## Деплой

### 🚀 Быстрый старт

**Для разработки и production:** См. [QUICK_DEPLOY.md](QUICK_DEPLOY.md) - минимальная инструкция по деплою.

**Подробная документация:** См. [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - полный гайд по деплою и разработке.

### Локальная разработка

**Рекомендуемый подход**: Используйте `docker-compose.yml` для запуска инфраструктуры (PostgreSQL, Redis, MinIO), а приложение запускайте локально:

```bash
# Запустить инфраструктуру
docker-compose up -d

# Запустить приложение локально (polling режим)
python run.py
```

**Альтернатива**: Полное окружение в Docker (см. [DOCKER.md](DOCKER.md)):
```bash
docker-compose -f docker-compose.dev.yml up -d
```

### Production

**Вариант 1: Systemd + Webhook (рекомендуется, минимальный)**

1. Настройте `.env` на сервере с `WEBHOOK_URL`
2. Примените миграции: `alembic upgrade head`
3. Запустите через systemd: `systemctl start silent-couple-bot-webhook`

**Быстрый деплой:**
```bash
bash deploy/deploy.sh  # Автоматический деплой через git
```

**Вариант 2: Docker**

1. Настройте переменные окружения в `.env` файле
2. Примените миграции: `alembic upgrade head`
3. Соберите и запустите контейнеры:
   ```bash
   docker-compose -f docker-compose.prod.yml build
   docker-compose -f docker-compose.prod.yml up -d
   ```

**Общее для обоих вариантов:**

- Настройте reverse proxy (nginx) для webhook
- Настройте webhook для Telegram Bot API
- Настройте мониторинг и логирование

Подробнее:
- [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md) - полный гайд по деплою
- [QUICK_DEPLOY.md](QUICK_DEPLOY.md) - быстрая инструкция
- [WEBHOOK_DEPLOYMENT.md](WEBHOOK_DEPLOYMENT.md) - настройка webhook
- [DOCKER.md](DOCKER.md) - Docker деплой

## Лицензия

MIT

## Контакты

- Admin: @your_admin
- Updates: @silent_couple_3_news
- Status: status.bot-domain.ru
