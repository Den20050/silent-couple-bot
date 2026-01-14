#!/bin/bash
set -e

echo "🚀 Silent Couple Bot 2.1 Deployment"

# 1. Проверка переменных
if [ -z "$TG_BOT_TOKEN" ]; then echo "❌ TG_BOT_TOKEN not set"; exit 1; fi
if [ -z "$DOMAIN" ]; then echo "❌ DOMAIN not set"; exit 1; fi

# 2. Сборка кастомного N8N
echo "Building N8N image..."
docker build -t n8n-custom:latest -f Dockerfile.n8n .

# 3. Запуск
echo "Starting infrastructure..."
docker-compose up -d

# 4. Ждём готовности
echo "Waiting for PostgreSQL primary..."
until docker exec n8n_db_primary pg_isready -U n8n; do sleep 2; done

echo "Waiting for replicas..."
until docker exec n8n_db_replica1 pg_isready -U n8n; do sleep 2; done
until docker exec n8n_db_replica2 pg_isready -U n8n; do sleep 2; done

# 5. Инициализация БД
echo "Initializing database..."
docker exec -it n8n_db_primary psql -U n8n -d n8n -f /docker-entrypoint-initdb.d/01-schema.sql
docker exec -it n8n_db_primary psql -U n8n -d n8n -f /docker-entrypoint-initdb.d/02-users.sql
docker exec -it n8n_db_primary psql -U n8n -d n8n -f /docker-entrypoint-initdb.d/03-partitions.sql

# 6. Создаём слоты репликации
docker exec n8n_db_primary psql -U n8n -c "SELECT * FROM pg_create_physical_replication_slot('replica1');"
docker exec n8n_db_primary psql -U n8n -c "SELECT * FROM pg_create_physical_replication_slot('replica2');"

# 7. Запуск workers
echo "Starting workers..."
docker-compose -f docker-compose.workers.yml up -d

# 8. Healthcheck
echo "Healthcheck..."
sleep 30
docker exec n8n_main curl -f http://localhost:5678/health || exit 1

# 9. Webhook Telegram
echo "Setting webhook..."
curl -s "https://api.telegram.org/bot${TG_BOT_TOKEN}/setWebhook?url=https://${DOMAIN}/webhook/telegram" | jq .

# 10. Команды меню
curl -X POST "https://api.telegram.org/bot${TG_BOT_TOKEN}/setMyCommands" \
  -d 'commands=[{"command":"start","description":"Начать"},{"command":"tz","description":"Часовой пояс"},{"command":"menu","description":"Меню"},{"command":"pay","description":"Оплатить"},{"command":"delete","description":"Удалить себя"},{"command":"help","description":"Помощь"}]' | jq .

# 11. Загрузка картинок
echo "Loading images..."
mkdir -p /opt/silent-bot/pics
# Скопировать картинки сюда
node scripts/load_test.js

echo "✅ Deployment complete!"
echo "📊 Check Grafana: https://grafana.$DOMAIN"
echo "🤖 Bot: https://t.me/YourBot"