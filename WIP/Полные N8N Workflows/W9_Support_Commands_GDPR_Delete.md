{
  "name": "W9_SupportCommands_v2",
  "nodes": [
    {
      "parameters": { "trigger": "message", "message": "delete" },
      "id": "telegram-delete",
      "type": "n8n-nodes-base.telegramTrigger",
      "typeVersion": 1
    },
    {
      "parameters": { "trigger": "message", "message": "help" },
      "id": "telegram-help",
      "type": "n8n-nodes-base.telegramTrigger",
      "typeVersion": 1
    },
    {
      "parameters": {
        "jsCode": "return [{ json: { tg_id: items[0].json.message.from.id } }];"
      },
      "id": "parse-tg-id",
      "type": "n8n-nodes-base.function",
      "typeVersion": 1
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "BEGIN; DELETE FROM consent_audit WHERE user_id = (SELECT id FROM users WHERE tg_id = $1); DELETE FROM pings WHERE pair_id IN (SELECT id FROM pairs WHERE uid_a = (SELECT id FROM users WHERE tg_id = $1) OR uid_b = (SELECT id FROM users WHERE tg_id = $1)); DELETE FROM pic_ledger WHERE pair_id IN (SELECT id FROM pairs WHERE uid_a = (SELECT id FROM users WHERE tg_id = $1) OR uid_b = (SELECT id FROM users WHERE tg_id = $1)); DELETE FROM refunds WHERE sub_id IN (SELECT id FROM subscriptions WHERE pair_id IN (SELECT id FROM pairs WHERE uid_a = (SELECT id FROM users WHERE tg_id = $1) OR uid_b = (SELECT id FROM users WHERE tg_id = $1))); DELETE FROM subscriptions WHERE pair_id IN (SELECT id FROM pairs WHERE uid_a = (SELECT id FROM users WHERE tg_id = $1) OR uid_b = (SELECT id FROM users WHERE tg_id = $1)); DELETE FROM pairs WHERE uid_a = (SELECT id FROM users WHERE tg_id = $1) OR uid_b = (SELECT id FROM users WHERE tg_id = $1); DELETE FROM users WHERE tg_id = $1; COMMIT;",
        "retryOnFail": true,
        "maxTries": 3,
        "options": { "queryParams": "={{$json.tg_id}}" }
      },
      "id": "gdpr-delete",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2,
      "credentials": { "postgres": { "id": "pg", "name": "Postgres" } }
    },
    {
      "parameters": {
        "chatId": "={{$json.tg_id}}",
        "text": "✅ Все ваши данные удалены. Подписка отменена. Спасибо за использование!"
      },
      "id": "confirm-delete",
      "type": "n8n-nodes-base.telegram",
      "typeVersion": 1,
      "credentials": { "telegramApi": { "id": "tg", "name": "Telegram" } }
    },
    {
      "parameters": {
        "chatId": "={{$json.tg_id}}",
        "text": "📖 Команды:\n/start — Начать\n/tz — Изменить часовой пояс\n/menu — Показать меню\n/pay — Оплатить подписку\n/delete — Удалить себя (GDPR)\n/help — Показать это сообщение"
      },
      "id": "show-help",
      "type": "n8n-nodes-base.telegram",
      "typeVersion": 1,
      "credentials": { "telegramApi": { "id": "tg", "name": "Telegram" } }
    }
  ],
  "connections": {
    "telegram-delete": { "main": [[{ "node": "parse-tg-id", "type": "main", "index": 0 }]] },
    "parse-tg-id": { "main": [[{ "node": "gdpr-delete", "type": "main", "index": 0 }]] },
    "gdpr-delete": { "main": [[{ "node": "confirm-delete", "type": "main", "index": 0 }]] },
    "telegram-help": { "main": [[{ "node": "show-help", "type": "main", "index": 0 }]] }
  }
}