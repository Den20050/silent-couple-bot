# 🚀 Быстрый деплой

## Минимальная настройка (один раз)

### 1. Настройте переменные окружения для деплоя

**Windows PowerShell:**
```powershell
$env:DEPLOY_HOST = "root@91.222.237.94"
$env:DEPLOY_PATH = "/root/Silent-Couple-Bot"
```

Или добавьте в профиль PowerShell (`notepad $PROFILE`):
```powershell
$env:DEPLOY_HOST = "root@91.222.237.94"
$env:DEPLOY_PATH = "/root/Silent-Couple-Bot"
```

### 2. Убедитесь, что на сервере настроен `.env` для production

На сервере (`ssh root@91.222.237.94`):
```bash
cd /root/Silent-Couple-Bot
nano .env
```

Убедитесь, что указаны:
```env
ENVIRONMENT=prod
WEBHOOK_URL=https://24policybot.ru/webhook/telegram
WEBHOOK_PATH=/webhook/telegram
WEBHOOK_PORT=8443
WEBHOOK_SECRET_TOKEN=your-secret-token-here
```

## Деплой (каждый раз)

### Вариант 1: Автоматический (рекомендуется)

```bash
# В Git Bash или WSL
bash deploy/deploy.sh
```

### Вариант 2: Ручной

```bash
# 1. Отправить в git
git push

# 2. На сервере
ssh root@91.222.237.94
cd /root/Silent-Couple-Bot
git pull
alembic upgrade head
sudo systemctl restart silent-couple-bot-webhook
```

## Разработка локально

```bash
# Просто запустите
python run.py
```

Бот работает в **polling** режиме - безопасно для разработки.

## Разница между окружениями

| Параметр | Локально (dev) | Сервер (prod) |
|----------|----------------|---------------|
| Режим | `polling` (`run.py`) | `webhook` (`src.entrypoints.webhook`) |
| ENVIRONMENT | `dev` | `prod` |
| WEBHOOK_URL | не указан | `https://24policybot.ru/webhook/telegram` |
| БД/Redis | через SSH туннели | прямое подключение |

Подробнее: [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)
