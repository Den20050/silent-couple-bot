{
  "name": "W4_EveningSender_v2",
  "nodes": [
    {
      "parameters": { "triggerTimes": { "item": [{ "minute": "0,30" }] } },
      "id": "cron-evening",
      "type": "n8n-nodes-base.cron",
      "typeVersion": 1
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "SELECT u.id, u.tg_id, p.id as pair_id, p.uid_a, p.uid_b FROM users u JOIN pairs p ON (u.id = p.uid_a OR u.id = p.uid_b) WHERE p.status IN ('trial', 'active') AND (EXTRACT(HOUR FROM NOW() AT TIME ZONE 'UTC' - INTERVAL '21 hours 30 minutes' - u.utc_offset) = 21);",
        "retryOnFail": true,
        "maxTries": 3
      },
      "id": "fetch-pairs-evening",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2,
      "credentials": { "postgres": { "id": "pg", "name": "Postgres" } }
    },
    {
      "parameters": {
        "jsCode": "/* Аналогично W3 */ const TelegramBot = require('node-telegram-bot-api'); const bot = new TelegramBot($env.TG_BOT_TOKEN); /* ... отправка вечернего запроса ... */ return results;"
      },
      "id": "send-requests-evening",
      "type": "n8n-nodes-base.function",
      "typeVersion": 1
    }
  ],
  "connections": {
    "cron-evening": { "main": [[{ "node": "fetch-pairs-evening", "type": "main", "index": 0 }]] },
    "fetch-pairs-evening": { "main": [[{ "node": "send-requests-evening", "type": "main", "index": 0 }]] }
  }
}