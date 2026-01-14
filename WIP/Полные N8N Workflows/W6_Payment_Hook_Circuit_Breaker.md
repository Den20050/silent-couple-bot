{
  "name": "W6_PaymentHook_CircuitBreaker",
  "nodes": [
    {
      "parameters": { "httpMethod": "POST", "path": "webhook/yookassa" },
      "id": "http-webhook",
      "type": "n8n-nodes-base.webhook",
      "typeVersion": 1
    },
    {
      "parameters": {
        "jsCode": "const crypto = require('crypto');\nconst secret = $env.YOOKASSA_SECRET;\nconst sig = items[0].headers['yookassa-signature'];\nconst body = JSON.stringify(items[0].json);\nconst hmac = crypto.createHmac('sha256', secret).update(body).digest('hex');\nif (sig !== hmac) throw new Error('Invalid signature');\nreturn items;"
      },
      "id": "verify-sig",
      "type": "n8n-nodes-base.function",
      "typeVersion": 1
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "SELECT is_open FROM circuit_breaker WHERE service = 'yookassa';",
        "retryOnFail": false
      },
      "id": "check-circuit",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2,
      "credentials": { "postgres": { "id": "pg", "name": "Postgres" } }
    },
    {
      "parameters": {
        "conditions": {
          "boolean": [
            { "value1": "={{$json.is_open}}", "operation": "equal", "value2": false }
          ]
        }
      },
      "id": "circuit-closed",
      "type": "n8n-nodes-base.if",
      "typeVersion": 1
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "UPDATE subscriptions SET status = 'active', current_period_end = $1, updated_at = NOW() WHERE external_id = $2 RETURNING *;",
        "retryOnFail": true,
        "maxTries": 5,
        "waitBetweenTries": 2000,
        "options": { "queryParams": "={{$json.object.paid_till}},{{$json.object.id}}" },
        "onError": "continueErrorOutput"
      },
      "id": "update-sub",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2,
      "credentials": { "postgres": { "id": "pg", "name": "Postgres" } }
    },
    {
      "parameters": {
        "jsCode": "const errorCount = $runIndex || 0;\nconst maxErrors = 3;\nif ($node['update-sub'].hasOwnProperty('error')) {\n  if (errorCount >= maxErrors) {\n    await $postgres.query(\"UPDATE circuit_breaker SET is_open = TRUE, opened_at = NOW(), error_count = $1 WHERE service = 'yookassa'\", [errorCount]);\n    await $notify('Circuit Opened', 'YooKassa webhook failed 3 times');\n    return [{ json: { status: 'circuit_open' } }];\n  }\n  $runIndex = errorCount + 1;\n  return $input.all();\n}\nawait $postgres.query(\"UPDATE circuit_breaker SET is_open = FALSE, error_count = 0 WHERE service = 'yookassa'\");\nreturn items;"
      },
      "id": "circuit-logic",
      "type": "n8n-nodes-base.function",
      "typeVersion": 1
    },
    {
      "parameters": {
        "chatId": "={{$json.payer_uid}}",
        "text": "✅ Оплата получена! Подписка продлена до {{$json.current_period_end}}"
      },
      "id": "confirm",
      "type": "n8n-nodes-base.telegram",
      "typeVersion": 1,
      "credentials": { "telegramApi": { "id": "tg", "name": "Telegram" } }
    },
    {
      "parameters": {
        "chatId": "={{$env.ADMIN_TG_ID}}",
        "text": "⚠️ Circuit Breaker: YooKassa открыт. Проверьте платежи."
      },
      "id": "alert-circuit",
      "type": "n8n-nodes-base.telegram",
      "typeVersion": 1,
      "credentials": { "telegramApi": { "id": "tg", "name": "Telegram" } }
    }
  ],
  "connections": {
    "http-webhook": { "main": [[{ "node": "verify-sig", "type": "main", "index": 0 }]] },
    "verify-sig": { "main": [[{ "node": "check-circuit", "type": "main", "index": 0 }]] },
    "check-circuit": { "main": [[{ "node": "circuit-closed", "type": "main", "index": 0 }]] },
    "circuit-closed": {
      "main": [
        [{ "node": "update-sub", "type": "main", "index": 0 }],
        [{ "node": "alert-circuit", "type": "main", "index": 0 }]
      ]
    },
    "update-sub": {
      "main": [[{ "node": "circuit-logic", "type": "main", "index": 0 }]],
      "error": [[{ "node": "circuit-logic", "type": "main", "index": 0 }]]
    },
    "circuit-logic": { "main": [[{ "node": "confirm", "type": "main", "index": 0 }]] }
  }
}