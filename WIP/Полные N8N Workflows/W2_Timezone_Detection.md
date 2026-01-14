{
  "name": "W2_TimezoneSetter_v2",
  "nodes": [
    {
      "parameters": { "trigger": "message", "message": "tz" },
      "id": "telegram-trigger-tz",
      "type": "n8n-nodes-base.telegramTrigger",
      "typeVersion": 1
    },
    {
      "parameters": {
        "jsCode": "const msg = items[0].json.message;\nconst msgDate = new Date(msg.date * 1000);\nconst utcHour = msgDate.getUTCHours();\nconst localHour = msgDate.getHours();\nreturn [{ json: { tg_id: msg.from.id, offset: localHour - utcHour } }];"
      },
      "id": "detect-tz",
      "type": "n8n-nodes-base.function",
      "typeVersion": 1
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "UPDATE users SET utc_offset = $1 WHERE tg_id = $2 RETURNING *;",
        "retryOnFail": true,
        "maxTries": 3,
        "options": { "queryParams": "={{$json.offset}},{{$json.tg_id}}" }
      },
      "id": "update-tz",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2,
      "credentials": { "postgres": { "id": "pg", "name": "Postgres" } }
    },
    {
      "parameters": {
        "chatId": "={{$json.tg_id}}",
        "text": "Часовой пояс обновлён: UTC{{$json.offset >= 0 ? '+' : ''}}{{$json.offset}}"
      },
      "id": "confirm-tz",
      "type": "n8n-nodes-base.telegram",
      "typeVersion": 1,
      "credentials": { "telegramApi": { "id": "tg", "name": "Telegram" } }
    }
  ],
  "connections": {
    "telegram-trigger-tz": { "main": [[{ "node": "detect-tz", "type": "main", "index": 0 }]] },
    "detect-tz": { "main": [[{ "node": "update-tz", "type": "main", "index": 0 }]] },
    "update-tz": { "main": [[{ "node": "confirm-tz", "type": "main", "index": 0 }]] }
  }
}