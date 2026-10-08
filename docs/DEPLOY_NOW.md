# 🚀 Быстрое развертывание на сервере - ПРЯМО СЕЙЧАС

## Выполните эти команды на сервере:

### 1. Клонируйте проект

```bash
cd /root
git clone git@github.com:Den20050/silent-couple-bot.git
cd silent-couple-bot
```

**Если SSH ключ для GitHub не настроен на сервере:**
```bash
git clone https://github.com/Den20050/silent-couple-bot.git
cd silent-couple-bot
```

### 2. Создайте .env файл

```bash
cp env.example .env
nano .env
```

**ВАЖНО:** Скопируйте настройки из вашего локального `.env`, но:
- ❌ УДАЛИТЕ строки с `DATABASE_SSH_HOST`, `DATABASE_SSH_USER`, `DATABASE_SSH_PORT`
- ❌ УДАЛИТЕ строки с `REDIS_SSH_HOST`, `REDIS_SSH_USER`, `REDIS_SSH_PORT`
- ✅ Используйте `localhost` для БД и Redis
- ✅ Добавьте `WEBHOOK_URL`, `WEBHOOK_PATH`, `WEBHOOK_PORT`, `WEBHOOK_SECRET_TOKEN`

**Сгенерируйте токен для webhook:**
```bash
openssl rand -hex 32
```

### 3. Установите зависимости

```bash
pip3 install -r requirements.txt
pip3 install uvicorn[standard]
```

### 4. Проверьте/обновите Nginx конфигурацию

```bash
sudo nano /etc/nginx/sites-available/24policybot.ru
```

Убедитесь, что есть блок для `/webhook/robokassa`:

```nginx
location /webhook/robokassa {
    proxy_pass http://127.0.0.1:8443;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;
}
```

Проверьте и перезагрузите:
```bash
sudo nginx -t
sudo systemctl reload nginx
```

### 5. Создайте и запустите systemd service

```bash
cd /root/silent-couple-bot
sudo cp deploy/webhook.service /etc/systemd/system/silent-couple-bot-webhook.service
sudo systemctl daemon-reload
sudo systemctl start silent-couple-bot-webhook
sudo systemctl enable silent-couple-bot-webhook
sudo systemctl status silent-couple-bot-webhook
```

### 6. Проверьте логи

```bash
sudo journalctl -u silent-couple-bot-webhook -f
```

Если видите ошибки - проверьте:
- Правильность путей в service файле
- Наличие всех зависимостей
- Правильность настроек в .env

### 7. Проверьте endpoints

```bash
curl https://24policybot.ru/health
curl -X POST https://24policybot.ru/webhook/robokassa
```

### 8. Настройте ResultURL в Робокассе

1. Войдите в личный кабинет Робокассы
2. Настройки магазина → ResultURL
3. Укажите: `https://24policybot.ru/webhook/robokassa`
4. Сохраните

## ✅ Готово!

После этого webhook сервер должен работать, и платежи Робокассы будут обрабатываться.

## Обновление кода в будущем

```bash
cd /root/silent-couple-bot
git pull
sudo systemctl restart silent-couple-bot-webhook
```
