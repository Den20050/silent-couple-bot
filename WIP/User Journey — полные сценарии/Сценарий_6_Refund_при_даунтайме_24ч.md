UptimeRobot: uptime < 95% за 24 часа
   └─ Алерт в Telegram-канал #alerts

Админ проверяет логи (Grafana → p99 latency >2с, queue depth >1000)
   └─ Подтверждает downtime >24ч
   └─ Запускает W8 (manual trigger)
   
W8:
   └─ Находит все active подписки за последние 7 дней
   └─ Создаёт refund в YooKassa (199 ₽)
   └─ Обновляет статус → 'cancelled'
   └─ Уведомляет user: «Возвращаем 199 ₽ в течение 3 дней»