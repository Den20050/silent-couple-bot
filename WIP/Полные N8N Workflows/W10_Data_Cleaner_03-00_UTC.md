{
  "name": "W10_DataCleaner_v2",
  "nodes": [
    {
      "parameters": { "triggerTimes": { "item": [{ "hour": 3, "minute": 0 }] } },
      "id": "cron-cleaner",
      "type": "n8n-nodes-base.cron",
      "typeVersion": 1
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "DELETE FROM pings WHERE sent_at < NOW() - INTERVAL '90 days'; DELETE FROM pic_ledger WHERE sent_at < CURRENT_DATE - 30; DELETE FROM consent_audit WHERE created_at < NOW() - INTERVAL '3 years'; VACUUM ANALYZE pings, pic_ledger, consent_audit;",
        "retryOnFail": true,
        "maxTries": 3
      },
      "id": "clean-data",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2,
      "credentials": { "postgres": { "id": "pg", "name": "Postgres" } }
    },
    {
      "parameters": {
        "chatId": "={{$env.ADMIN_TG_ID}}",
        "text": "🧹 Очистка завершена: pings >90д, ledger >30д, audit >3лет."
      },
      "id": "notify-admin",
      "type": "n8n-nodes-base.telegram",
      "typeVersion": 1,
      "credentials": { "telegramApi": { "id": "tg", "name": "Telegram" } }
    }
  ],
  "connections": {
    "cron-cleaner": { "main": [[{ "node": "clean-data", "type": "main", "index": 0 }]] },
    "clean-data": { "main": [[{ "node": "notify-admin", "type": "main", "index": 0 }]] }
  }
}