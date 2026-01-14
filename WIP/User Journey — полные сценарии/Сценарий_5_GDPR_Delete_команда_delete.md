User A пишет /delete
   └─ Бот: «Вы уверены?» (подтверждение inline-кнопкой)
   
User A подтверждает
   └─ DELETE FROM pings (cascade)
   └─ DELETE FROM pic_ledger (cascade)
   └─ DELETE FROM subscriptions (cascade)
   └─ DELETE FROM pairs (cascade)
   └─ DELETE FROM users WHERE tg_id = $1
   └─ DELETE FROM consent_audit (GDPR log)
   └─ Все данные удалены ≤ 3 секунд
   └─ Бот: «✅ Все ваши данные удалены»