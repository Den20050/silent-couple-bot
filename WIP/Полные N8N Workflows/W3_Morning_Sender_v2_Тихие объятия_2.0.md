{
  "name": "W3_MorningSender_v2",
  "nodes": [
    {
      "parameters": { "triggerTimes": { "item": [{ "minute": "0,30" }] } },
      "id": "cron-morning",
      "type": "n8n-nodes-base.cron",
      "typeVersion": 1
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "SELECT u.id, u.tg_id, p.id as pair_id, p.uid_a, p.uid_b, p.mode, p.common_chat_id FROM users u JOIN pairs p ON (u.id = p.uid_a OR u.id = p.uid_b) WHERE p.status IN ('trial', 'active') AND (EXTRACT(HOUR FROM NOW() AT TIME ZONE 'UTC' - INTERVAL '7 hours 30 minutes' - u.utc_offset) = 7);",
        "retryOnFail": true,
        "maxTries": 3
      },
      "id": "fetch-pairs",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2,
      "credentials": { "postgres": { "id": "pg", "name": "Postgres" } }
    },
    {
      "parameters": {
        "jsCode": "for (const item of items) {\n  item.json.is_morning_time = true;\n}\nreturn items;"
      },
      "id": "prepare",
      "type": "n8n-nodes-base.function",
      "typeVersion": 1
    },
    {
      "parameters": {
        "jsCode": "const TelegramBot = require('node-telegram-bot-api');\nconst bot = new TelegramBot($env.TG_BOT_TOKEN);\nconst results = [];\n\nfor (const item of items) {\n  const pair = item.json;\n  \n  // Выбираем картинку\n  const pic = await $postgres.query(\"SELECT file_id FROM pics_pool WHERE type='morning' ORDER BY RANDOM() LIMIT 1;\");\n  \n  if (pair.mode === 'chat' && pair.common_chat_id) {\n    // Режим CHAT: отправляем кнопку Mini App в личный чат\n    await bot.sendMessage(pair.uid_a, 'Утро! Откройте и поделитесь с партнёром:', {\n      reply_markup: {\n        inline_keyboard: [[{\n          text: \"📤 Отправить картинку в чат\",\n          web_app: { url: `${process.env.MINI_APP_URL}?file_id=${pic[0].file_id}&chat_id=${pair.common_chat_id}` }\n        }]]\n      }\n    });\n    \n    await bot.sendMessage(pair.uid_b, 'Утро! Откройте и поделитесь с партнёром:', {\n      reply_markup: {\n        inline_keyboard: [[{\n          text: \"📤 Отправить картинку в чат\",\n          web_app: { url: `${process.env.MINI_APP_URL}?file_id=${pic[0].file_id}&chat_id=${pair.common_chat_id}` }\n        }]]\n      }\n    });\n  } else {\n    // Режим SILENT: отправляем запрос в чат с ботом\n    const msgA = await bot.sendMessage(pair.uid_a, 'Хотите отправить пожелание с \"Добрым утром\"?', {\n      reply_markup: {\n        inline_keyboard: [[{\n          text: \"Отправить в ответ\",\n          callback_data: `request_morning_${pair.pair_id}_${pair.uid_a}`\n        }]]\n      }\n    });\n    \n    const msgB = await bot.sendMessage(pair.uid_b, 'Хотите отправить пожелание с \"Добрым утром\"?', {\n      reply_markup: {\n        inline_keyboard: [[{\n          text: \"Отправить в ответ\",\n          callback_data: `request_morning_${pair.pair_id}_${pair.uid_b}`\n        }]]\n      }\n    });\n    \n    results.push({\n      json: {\n        pair_id: pair.pair_id,\n        message_id_a: msgA.message_id,\n        message_id_b: msgB.message_id\n      }\n    });\n  }\n}\n\nreturn results;"
      },
      "id": "send-by-mode",
      "type": "n8n-nodes-base.function",
      "typeVersion": 1
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "UPDATE pairs SET morning_message_id_a = $1, morning_message_id_b = $2 WHERE id = $3;",
        "retryOnFail": true,
        "maxTries": 3,
        "options": { "queryParams": "={{$json.message_id_a}},{{$json.message_id_b}},{{$json.pair_id}}" }
      },
      "id": "save-ids",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2,
      "credentials": { "postgres": { "id": "pg", "name": "Postgres" } }
    }
  ],
  "connections": {
    "cron-morning": { "main": [[{ "node": "fetch-pairs", "type": "main", "index": 0 }]] },
    "fetch-pairs": { "main": [[{ "node": "prepare", "type": "main", "index": 0 }]] },
    "prepare": { "main": [[{ "node": "send-by-mode", "type": "main", "index": 0 }]] },
    "send-by-mode": { "main": [[{ "node": "save-ids", "type": "main", "index": 0 }]] }
  }
}