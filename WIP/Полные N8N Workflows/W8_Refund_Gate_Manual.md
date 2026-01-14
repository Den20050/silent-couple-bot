{
  "name": "W8_RefundGate_v2",
  "nodes": [
    {
      "parameters": { "trigger": "manual" },
      "id": "manual-trigger",
      "type": "n8n-nodes-base.manualTrigger",
      "typeVersion": 1
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "SELECT u.tg_id, s.id as sub_id, s.external_id, s.payer_uid FROM subscriptions s JOIN users u ON u.id = s.payer_uid WHERE s.status = 'active' AND s.current_period_end > NOW() - INTERVAL '7 days' LIMIT 1;"
      },
      "id": "fetch-sub",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2,
      "credentials": { "postgres": { "id": "pg", "name": "Postgres" } }
    },
    {
      "parameters": {
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "httpMethod": "POST",
        "url": "https://api.yookassa.ru/v3/refunds",
        "jsonParameters": true,
        "options": {
          "bodyContentType": "json",
          "headerParameters": {
            "parameters": [
              { "name": "Idempotence-Key", "value": "={{$json.sub_id}}" }
            ]
          },
          "bodyParameters": {
            "parameters": [
              { "name": "amount", "value": "{\"value\":\"199.00\",\"currency\":\"RUB\"}" },
              { "name": "payment_id", "value": "={{$json.external_id}}" }
            ]
          }
        },
        "retryOnFail": true,
        "maxTries": 3,
        "waitBetweenTries": 2000
      },
      "id": "yookassa-refund",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 4,
      "credentials": { "httpHeaderAuth": { "id": "yookassa", "name": "YooKassa Auth" } }
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "BEGIN; INSERT INTO refunds (sub_id, amount_cents, reason, refund_id, created_at) VALUES ($1, 19900, 'downtime >24h', $2, NOW()); UPDATE subscriptions SET status = 'cancelled' WHERE id = $1; COMMIT;",
        "retryOnFail": true,
        "maxTries": 3,
        "options": { "queryParams": "={{$json.sub_id}},{{$json.id}}" }
      },
      "id": "log-refund",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2,
      "credentials": { "postgres": { "id": "pg", "name": "Postgres" } }
    },
    {
      "parameters": {
        "chatId": "={{$json.tg_id}}",
        "text": "Извините, сервис был недоступен >24ч. Возвращаем 199 ₽ в течение 3 дней."
      },
      "id": "notify-refund",
      "type": "n8n-nodes-base.telegram",
      "typeVersion": 1,
      "credentials": { "telegramApi": { "id": "tg", "name": "Telegram" } }
    }
  ],
  "connections": {
    "manual-trigger": { "main": [[{ "node": "fetch-sub", "type": "main", "index": 0 }]] },
    "fetch-sub": { "main": [[{ "node": "yookassa-refund", "type": "main", "index": 0 }]] },
    "yookassa-refund": { "main": [[{ "node": "log-refund", "type": "main", "index": 0 }]] },
    "log-refund": { "main": [[{ "node": "notify-refund", "type": "main", "index": 0 }]] }
  }
}