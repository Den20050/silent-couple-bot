"""Сбросить daily_state для пары на сегодняшний день.

Этот скрипт позволяет очистить запись о отправленных картинках для пары,
чтобы можно было протестировать отправку картинок несколько раз в один день.

Использование:
    python scripts/reset_daily_state.py <pair_id> [morning|evening|both]
    
Примеры:
    python scripts/reset_daily_state.py 4 both          # Сбросить утренние и вечерние
    python scripts/reset_daily_state.py 4 morning       # Сбросить только утренние
    python scripts/reset_daily_state.py 4 evening      # Сбросить только вечерние
"""

import asyncio
import sys
from datetime import date
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.db.base import async_session_maker
from src.db.models import DailyState
from sqlalchemy import select


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
            print(f"✅ Запись для пары {pair_id} на {today} не найдена")
            print(f"   Можно тестировать отправку картинок")
            return
        
        print(f"📋 Найдена запись для пары {pair_id} на {today}:")
        print(f"   Утренняя картинка: initiator={daily_state.morning_initiator}, sent_at={daily_state.morning_sent_at}")
        print(f"   Вечерняя картинка: initiator={daily_state.evening_initiator}, sent_at={daily_state.evening_sent_at}")
        print()
        
        # Сбросить поля
        if reset_morning:
            daily_state.morning_initiator = None
            daily_state.morning_sent_at = None
            daily_state.morning_file_id = None
            daily_state.morning_responded_at = None
            print(f"   ✅ Утренние данные сброшены")
        
        if reset_evening:
            daily_state.evening_initiator = None
            daily_state.evening_sent_at = None
            daily_state.evening_file_id = None
            daily_state.evening_responded_at = None
            print(f"   ✅ Вечерние данные сброшены")
        
        await session.commit()
        print()
        print(f"✅ Daily state успешно сброшен для пары {pair_id} на {today}")
        print(f"   Теперь можно тестировать отправку картинок")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("=" * 70)
        print("СБРОС DAILY_STATE ДЛЯ ТЕСТИРОВАНИЯ")
        print("=" * 70)
        print()
        print("Использование:")
        print("  python scripts/reset_daily_state.py <pair_id> [morning|evening|both]")
        print()
        print("Примеры:")
        print("  python scripts/reset_daily_state.py 4 both          # Сбросить утренние и вечерние")
        print("  python scripts/reset_daily_state.py 4 morning       # Сбросить только утренние")
        print("  python scripts/reset_daily_state.py 4 evening      # Сбросить только вечерние")
        print()
        print("=" * 70)
        sys.exit(1)
    
    try:
        pair_id = int(sys.argv[1])
    except ValueError:
        print(f"❌ Ошибка: pair_id должен быть числом, получено: {sys.argv[1]}")
        sys.exit(1)
    
    reset_type = sys.argv[2] if len(sys.argv) > 2 else "both"
    
    if reset_type not in ["morning", "evening", "both"]:
        print(f"❌ Ошибка: тип должен быть 'morning', 'evening' или 'both', получено: {reset_type}")
        sys.exit(1)
    
    reset_morning = reset_type in ["morning", "both"]
    reset_evening = reset_type in ["evening", "both"]
    
    try:
        asyncio.run(reset_daily_state(pair_id, reset_morning, reset_evening))
    except Exception as e:
        print(f"❌ Ошибка: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
