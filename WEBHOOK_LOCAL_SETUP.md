# Настройка Webhook для локального проекта

## Текущая архитектура

- **Локально (Windows)**: Проект, бот (polling режим)
- **На сервере (91.222.237.94)**: PostgreSQL, Redis, Nginx

## Проблема

Nginx на сервере настроен проксировать `/webhook/telegram` на `127.0.0.1:8443`, но webhook сервер должен работать на том же сервере, где Nginx.

## Решения

### Вариант 1: Запустить webhook сервер на сервере (рекомендуется для production)

#### Шаг 1: Скопировать проект на сервер

```bash
# На локальной машине (Windows PowerShell)
scp -r C:\Silent-Couple-Bot root@91.222.237.94:/root/Silent-Couple-Bot
```

Или используйте Git:
```bash
# На сервере
cd /root
git clone <your-repo-url> Silent-Couple-Bot
cd Silent-Couple-Bot
```

#### Шаг 2: Настроить .env на сервере

```bash
# На сервере
cd /root/Silent-Couple-Bot
cp env.example .env
nano .env
```

Настройте:
- `DATABASE_URL` - должен указывать на локальный PostgreSQL (без SSH туннеля, так как мы уже на сервере)
- `REDIS_URL` - должен указывать на локальный Redis
- `WEBHOOK_URL=https://24policybot.ru/webhook/telegram`
- `WEBHOOK_SECRET_TOKEN` - сгенерируйте токен

#### Шаг 3: Установить зависимости на сервере

```bash
cd /root/Silent-Couple-Bot
pip3 install -r requirements.txt
pip3 install uvicorn[standard]
```

#### Шаг 4: Создать и запустить systemd service

```bash
# Создать service файл
sudo bash -c 'cat > /etc/systemd/system/silent-couple-bot-webhook.service << '\''EOF'\''
[Unit]
Description=Silent Couple Bot Webhook Server
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/Silent-Couple-Bot
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 -m src.entrypoints.webhook
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF'

# Запустить
sudo systemctl daemon-reload
sudo systemctl start silent-couple-bot-webhook
sudo systemctl enable silent-couple-bot-webhook
sudo systemctl status silent-couple-bot-webhook
```

#### Шаг 5: Установить webhook в Telegram

```bash
cd /root/Silent-Couple-Bot
python3 scripts/set_webhook.py
```

---

### Вариант 2: Reverse SSH Tunnel (для разработки)

Если хотите запустить webhook локально и проксировать через сервер:

#### Шаг 1: Запустить webhook сервер локально

```bash
# На локальной машине (Windows PowerShell)
cd C:\Silent-Couple-Bot
python -m src.entrypoints.webhook
```

#### Шаг 2: Создать reverse SSH tunnel

```bash
# На локальной машине (Windows PowerShell)
# Проксирует порт 8443 с сервера на локальный порт 8443
ssh -R 8443:localhost:8443 root@91.222.237.94 -N
```

#### Шаг 3: Обновить Nginx на сервере

Nginx уже настроен правильно - он проксирует на `127.0.0.1:8443`, который теперь будет перенаправлен через tunnel на локальную машину.

#### Шаг 4: Установить webhook

```bash
# На локальной машине
python scripts/set_webhook.py
```

**Недостатки варианта 2:**
- Требует постоянного SSH соединения
- Не подходит для production (если локальная машина выключена, webhook не работает)
- Медленнее из-за дополнительного hop

---

## Рекомендация

Для production используйте **Вариант 1** - запустите webhook сервер на сервере. Это:
- ✅ Надежнее (не зависит от локальной машины)
- ✅ Быстрее (нет дополнительных network hops)
- ✅ Стандартная практика для production

Для разработки можно использовать **Вариант 2**, но лучше все равно использовать Вариант 1 с отдельной веткой/окружением на сервере.

