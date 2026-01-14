{
  "name": "W1_Onboarding_v2",
  "nodes": [
    {
      "parameters": { "trigger": "message", "message": "start" },
      "id": "telegram-trigger-start",
      "type": "n8n-nodes-base.telegramTrigger",
      "typeVersion": 1
    },
    {
      "parameters": {
        "jsCode": "const msg = items[0].json.message;\nreturn [{ json: { tg_id: msg.from.id, username: msg.from.username || '', ip: items[0].headers['x-real-ip'] || '0.0.0.0' } }];"
      },
      "id": "parse-user",
      "type": "n8n-nodes-base.function",
      "typeVersion": 1
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "INSERT INTO users (tg_id, tg_username, consent_ip, consent_dt) VALUES ($1, $2, $3, NOW()) ON CONFLICT (tg_id) DO UPDATE SET consent_ip = EXCLUDED.consent_ip RETURNING id, consent;",
        "retryOnFail": true,
        "maxTries": 3,
        "options": { "queryParams": "={{$json.tg_id}},{{$json.username}},{{$json.ip}}" }
      },
      "id": "upsert-user",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2,
      "credentials": { "postgres": { "id": "pg", "name": "PG" } }
    },
    {
      "parameters": {
        "chatId": "={{$json.tg_id}}",
        "text": "Добро пожаловать! 📄 Ознакомьтесь с политикой:",
        "buttons": [{ "text": "📄 Политика", "url": "https://telegra.ph/YourPrivacy-07-01" }]
      },
      "id": "show-policy",
      "type": "n8n-nodes-base.telegram",
      "typeVersion": 1,
      "credentials": { "telegramApi": { "id": "tg", "name": "TG" } }
    },
    {
      "parameters": {
        "chatId": "={{$json.tg_id}}",
        "text": "Ознакомились? Теперь можете принять условия:",
        "buttons": [{ "text": "Принимаю ✅", "callbackData": "consent_={{$json.id}}" }]
      },
      "id": "ask-consent",
      "type": "n8n-nodes-base.telegram",
      "typeVersion": 1,
      "credentials": { "telegramApi": { "id": "tg", "name": "TG" } }
    },
    {
      "parameters": {
        "trigger": "callback",
        "message": "consent_"
      },
      "id": "telegram-callback-consent",
      "type": "n8n-nodes-base.telegramTrigger",
      "typeVersion": 1
    },
    {
      "parameters": {
        "jsCode": "const userId = items[0].json.callback_query.data.split('_')[1];\nreturn [{ json: { user_id: parseInt(userId), callback_id: items[0].json.callback_query.id, tg_id: items[0].json.callback_query.from.id } }];"
      },
      "id": "parse-consent",
      "type": "n8n-nodes-base.function",
      "typeVersion": 1
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "UPDATE users SET consent = TRUE, consent_dt = NOW() WHERE id = $1 RETURNING id;",
        "retryOnFail": true,
        "maxTries": 3,
        "options": { "queryParams": "={{$json.user_id}}" }
      },
      "id": "save-consent",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2,
      "credentials": { "postgres": { "id": "pg", "name": "PG" } }
    },
    {
      "parameters": {
        "chatId": "={{$json.tg_id}}",
        "text": "Как вы общаетесь с партнёром?",
        "buttons": [
          { "text": "💬 Часто пишем в личном чате", "callbackData": "mode_chat_={{$json.user_id}}" },
          { "text": "💔 Редко, нужен сигнал", "callbackData": "mode_silent_={{$json.user_id}}" }
        ]
      },
      "id": "ask-mode",
      "type": "n8n-nodes-base.telegram",
      "typeVersion": 1,
      "credentials": { "telegramApi": { "id": "tg", "name": "TG" } }
    },
    {
      "parameters": {
        "trigger": "callback",
        "message": "mode_"
      },
      "id": "telegram-callback-mode",
      "type": "n8n-nodes-base.telegramTrigger",
      "typeVersion": 1
    },
    {
      "parameters": {
        "jsCode": "const [mode, userId] = items[0].json.callback_query.data.split('_');\nreturn [{ json: { mode: mode.split('_')[1], user_id: parseInt(userId), tg_id: items[0].json.callback_query.from.id } }];"
      },
      "id": "parse-mode",
      "type": "n8n-nodes-base.function",
      "typeVersion": 1
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "UPDATE users SET updated_at = NOW() WHERE id = $1 RETURNING id;",
        "retryOnFail": true,
        "maxTries": 3,
        "options": { "queryParams": "={{$json.user_id}}" }
      },
      "id": "update-user-mode",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2,
      "credentials": { "postgres": { "id": "pg", "name": "PG" } }
    },
    {
      "parameters": {
        "chatId": "={{$json.tg_id}}",
        "text": "={{$json.mode === 'chat' ? 'Отлично! Теперь добавьте меня в личный чат с партнёром и отправьте команду /link' : 'Хорошо! Вы выбрали режим безмолвия. Пригласите партнёра по ссылке'}}",
        "buttons": [{ "text": "➡️ Пригласить партнёра", "callbackData": "invite_={{$json.user_id}}_{{$json.mode}}" }]
      },
      "id": "mode-instruction",
      "type": "n8n-nodes-base.telegram",
      "typeVersion": 1,
      "credentials": { "telegramApi": { "id": "tg", "name": "TG" } }
    }
  ],
  "connections": {
    "telegram-trigger-start": { "main": [[{ "node": "parse-user", "type": "main", "index": 0 }]] },
    "parse-user": { "main": [[{ "node": "upsert-user", "type": "main", "index": 0 }]] },
    "upsert-user": { "main": [[{ "node": "show-policy", "type": "main", "index": 0 }]] },
    "show-policy": { "main": [[{ "node": "ask-consent", "type": "main", "index": 0 }]] },
    "telegram-callback-consent": { "main": [[{ "node": "parse-consent", "type": "main", "index": 0 }]] },
    "parse-consent": { "main": [[{ "node": "save-consent", "type": "main", "index": 0 }]] },
    "save-consent": { "main": [[{ "node": "ask-mode", "type": "main", "index": 0 }]] },
    "telegram-callback-mode": { "main": [[{ "node": "parse-mode", "type": "main", "index": 0 }]] },
    "parse-mode": { "main": [[{ "node": "update-user-mode", "type": "main", "index": 0 }]] },
    "update-user-mode": { "main": [[{ "node": "mode-instruction", "type": "main", "index": 0 }]] }
  }
}