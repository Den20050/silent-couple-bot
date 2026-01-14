# Анализ окончания демо режима

## Обзор

Данный документ описывает, что происходит в системе, когда заканчивается демо период (7 дней) для пары пользователей.

## Жизненный цикл подписки

### 1. Создание пары и начало демо периода

**Место в коде:** `src/bot/handlers/start.py`

При создании пары:
- Создается запись в таблице `pairs` со статусом `trial`
- Создается запись в таблице `subscriptions`:
  - `status = 'trial'`
  - `period_end = date.today() + 7 дней`
  - `is_lifetime = False`
- Оба пользователя помечаются в `user_demo` (защита от повторного использования демо)

**Код:**
```python
# src/bot/handlers/start.py:350-356
trial_end = date.today() + timedelta(days=TRIAL_PERIOD_DAYS)
await subs_repo.create(
    pair_id=pair.id,
    payer_id=partner.id,
    period_end=trial_end,
)
```

### 2. Работа в демо режиме

**Место в коде:** `src/worker/jobs.py`

Пока демо период активен:
- Пара имеет статус `trial` в таблице `pairs`
- Подписка имеет статус `trial` в таблице `subscriptions`
- Пара попадает в выборку `get_active_pairs()` (включает только `trial` и `active`)
- Утренние и вечерние сообщения отправляются ежедневно
- Пользователи могут обмениваться картинками через кнопки

**Код:**
```python
# src/db/repositories/pairs.py:125-130
async def get_active_pairs(self) -> list[Pair]:
    """Get active pairs (trial or active status)."""
    result = await self.session.execute(
        select(Pair).where(Pair.status.in_([PairStatus.TRIAL.value, PairStatus.ACTIVE.value]))
    )
    return list(result.scalars().all())
```

### 3. Обнаружение просроченных подписок

**Место в коде:** `src/worker/jobs.py:dunning_notifications()`

**Расписание:** Ежедневно в 10:00 UTC

**Процесс:**
1. Задача `dunning_notifications` запускается по расписанию
2. Вызывается `subs_repo.get_past_due()` для поиска просроченных подписок
3. Критерии поиска:
   - `subscription.period_end < today`
   - `subscription.status IN ('trial', 'active')`
   - `subscription.is_lifetime = False`

**Код:**
```python
# src/db/repositories/subscriptions.py:88-98
async def get_past_due(self) -> list[Subscription]:
    """Get past due subscriptions (excluding lifetime subscriptions)."""
    today = date.today()
    result = await self.session.execute(
        select(Subscription).where(
            Subscription.period_end < today,
            Subscription.status.in_([SubscriptionStatus.TRIAL.value, SubscriptionStatus.ACTIVE.value]),
            Subscription.is_lifetime == False,
        )
    )
    return list(result.scalars().all())
```

### 4. Переход в статус PAST_DUE

**Место в коде:** `src/worker/jobs.py:dunning_notifications()`

**Что происходит:**
1. Для каждой просроченной подписки:
   - Статус пары меняется на `PAST_DUE`
   - Обоим пользователям отправляется уведомление с кнопкой оплаты

**Код:**
```python
# src/worker/jobs.py:278-328
async def dunning_notifications(ctx: dict[str, Any]) -> None:
    """Send dunning notifications for past due subscriptions."""
    async with async_session_maker() as session:
        subs_repo = SubscriptionsRepository(session)
        pairs_repo = PairsRepository(session)
        
        past_due_subs = await subs_repo.get_past_due()
        
        for sub in past_due_subs:
            try:
                pair = await pairs_repo.get_by_id(sub.pair_id)
                if not pair:
                    continue
                
                # Update pair status
                await pairs_repo.update_status(pair.id, PairStatus.PAST_DUE)
                
                # Get users
                user_a_result = await session.execute(select(User).where(User.id == pair.uid_a))
                user_a = user_a_result.scalar_one()
                user_b_result = await session.execute(select(User).where(User.id == pair.uid_b))
                user_b = user_b_result.scalar_one()
                
                # Send notifications
                keyboard = {
                    "inline_keyboard": [
                        [
                            {
                                "text": "💳 Оплатить",
                                "callback_data": "pay_now",
                            },
                        ],
                    ],
                }
                
                await send_message_with_retry(
                    chat_id=user_a.tg_id,
                    text="⏳ Подписка просрочена. Оплатите для продолжения использования.",
                    reply_markup=keyboard,
                )
                await send_message_with_retry(
                    chat_id=user_b.tg_id,
                    text="⏳ Подписка просрочена. Оплатите для продолжения использования.",
                    reply_markup=keyboard,
                )
```

**Важно:** Статус подписки в таблице `subscriptions` НЕ меняется автоматически. Он остается `trial` или `active`, пока не будет обновлен через webhook при оплате.

### 5. Поведение системы после перехода в PAST_DUE

#### 5.1. Утренние и вечерние сообщения

**Место в коде:** `src/worker/jobs.py:morning_sender()`, `evening_sender()`

**Что происходит:**
- Пары со статусом `PAST_DUE` **НЕ получают** утренние и вечерние сообщения
- Причина: `get_active_pairs()` исключает пары со статусом `PAST_DUE`

**Код:**
```python
# src/worker/jobs.py:88
pairs = await pairs_repo.get_active_pairs()  # Не включает PAST_DUE
```

#### 5.2. Обработка callbacks (кнопки)

**Место в коде:** `src/bot/handlers/callbacks.py`

**Проблема:** В обработчиках callbacks **НЕТ проверки статуса пары**

**Что это означает:**
- Если пользователь нажимает старые кнопки (от сообщений, отправленных до окончания демо), они **все еще работают**
- Пользователь может отправить картинку партнеру, даже если подписка просрочена
- Это потенциальная уязвимость в бизнес-логике

**Примеры обработчиков без проверки статуса:**
- `handle_request_morning()` - отправка утреннего пожелания
- `handle_tap_morning()` - ответ на утреннее пожелание
- `handle_request_evening()` - отправка вечернего пожелания
- `handle_tap_evening()` - ответ на вечернее пожелание

**Рекомендация:** Добавить проверку статуса пары в начале каждого обработчика callback:

```python
if pair.status == PairStatus.PAST_DUE.value:
    await callback.answer(
        "⏳ Подписка просрочена. Оплатите для продолжения использования.",
        show_alert=True
    )
    return
```

#### 5.3. Команда /pay

**Место в коде:** `src/bot/handlers/pay.py`

**Что происходит:**
- Команда `/pay` доступна пользователям с просроченной подпиской
- Показывается список тарифов для оплаты
- После успешной оплаты через webhook статус меняется на `active`

**Код:**
```python
# src/bot/handlers/pay.py:90-95
if pair.status == PairStatus.ACTIVE.value:
    if subscription.is_lifetime:
        return False, "✅ Подписка активна навсегда", None
    period_end = subscription.period_end
    return False, f"✅ Подписка активна до {period_end.strftime('%d.%m.%Y')}", None

# Show tariffs
```

#### 5.4. Команда /subscription

**Место в коде:** `src/bot/handlers/subscription.py`

**Что происходит:**
- Команда показывает текущий статус подписки
- Для статуса `PAST_DUE` нет специальной обработки (используется fallback как для `trial`)

**Проблема:** Нет явного сообщения о просроченной подписке

**Рекомендация:** Добавить обработку статуса `PAST_DUE`:

```python
elif pair.status == PairStatus.PAST_DUE.value:
    text = (
        f"📊 <b>Подписка</b>\n\n"
        f"⏳ Подписка просрочена. Оплатите для продолжения использования."
    )
```

### 6. Восстановление после оплаты

**Место в коде:** `src/bot/handlers/webhook.py`

**Что происходит при успешной оплате:**
1. Webhook от YooKassa обрабатывает платеж
2. Подписка обновляется:
   - `status = 'active'`
   - `period_end` продлевается
   - `yoo_id` сохраняется
3. Статус пары меняется на `active`
4. Обоим пользователям отправляется уведомление об активации

**Код:**
```python
# src/bot/handlers/webhook.py:87-96
await subs_repo.update_payment(
    subscription_id=subscription.id,
    yoo_id=payment_id,
    period_end=period_end,
    is_lifetime=is_lifetime,
)

# Update pair status
await pairs_repo.update_status(pair.id, PairStatus.ACTIVE)
```

После этого пара снова начинает получать утренние и вечерние сообщения.

## Временная шкала событий

```
День 0: Создание пары
├─ status = 'trial'
├─ period_end = today + 7 дней
└─ Оба пользователя в user_demo

День 1-7: Демо период активен
├─ Утренние сообщения отправляются (07:30-08:30 UTC)
├─ Вечерние сообщения отправляются (21:30-22:30 UTC)
└─ Пользователи могут обмениваться картинками

День 8: Демо период истек
├─ 10:00 UTC: Задача dunning_notifications запускается
├─ Находит просроченные подписки (period_end < today)
├─ Статус пары меняется на 'past_due'
└─ Обоим пользователям отправляется уведомление с кнопкой оплаты

День 8+: После перехода в PAST_DUE
├─ Утренние/вечерние сообщения НЕ отправляются
├─ Старые кнопки все еще работают (ПРОБЛЕМА)
├─ Команда /pay доступна для оплаты
└─ После оплаты статус меняется на 'active', работа возобновляется
```

## Выявленные проблемы

### 1. Критическая: Отсутствие проверки статуса в callbacks

**Проблема:** Пользователи могут продолжать использовать бота после окончания демо периода через старые кнопки.

**Местоположение:** `src/bot/handlers/callbacks.py`

**Обработчики, требующие исправления:**
- `handle_request_morning()`
- `handle_tap_morning()`
- `handle_request_evening()`
- `handle_tap_evening()`

**Решение:** Добавить проверку статуса пары в начале каждого обработчика.

### 2. Средняя: Нет явного сообщения о просрочке в /subscription

**Проблема:** Команда `/subscription` не показывает явное сообщение о просроченной подписке.

**Местоположение:** `src/bot/handlers/subscription.py`

**Решение:** Добавить обработку статуса `PAST_DUE`.

### 3. Низкая: Статус подписки не синхронизируется автоматически

**Проблема:** Статус в таблице `subscriptions` остается `trial` или `active`, даже когда пара перешла в `PAST_DUE`.

**Примечание:** Это может быть намеренным решением, так как статус подписки обновляется только при оплате через webhook.

## Рекомендации

1. **Добавить проверку статуса в callbacks** - критично для бизнес-логики
2. **Улучшить обработку статуса PAST_DUE в команде /subscription**
3. **Рассмотреть синхронизацию статусов** между `pairs` и `subscriptions`
4. **Добавить логирование** переходов статусов для мониторинга
5. **Добавить тесты** для проверки поведения при окончании демо периода

## Связанные файлы

- `src/bot/handlers/start.py` - создание пары и демо периода
- `src/bot/handlers/callbacks.py` - обработка кнопок (требует исправления)
- `src/bot/handlers/pay.py` - команда оплаты
- `src/bot/handlers/subscription.py` - команда статуса (требует улучшения)
- `src/bot/handlers/webhook.py` - обработка платежей
- `src/worker/jobs.py` - фоновые задачи (dunning_notifications, morning_sender, evening_sender)
- `src/db/repositories/pairs.py` - репозиторий пар
- `src/db/repositories/subscriptions.py` - репозиторий подписок
- `src/core/constants.py` - константы статусов
