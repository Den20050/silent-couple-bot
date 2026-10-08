# Объяснение: "Бот отправляет картинку только один раз в день"

## Как это работает

### Логика проверки

Бот проверяет, была ли картинка отправлена **сегодня** (по дате, а не по времени):

```python
today = date.today()  # Например: 2025-12-13
daily_state = await daily_state_repo.get_or_create(pair.id, today)

# Проверка: если картинка уже отправлена сегодня - пропускаем
if daily_state.morning_initiator is not None or daily_state.morning_sent_at is not None:
    logger.info("Morning message already sent today, skipping")
    continue  # НЕ отправляем снова
```

### Что это означает на практике

**Пример 1: Картинка отправлена утром**
- Время отправки: `13:00:13` (UTC) = `16:00:13` (локальное время, UTC+3)
- Дата: `2025-12-13`
- Что происходит:
  - ✅ Картинка отправлена в 16:00
  - ❌ Если вы измените время в `.env` на `21:20` и перезапустите бота в 21:20 - картинка **НЕ отправится снова**
  - ✅ Картинка отправится только **на следующий день** (2025-12-14), когда `date.today()` изменится

**Пример 2: Изменение времени в середине дня**
- Текущее время: `15:00` (13 декабря)
- Картинка уже отправлена сегодня в `16:00`
- Вы изменяете `.env`: `MORNING_START=15:30`
- Вы перезапускаете бота
- Что происходит:
  - ❌ В 15:30 картинка **НЕ отправится**, потому что `morning_sent_at` уже установлен для сегодняшнего дня
  - ✅ Картинка отправится только **завтра** (14 декабря) в новое время (15:30)

## Структура данных

В базе данных есть таблица `daily_state`:

```sql
CREATE TABLE daily_state (
    pair_id BIGINT,
    day DATE,  -- Дата (например, 2025-12-13)
    morning_initiator BIGINT,  -- Кто отправил утреннюю картинку
    morning_sent_at TIMESTAMP, -- Когда была отправлена картинка
    morning_file_id TEXT,     -- ID картинки
    ...
    PRIMARY KEY (pair_id, day)
);
```

**Важно:** Ключ состоит из `pair_id` + `day` (дата), поэтому для каждого дня создается отдельная запись.

## Как обойти для тестирования

Если вы хотите протестировать отправку картинок несколько раз в один день, нужно очистить `daily_state` для сегодняшнего дня:

### Вариант 1: SQL запрос

```sql
-- Очистить утреннюю картинку для пары #4 на сегодня
UPDATE daily_state 
SET 
    morning_initiator = NULL, 
    morning_sent_at = NULL, 
    morning_file_id = NULL,
    morning_responded_at = NULL
WHERE pair_id = 4 AND day = CURRENT_DATE;

-- Очистить вечернюю картинку
UPDATE daily_state 
SET 
    evening_initiator = NULL, 
    evening_sent_at = NULL, 
    evening_file_id = NULL,
    evening_responded_at = NULL
WHERE pair_id = 4 AND day = CURRENT_DATE;
```

### Вариант 2: Удалить запись полностью

```sql
-- Удалить всю запись для сегодняшнего дня
DELETE FROM daily_state 
WHERE pair_id = 4 AND day = CURRENT_DATE;
```

### Вариант 3: Использовать скрипт (можно создать)

Можно создать скрипт `scripts/reset_daily_state.py`:

```python
"""Сбросить daily_state для пары на сегодняшний день."""

import asyncio
from datetime import date
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.db.base import async_session_maker
from src.db.models import DailyState
from sqlalchemy import select, update


async def reset_daily_state(pair_id: int, reset_morning: bool = True, reset_evening: bool = True):
    """Сбросить daily_state для пары на сегодня."""
    today = date.today()
    
    async with async_session_maker() as session:
        # Получить запись
        result = await session.execute(
            select(DailyState).where(
                DailyState.pair_id == pair_id,
                DailyState.day == today
            )
        )
        daily_state = result.scalar_one_or_none()
        
        if not daily_state:
            print(f"✅ Запись для пары {pair_id} на {today} не найдена (можно тестировать)")
            return
        
        # Сбросить поля
        if reset_morning:
            daily_state.morning_initiator = None
            daily_state.morning_sent_at = None
            daily_state.morning_file_id = None
            daily_state.morning_responded_at = None
        
        if reset_evening:
            daily_state.evening_initiator = None
            daily_state.evening_sent_at = None
            daily_state.evening_file_id = None
            daily_state.evening_responded_at = None
        
        await session.commit()
        print(f"✅ Daily state сброшен для пары {pair_id} на {today}")


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Использование: python scripts/reset_daily_state.py <pair_id> [morning|evening|both]")
        sys.exit(1)
    
    pair_id = int(sys.argv[1])
    reset_type = sys.argv[2] if len(sys.argv) > 2 else "both"
    
    reset_morning = reset_type in ["morning", "both"]
    reset_evening = reset_type in ["evening", "both"]
    
    asyncio.run(reset_daily_state(pair_id, reset_morning, reset_evening))
```

## Резюме

**"Один раз в день" означает:**
- ✅ Бот отправляет картинку **максимум один раз в сутки** для каждой пары
- ✅ Проверка идет по **дате** (дню), а не по времени
- ✅ Если картинка уже отправлена сегодня, она **не отправится снова** в этот же день, даже если вы измените время в `.env`
- ✅ Картинка отправится только **на следующий день** в новое время

**Для тестирования:**
- Очистите `daily_state` для сегодняшнего дня (см. варианты выше)
- ИЛИ дождитесь следующего дня
- ИЛИ используйте скрипт для автоматического сброса
