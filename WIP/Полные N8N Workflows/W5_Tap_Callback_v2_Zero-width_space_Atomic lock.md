{
  "name": "W5_TapCallback_v2",
  "nodes": [
    {
      "parameters": { "trigger": "callback", "retryOnFail": true, "maxTries": 5 },
      "id": "telegram-callback",
      "type": "n8n-nodes-base.telegramTrigger",
      "typeVersion": 1
    },
    {
      "parameters": {
        "jsCode": "const data = items[0].json.callback_query.data;\nconst [action, pairId, userId] = data.split('_');\nreturn [{ json: { action, pair_id: parseInt(pairId), user_id: parseInt(userId), callback_id: items[0].json.callback_query.id, message_id: items[0].json.callback_query.message?.message_id } }];"
      },
      "id": "parse-callback",
      "type": "n8n-nodes-base.function",
      "typeVersion": 1
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "SELECT u.tg_id, p.uid_a, p.uid_b, p.morning_initiator_uid, p.morning_message_id_a, p.morning_message_id_b FROM users u JOIN pairs p ON (u.id = p.uid_a OR u.id = p.uid_b) WHERE p.id = $1 AND u.id = $2;",
        "retryOnFail": true,
        "maxTries": 3,
        "options": { "queryParams": "={{$json.pair_id}},{{$json.user_id}}" }
      },
      "id": "fetch-pair",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2,
      "credentials": { "postgres": { "id": "pg", "name": "Postgres" } }
    },
    {
      "parameters": {
        "conditions": {
          "string": [
            { "value1": "={{$json.action}}", "operation": "equal", "value2": "request_morning" }
          ]
        }
      },
      "id": "is-request",
      "type": "n8n-nodes-base.if",
      "typeVersion": 1
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "UPDATE pairs SET morning_initiator_uid = $1 WHERE id = $2 AND morning_initiator_uid IS NULL RETURNING *;",
        "retryOnFail": true,
        "maxTries": 3,
        "options": { "queryParams": "={{$json.user_id}},{{$json.pair_id}}" }
      },
      "id": "atomic-lock",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2,
      "credentials": { "postgres": { "id": "pg", "name": "Postgres" } }
    },
    {
      "parameters": {
        "jsCode": "const TelegramBot = require('node-telegram-bot-api');\nconst bot = new TelegramBot($env.TG_BOT_TOKEN);\nconst item = items[0].json;\nconst partnerId = item.uid_a === item.user_id ? item.uid_b : item.uid_a;\nconst partnerMsgId = item.uid_a === item.user_id ? item.morning_message_id_b : item.morning_message_id_a;\n\n// Если не удалось захватить (someone was faster)\nif (items.length === 0) {\n  await bot.editMessageText('Ваш партнёр уже отправил пожелание', {\n    chat_id: item.tg_id,\n    message_id: item.message_id,\n    reply_markup: { inline_keyboard: [] }\n  });\n  return [];\n}\n\n// Success!\nawait bot.editMessageText('✅ Вы отправили пожелание', {\n  chat_id: item.tg_id,\n  message_id: item.message_id,\n  reply_markup: { inline_keyboard: [] }\n});\n\n// Partner message - zero-width space trick\nawait bot.editMessageText('\\u200B', {\n  chat_id: partnerId,\n  message_id: partnerMsgId,\n  reply_markup: { inline_keyboard: [] }\n});\n\n// Send pic to partner\nconst pic = await $postgres.query(\"SELECT file_id FROM pics_pool WHERE type='morning' ORDER BY RANDOM() LIMIT 1;\");\nawait bot.sendPhoto(partnerId, pic[0].file_id, {\n  caption: 'Доброе утро ☀️',\n  reply_markup: {\n    inline_keyboard: [[{\n      text: \"Отправить в ответ\",\n      callback_data: `tap_morning_${item.pair_id}_${partnerId}`\n    }]]\n  }\n});\n\nreturn items;"
      },
      "id": "process-request",
      "type": "n8n-nodes-base.function",
      "typeVersion": 1
    },
    {
      "parameters": {
        "conditions": {
          "string": [
            { "value1": "={{$json.action}}", "operation": "equal", "value2": "tap_morning" }
          ]
        }
      },
      "id": "is-tap",
      "type": "n8n-nodes-base.if",
      "typeVersion": 1
    },
    {
      "parameters": {
        "jsCode": "const TelegramBot = require('node-telegram-bot-api');\nconst bot = new TelegramBot($env.TG_BOT_TOKEN);\nconst item = items[0].json;\nconst partnerId = item.uid_a === item.user_id ? item.uid_b : item.uid_a;\n\n// Remove button\nawait bot.editMessageText('✅ Вы ответили на пожелание', {\n  chat_id: item.tg_id,\n  message_id: item.message_id,\n  reply_markup: { inline_keyboard: [] }\n});\n\n// Send response pic\nconst pic = await $postgres.query(\"SELECT file_id FROM pics_pool WHERE type='morning' ORDER BY RANDOM() LIMIT 1;\");\nawait bot.sendPhoto(partnerId, pic[0].file_id, {\n  caption: 'Ваш партнёр ответил ❤️'\n});\n\nreturn items;"
      },
      "id": "process-tap",
      "type": "n8n-nodes-base.function",
      "typeVersion": 1
    },
    {
      "parameters": {
        "callbackQueryId": "={{$json.callback_id}}",
        "text": "Отправлено!"
      },
      "id": "answer-callback",
      "type": "n8n-nodes-base.telegram",
      "typeVersion": 1,
      "credentials": { "telegramApi": { "id": "tg", "name": "Telegram" } }
    }
  ],
  "connections": {
    "telegram-callback": { "main": [[{ "node": "parse-callback", "type": "main", "index": 0 }]] },
    "parse-callback": { "main": [[{ "node": "fetch-pair", "type": "main", "index": 0 }]] },
    "fetch-pair": { "main": [[{ "node": "is-request", "type": "main", "index": 0 }]] },
    "is-request": {
      "main": [
        [{ "node": "atomic-lock", "type": "main", "index": 0 }],
        [{ "node": "is-tap", "type": "main", "index": 0 }]
      ]
    },
    "atomic-lock": { "main": [[{ "node": "process-request", "type": "main", "index": 0 }]] },
    "is-tap": { "main": [[{ "node": "process-tap", "type": "main", "index": 0 }]] },
    "process-request": { "main": [[{ "node": "answer-callback", "type": "main", "index": 0 }]] },
    "process-tap": { "main": [[{ "node": "answer-callback", "type": "main", "index": 0 }]] }
  }
}