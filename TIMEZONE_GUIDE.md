# Руководство по часовым поясам (UTC Offset)

## Формат `utc_offset` в базе данных

Поле `utc_offset` в таблице `users` хранится как **целое число (integer)**, означающее разницу с UTC в часах.

### Примеры значений:

| Часовой пояс | UTC Offset | Пример города |
|--------------|------------|---------------|
| UTC+3        | `3`        | Москва, Киев, Минск |
| UTC+2        | `2`        | Калининград |
| UTC+5        | `5`        | Екатеринбург |
| UTC+8        | `8`        | Иркутск, Пекин |
| UTC+0        | `0`        | Лондон (зима) |
| UTC-5        | `-5`       | Нью-Йорк (зима) |
| UTC-8        | `-8`       | Лос-Анджелес (зима) |
| UTC+9        | `9`        | Токио, Сеул |

### По умолчанию

Если пользователь не указал свой часовой пояс, используется значение `3` (UTC+3, Москва).

## Проверка текущих значений в БД

### Через SQL:

```sql
-- Посмотреть всех пользователей с их часовыми поясами
SELECT tg_id, username, utc_offset, 
       CONCAT('UTC', CASE WHEN utc_offset >= 0 THEN '+' ELSE '' END, utc_offset) as timezone
FROM users
ORDER BY utc_offset, tg_id;

-- Найти пользователей с неправильным часовым поясом (например, все с дефолтным значением)
SELECT tg_id, username, utc_offset 
FROM users 
WHERE utc_offset = 3;  -- Все с дефолтным значением Москвы
```

### Через Python скрипт:

```python
import asyncio
from src.core.database import get_async_session
from src.db.models import User
from sqlalchemy import select

async def check_timezones():
    async for session in get_async_session():
        result = await session.execute(select(User))
        users = result.scalars().all()
        
        print("Пользователи и их часовые пояса:")
        for user in users:
            tz_str = f"UTC{'+' if user.utc_offset >= 0 else ''}{user.utc_offset}"
            print(f"  tg_id={user.tg_id}, username={user.username}, offset={user.utc_offset} ({tz_str})")
        
        await session.close()
        break

asyncio.run(check_timezones())
```

## Обновление часового пояса

### Через SQL:

```sql
-- Установить часовой пояс для конкретного пользователя
UPDATE users SET utc_offset = 3 WHERE tg_id = 123456789;  -- Москва (UTC+3)
UPDATE users SET utc_offset = -5 WHERE tg_id = 987654321;  -- Нью-Йорк (UTC-5)

-- Установить для всех пользователей (если нужно)
UPDATE users SET utc_offset = 3 WHERE utc_offset IS NULL OR utc_offset = 0;
```

### Через Python:

```python
from src.core.database import get_async_session
from src.db.repositories.users import UsersRepository

async def update_timezone(tg_id: int, utc_offset: int):
    async for session in get_async_session():
        users_repo = UsersRepository(session)
        user = await users_repo.update_utc_offset(tg_id, utc_offset)
        await session.commit()
        print(f"Часовой пояс обновлен: UTC{'+' if utc_offset >= 0 else ''}{utc_offset}")
        await session.close()
        break

# Пример: установить Москву для пользователя
# await update_timezone(123456789, 3)
```

## Автоматическое определение часового пояса

Бот синхронизирует часовой пояс **с системных настроек телефона** через Mini App (WebView Telegram).

### Как это работает

1. Пользователь отправляет **`/start`**
2. Бот показывает кнопку **«🚀 Продолжить»** (Mini App)
3. При нажатии Mini App читает часовой пояс телефона и сохраняет в БД:
   - `timezone_name` — IANA-имя (например `Europe/Moscow`)
   - `utc_offset` — смещение UTC в часах
4. После синхронизации бот продолжает обычный сценарий `/start`

### Смена часового пояса (переезд, путешествие)

Пользователю достаточно снова отправить **`/start`** и нажать **«🚀 Продолжить»**.  
Отдельной настройки часового пояса в меню нет.

### Ограничения

- Синхронизация **не происходит автоматически** при доставке утреннего/вечернего запроса — только при `/start`
- IP-определение (`TIMEZONE_DETECT_FROM_IP_ENABLED`) ненадёжно в webhook-режиме и не используется как основной способ
- `MINI_APP_URL` в `.env` должен быть публичным **HTTPS**-адресом Mini App сервера

### Проверка в БД

```sql
SELECT tg_id, username, utc_offset, timezone_name FROM users;
```
