День 0: Пара создана → subscription.status = 'trial', trial_end = +7д

День 7 (10:00 UTC): W7 проверяет подписки
   └─ status = 'trial' AND trial_end < NOW()
   └─ Отправляем invoice через YooKassa
   └─ subscription.status = 'active', current_period_end = +30д

День 37: payment failed
   └─ YooKassa webhook → status = 'past_due'
   └─ W7 каждый день отправляет напоминание

День 40: user оплачивает → W6 обновляет статус → 'active' +30д

Если downtime >24ч: админ запускает W8 → refund 199 ₽ → status = 'cancelled'