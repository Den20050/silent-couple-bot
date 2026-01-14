# Docker Guide для Silent Couple Bot

## Обзор

Проект поддерживает несколько вариантов запуска с Docker:

1. **Инфраструктура только** (`docker-compose.yml`) - PostgreSQL, Redis, MinIO
2. **Полное локальное окружение** (`docker-compose.dev.yml`) - инфраструктура + приложение
3. **Продакшн** (`docker-compose.prod.yml`) - только приложение (БД на удаленном сервере)

## Быстрый старт

### Вариант 1: Инфраструктура в Docker, приложение локально (рекомендуется для разработки)

```bash
# Запустить только инфраструктуру
docker-compose up -d

# Применить миграции
alembic upgrade head

# Запустить приложение локально
python run.py
```

### Вариант 2: Полное окружение в Docker (для тестирования)

```bash
# Создать .env файл с настройками
cp env.example .env
# Отредактируйте .env, установите TG_BOT_TOKEN

# Запустить все сервисы
docker-compose -f docker-compose.dev.yml up -d

# Применить миграции (внутри контейнера или локально)
docker-compose -f docker-compose.dev.yml exec postgres psql -U postgres -d silent_couple_bot
# или локально:
alembic upgrade head

# Раскомментируйте команды в docker-compose.dev.yml для запуска bot/worker
# или запустите локально с подключением к Docker сервисам
```

### Вариант 3: Продакшн деплой

```bash
# Создать .env файл с продакшн настройками
cp env.example .env
# Настройте DATABASE_URL, REDIS_URL для удаленного сервера

# Собрать образы
docker-compose -f docker-compose.prod.yml build

# Запустить сервисы
docker-compose -f docker-compose.prod.yml up -d

# Проверить статус
docker-compose -f docker-compose.prod.yml ps

# Просмотр логов
docker-compose -f docker-compose.prod.yml logs -f bot
docker-compose -f docker-compose.prod.yml logs -f worker
```

## Структура Dockerfile

Dockerfile использует multi-stage сборку:

- **base** - базовый образ с зависимостями
- **bot** - образ для бота
- **worker** - образ для worker
- **combined** - образ для запуска bot + worker вместе

## Переменные окружения

Все переменные из `.env` передаются в контейнеры через `env_file`.

**Важно для Docker:**
- `DATABASE_URL` должен указывать на имя сервиса в docker-compose (например, `postgres:5432`)
- `REDIS_URL` должен указывать на имя сервиса в docker-compose (например, `redis:6379`)
- Для продакшна используйте реальные адреса удаленных серверов

## Разработка с Docker

### Hot Reload (разработка)

В `docker-compose.dev.yml` код монтируется как volume:

```yaml
volumes:
  - .:/app
```

Изменения в коде будут сразу видны в контейнере.

### Отладка

```bash
# Войти в контейнер
docker-compose -f docker-compose.dev.yml exec bot bash

# Запустить Python с отладчиком
docker-compose -f docker-compose.dev.yml exec bot python -m pdb -m src.entrypoints.bot
```

### Логи

```bash
# Все логи
docker-compose logs -f

# Только bot
docker-compose logs -f bot

# Только worker
docker-compose logs -f worker

# Последние 100 строк
docker-compose logs --tail=100 bot
```

## Продакшн деплой

### Подготовка

1. Создайте `.env` файл с продакшн настройками
2. Убедитесь, что PostgreSQL и Redis доступны (через SSH туннель или напрямую)
3. Примените миграции: `alembic upgrade head`

### Запуск

```bash
# Собрать образы
docker-compose -f docker-compose.prod.yml build

# Запустить в фоне
docker-compose -f docker-compose.prod.yml up -d

# Проверить статус
docker-compose -f docker-compose.prod.yml ps
```

### Обновление

```bash
# Остановить сервисы
docker-compose -f docker-compose.prod.yml down

# Обновить код
git pull

# Пересобрать образы
docker-compose -f docker-compose.prod.yml build

# Запустить снова
docker-compose -f docker-compose.prod.yml up -d
```

### Мониторинг

```bash
# Использование ресурсов
docker stats

# Health checks
docker-compose -f docker-compose.prod.yml ps

# Логи
docker-compose -f docker-compose.prod.yml logs -f --tail=100
```

## Troubleshooting

### Контейнер не запускается

```bash
# Проверить логи
docker-compose logs bot

# Проверить переменные окружения
docker-compose exec bot env | grep DATABASE_URL
```

### Проблемы с подключением к БД

1. Убедитесь, что PostgreSQL запущен: `docker-compose ps`
2. Проверьте `DATABASE_URL` в `.env`
3. Для Docker используйте имя сервиса: `postgres:5432`
4. Для продакшна проверьте SSH туннель или прямой доступ

### Проблемы с Redis

1. Убедитесь, что Redis запущен: `docker-compose ps redis`
2. Проверьте `REDIS_URL` в `.env`
3. Для Docker используйте имя сервиса: `redis:6379`

### Пересборка образов

```bash
# Пересобрать без кеша
docker-compose build --no-cache

# Пересобрать конкретный сервис
docker-compose build bot
```

## Best Practices

1. **Разработка**: Используйте `docker-compose.yml` для инфраструктуры, запускайте приложение локально
2. **Тестирование**: Используйте `docker-compose.dev.yml` для полного окружения
3. **Продакшн**: Используйте `docker-compose.prod.yml` с продакшн настройками
4. **Безопасность**: Никогда не коммитьте `.env` файл с реальными токенами
5. **Резервное копирование**: Настройте регулярные бэкапы БД и Redis

## Альтернативы

Если Docker не подходит для разработки, можно использовать:
- Локальный PostgreSQL/Redis (установленные напрямую)
- Удаленный сервер через SSH туннель (текущий подход)
- Docker только для инфраструктуры, приложение локально (рекомендуется)

