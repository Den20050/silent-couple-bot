# Минимальный гайд по деплою и разработке

## 🎯 Цель

Задеплоить бота на сервер для production, но продолжать разрабатывать локально.

## 📋 Быстрая настройка

### 1. Локальная разработка (Windows)

**Настройки `.env` для разработки:**

```env
# Режим разработки
ENVIRONMENT=dev

# Polling режим (по умолчанию, webhook не нужен)
# WEBHOOK_URL не указываем или закомментирован

# Подключение к БД/Redis на сервере через SSH туннели
DATABASE_URL=postgresql+asyncpg://bot_user:password@localhost:5432/silent_couple_bot
DATABASE_SSH_HOST=91.222.237.94
DATABASE_SSH_USER=root
DATABASE_SSH_PORT=22

REDIS_URL=redis://127.0.0.1:6379/0
REDIS_SSH_HOST=91.222.237.94
REDIS_SSH_USER=root
REDIS_SSH_PORT=22
```

**Запуск локально:**

```bash
python run.py
```

Бот работает в режиме **polling** - периодически запрашивает обновления у Telegram API.

### 2. Production на сервере

**Настройки `.env` на сервере:**

```env
# Режим production
ENVIRONMENT=prod

# Webhook режим (обязательно для production)
WEBHOOK_URL=https://24policybot.ru/webhook/telegram
WEBHOOK_PATH=/webhook/telegram
WEBHOOK_PORT=8443
WEBHOOK_SECRET_TOKEN=your-secret-token-here  # Сгенерируйте: openssl rand -hex 32

# Прямое подключение к БД/Redis (без SSH туннелей, т.к. на том же сервере)
DATABASE_URL=postgresql+asyncpg://bot_user:password@localhost:5432/silent_couple_bot
# DATABASE_SSH_HOST не указываем (закомментировано)

REDIS_URL=redis://127.0.0.1:6379/0
# REDIS_SSH_HOST не указываем (закомментировано)
```

**Запуск на сервере:**

```bash
# Через systemd (автозапуск)
sudo systemctl start silent-couple-bot-webhook
sudo systemctl enable silent-couple-bot-webhook

# Или вручную для тестирования
python -m src.entrypoints.webhook
```

## 🚀 Процесс деплоя

### Вариант 1: Автоматический деплой (рекомендуется)

**Настройка один раз:**

```bash
# На Windows (PowerShell)
$env:DEPLOY_HOST = "root@91.222.237.94"
$env:DEPLOY_PATH = "/root/Silent-Couple-Bot"  # опционально

# Или добавьте в профиль PowerShell:
# notepad $PROFILE
# Добавьте строки:
# $env:DEPLOY_HOST = "root@91.222.237.94"
# $env:DEPLOY_PATH = "/root/Silent-Couple-Bot"
```

**Деплой:**

```bash
# На Windows через Git Bash или WSL
bash deploy/deploy.sh

# Или через PowerShell (если установлен Git Bash)
& "C:\Program Files\Git\bin\bash.exe" deploy/deploy.sh
```

Скрипт автоматически:
1. ✅ Проверит локальные изменения
2. ✅ Отправит код в git (если есть изменения)
3. ✅ Обновит код на сервере (`git pull`)
4. ✅ Установит зависимости
5. ✅ Применит миграции БД
6. ✅ Перезапустит сервис

### Вариант 2: Ручной деплой

```bash
# 1. Отправить изменения в git
git add .
git commit -m "feat: описание изменений"
git push

# 2. Подключиться к серверу
ssh root@91.222.237.94

# 3. На сервере: обновить код
cd /root/Silent-Couple-Bot
git pull

# 4. Установить зависимости (если нужно)
pip3 install -r requirements.txt

# 5. Применить миграции
alembic upgrade head

# 6. Перезапустить сервис
sudo systemctl restart silent-couple-bot-webhook

# 7. Проверить статус
sudo systemctl status silent-couple-bot-webhook
```

## 📁 Структура файлов

```
Silent-Couple-Bot/
├── .env                    # Локальный .env (НЕ коммитить в git!)
├── .env.production         # Пример продакшн .env (можно коммитить)
├── deploy/
│   ├── deploy.sh          # Скрипт автоматического деплоя
│   └── webhook.service    # Systemd service файл
└── DEPLOYMENT_GUIDE.md    # Этот файл
```

## 🔄 Типичный workflow

### Разработка новой фичи:

```bash
# 1. Локально: создайте ветку
git checkout -b feature/new-feature

# 2. Разрабатывайте локально
python run.py  # Запуск в polling режиме

# 3. Тестируйте локально
# ... тесты ...

# 4. Закоммитьте изменения
git add .
git commit -m "feat: новая фича"

# 5. Отправить в git
git push origin feature/new-feature

# 6. Создать PR и смержить в main
# (или смержить локально: git checkout main && git merge feature/new-feature)
```

### Деплой на production:

```bash
# После мерджа в main:

# Вариант 1: Автоматический
bash deploy/deploy.sh

# Вариант 2: Ручной
git push  # если еще не отправили
ssh root@91.222.237.94
cd /root/Silent-Couple-Bot
git pull
alembic upgrade head
sudo systemctl restart silent-couple-bot-webhook
```

## 🔍 Проверка работы

### Локально (polling):

```bash
# Запуск
python run.py

# Логи в консоли
# Бот должен отвечать на команды в Telegram
```

### На сервере (webhook):

```bash
# Проверка статуса сервиса
ssh root@91.222.237.94
sudo systemctl status silent-couple-bot-webhook

# Просмотр логов
sudo journalctl -u silent-couple-bot-webhook -f

# Проверка health endpoint
curl https://24policybot.ru/health

# Проверка webhook в Telegram
curl "https://api.telegram.org/bot${TG_BOT_TOKEN}/getWebhookInfo"
```

## ⚠️ Важные моменты

### 1. Разные `.env` файлы

- **Локально**: `.env` с `ENVIRONMENT=dev`, без `WEBHOOK_URL`
- **На сервере**: `.env` с `ENVIRONMENT=prod`, с `WEBHOOK_URL`

**Важно:** `.env` файлы НЕ коммитятся в git (уже в `.gitignore`)

### 2. Разные режимы работы

- **Локально**: `run.py` → polling режим
- **На сервере**: `python -m src.entrypoints.webhook` → webhook режим

### 3. Миграции БД

Миграции применяются **на сервере** после деплоя:
```bash
alembic upgrade head
```

### 4. Перезапуск сервиса

После деплоя обязательно перезапустите сервис:
```bash
sudo systemctl restart silent-couple-bot-webhook
```

## 🐛 Troubleshooting

### Бот не отвечает после деплоя

1. **Проверьте логи:**
   ```bash
   ssh root@91.222.237.94
   sudo journalctl -u silent-couple-bot-webhook -n 50
   ```

2. **Проверьте webhook:**
   ```bash
   curl "https://api.telegram.org/bot${TG_BOT_TOKEN}/getWebhookInfo"
   ```

3. **Проверьте статус сервиса:**
   ```bash
   sudo systemctl status silent-couple-bot-webhook
   ```

### Ошибки подключения к БД/Redis

- **Локально**: Проверьте SSH туннели (создаются автоматически)
- **На сервере**: Проверьте, что PostgreSQL и Redis запущены:
  ```bash
  sudo systemctl status postgresql
  sudo systemctl status redis
  ```

### Миграции не применяются

```bash
# Проверьте текущую версию
alembic current

# Примените миграции вручную
alembic upgrade head

# Если ошибка - проверьте подключение к БД
```

## 📝 Чеклист перед деплоем

- [ ] Код протестирован локально
- [ ] Изменения закоммичены в git
- [ ] `.env` на сервере настроен правильно (WEBHOOK_URL и т.д.)
- [ ] Миграции БД готовы (если есть изменения схемы)
- [ ] Зависимости обновлены в `requirements.txt` (если нужно)

## 🎉 Готово!

Теперь у вас:
- ✅ Локальная разработка в polling режиме
- ✅ Production на сервере в webhook режиме
- ✅ Простой процесс деплоя через git

**Совет:** Используйте автоматический деплой (`deploy/deploy.sh`) - это быстрее и надежнее!
