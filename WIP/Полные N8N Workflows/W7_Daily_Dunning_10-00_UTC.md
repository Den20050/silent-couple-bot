{
  "name": "W7_DailyDunning_v2",
  "nodes": [
    {
      "parameters": { "triggerTimes": { "item": [{ "hour": 10, "minute": 0 }] } },
      "id": "cron-dunning",
      "type": "n8n-nodes-base.cron",
      "typeVersion": 1
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "SELECT u.tg_id, s.id as sub_id, s.current_period_end FROM subscriptions s JOIN users u ON u.id = s.payer_uid WHERE s.status = 'past_due' AND s.current_period_end < NOW() - INTERVAL '1 day';",
        "retryOnFail": true,
        "maxTries": 3
      },
      "id": "fetch-overdue",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2,
      "credentials": { "postgres": { "id": "pg", "name": "Postgres" } }
    },
    {
      "parameters": {
        "chatId": "={{$json.tg_id}}",
        "text": "⏰ Подписка истекла. Оплатите 199 ₽, чтобы продолжить:",
        "buttons": [{ "text": "💳 Оплатить", "url": "https://yookassa.ru/shop/pay/{{$json.sub_id}}" }]
      },
      "id": "send-dunning",
      "type": "n8n-nodes-base.telegram",
      "typeVersion": 1,
      "retryOnFail": true,
      "maxTries": 3,
      "credentials": { "telegramApi": { "id": "tg", "name": "Telegram" } }
    }
  ],
  "connections": {
    "cron-dunning": { "main": [[{ "node": "fetch-overdue", "type": "main", "index": 0 }]] },
    "fetch-overdue": { "main": [[{ "node": "send-dunning", "type": "main", "index": 0 }]] }
  }
}