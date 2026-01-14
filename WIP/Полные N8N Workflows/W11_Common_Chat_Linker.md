{
  "name": "W11_CommonChatLinker",
  "nodes": [
    {
      "parameters": { "trigger": "message", "message": "link" },
      "id": "telegram-trigger-link",
      "type": "n8n-nodes-base.telegramTrigger",
      "typeVersion": 1
    },
    {
      "parameters": {
        "jsCode": "const msg = items[0].json.message;\nif (!msg.chat || msg.chat.type !== 'private') {\n  throw new Error('Эту команду нужно отправить в личном чате с партнёром!');\n}\nreturn [{ json: { chat_id: msg.chat.id, tg_id: msg.from.id } }];"
      },
      "id": "parse-link",
      "type": "n8n-nodes-base.function",
      "typeVersion": 1
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "SELECT p.id as pair_id, p.uid_a, p.uid_b, p.mode FROM pairs p JOIN users u ON (u.id = p.uid_a OR u.id = p.uid_b) WHERE u.tg_id = $1 AND p.mode = 'chat' AND p.status IN ('trial', 'active');",
        "retryOnFail": true,
        "maxTries": 3,
        "options": { "queryParams": "={{$json.tg_id}}" }
      },
      "id": "find-pair",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2,
      "credentials": { "postgres": { "id": "pg", "name": "Postgres" } }
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "UPDATE pairs SET common_chat_id = $1 WHERE id = $2 RETURNING *;",
        "retryOnFail": true,
        "maxTries": 3,
        "options": { "queryParams": "={{$json.chat_id}},{{$json.pair_id}}" }
      },
      "id": "save-chat-id",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2,
      "credentials": { "postgres": { "id": "pg", "name": "Postgres" } }
    },
    {
      "parameters": {
        "chatId": "={{$json.tg_id}}",
        "text": "✅ Чат связан! Теперь картинки будут приходить сюда через Mini App.\n\nЗакрепите это сообщение, чтобы не потерять."
      },
      "id": "confirm-link",
      "type": "n8n-nodes-base.telegram",
      "typeVersion": 1,
      "credentials": { "telegramApi": { "id": "tg", "name": "TG" } }
    }
  ],
  "connections": {
    "telegram-trigger-link": { "main": [[{ "node": "parse-link", "type": "main", "index": 0 }]] },
    "parse-link": { "main": [[{ "node": "find-pair", "type": "main", "index": 0 }]] },
    "find-pair": { "main": [[{ "node": "save-chat-id", "type": "main", "index": 0 }]] },
    "save-chat-id": { "main": [[{ "node": "confirm-link", "type": "main", "index": 0 }]] }
  }
}