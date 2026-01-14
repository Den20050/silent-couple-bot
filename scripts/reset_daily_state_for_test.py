"""Reset daily state for testing purposes."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from datetime import date
from sqlalchemy import select
from src.core.config import settings
from src.core.logger import configure_logging, get_logger
from src.db.base import async_session_maker
from src.db.models import DailyState, Pair, User

logger = get_logger(__name__)
configure_logging(settings.log_level)


async def reset_daily_state_for_pair(pair_id: int) -> None:
    """Reset daily state for a specific pair (for testing)."""
    async with async_session_maker() as session:
        # Get pair
        result = await session.execute(
            select(Pair).where(Pair.id == pair_id)
        )
        pair = result.scalar_one_or_none()
        
        if not pair:
            print(f"❌ Пара с ID {pair_id} не найдена")
            return
        
        # Get users
        user_a_result = await session.execute(
            select(User).where(User.id == pair.uid_a)
        )
        user_a = user_a_result.scalar_one()
        
        user_b_result = await session.execute(
            select(User).where(User.id == pair.uid_b)
        )
        user_b = user_b_result.scalar_one()
        
        print(f"📋 Пара ID: {pair_id}")
        print(f"   Пользователь A: {user_a.tg_id}")
        print(f"   Пользователь B: {user_b.tg_id}")
        print()
        
        # Get today's daily state
        today = date.today()
        result = await session.execute(
            select(DailyState).where(
                DailyState.pair_id == pair_id,
                DailyState.day == today,
            )
        )
        daily_state = result.scalar_one_or_none()
        
        if not daily_state:
            print(f"✅ Daily state для сегодня не найдена (ничего не отправлялось)")
            return
        
        # Show current state
        print("📊 Текущее состояние:")
        print(f"   Утренний инициатор: {daily_state.morning_initiator}")
        print(f"   Утренняя отправка: {daily_state.morning_sent_at}")
        print(f"   Утренний ответ: {daily_state.morning_responded_at}")
        print(f"   Вечерний инициатор: {daily_state.evening_initiator}")
        print(f"   Вечерняя отправка: {daily_state.evening_sent_at}")
        print(f"   Вечерний ответ: {daily_state.evening_responded_at}")
        print()
        
        # Reset morning state
        daily_state.morning_initiator = None
        daily_state.morning_sent_at = None
        daily_state.morning_responded_at = None
        daily_state.morning_file_id = None
        
        # Reset evening state
        daily_state.evening_initiator = None
        daily_state.evening_sent_at = None
        daily_state.evening_responded_at = None
        daily_state.evening_file_id = None
        
        await session.commit()
        
        print("✅ Daily state сброшена!")
        print("   Теперь можно протестировать отправку картинок снова")


async def reset_all_pairs() -> None:
    """Reset daily state for all active pairs."""
    async with async_session_maker() as session:
        # Get all active pairs
        from src.db.repositories.pairs import PairsRepository
        pairs_repo = PairsRepository(session)
        pairs = await pairs_repo.get_active_pairs()
        
        print(f"📋 Найдено активных пар: {len(pairs)}")
        print()
        
        today = date.today()
        reset_count = 0
        
        for pair in pairs:
            # Get today's daily state
            result = await session.execute(
                select(DailyState).where(
                    DailyState.pair_id == pair.id,
                    DailyState.day == today,
                )
            )
            daily_state = result.scalar_one_or_none()
            
            if daily_state:
                # Reset morning state
                daily_state.morning_initiator = None
                daily_state.morning_sent_at = None
                daily_state.morning_responded_at = None
                daily_state.morning_file_id = None
                
                # Reset evening state
                daily_state.evening_initiator = None
                daily_state.evening_sent_at = None
                daily_state.evening_responded_at = None
                daily_state.evening_file_id = None
                
                reset_count += 1
        
        await session.commit()
        
        print(f"✅ Сброшено daily state для {reset_count} пар")


async def main() -> None:
    """Main entry point."""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--all":
            # Reset all pairs
            await reset_all_pairs()
        else:
            # Reset specific pair
            try:
                pair_id = int(sys.argv[1])
                await reset_daily_state_for_pair(pair_id)
            except ValueError:
                print("❌ Неверный формат. Используйте: python scripts/reset_daily_state_for_test.py <pair_id>")
                print("   Или: python scripts/reset_daily_state_for_test.py --all")
    else:
        print("📋 Сброс daily state для тестирования")
        print()
        print("Использование:")
        print("  python scripts/reset_daily_state_for_test.py <pair_id>  - сбросить для конкретной пары")
        print("  python scripts/reset_daily_state_for_test.py --all      - сбросить для всех активных пар")
        print()
        print("Пример:")
        print("  python scripts/reset_daily_state_for_test.py 1")
        print("  python scripts/reset_daily_state_for_test.py --all")


if __name__ == "__main__":
    asyncio.run(main())
