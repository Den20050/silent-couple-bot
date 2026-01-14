"""Script to check morning time configuration and active pairs."""

import asyncio
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from src.core.config import settings
from src.core.constants import MORNING_WINDOW_START, MORNING_WINDOW_END, PairStatus
from src.db.models import Pair, User


async def main():
    """Check morning time configuration and active pairs."""
    print("=" * 60)
    print("Проверка конфигурации времени утренних сообщений")
    print("=" * 60)
    
    # Check config
    print(f"\n📋 Конфигурация из .env:")
    print(f"  MORNING_START={settings.morning_start}")
    print(f"  MORNING_END={settings.morning_end}")
    print(f"\n⏰ Временные окна (объекты time):")
    print(f"  MORNING_WINDOW_START={MORNING_WINDOW_START}")
    print(f"  MORNING_WINDOW_END={MORNING_WINDOW_END}")
    
    # Check current time
    now_utc = datetime.utcnow()
    print(f"\n🌍 Текущее время UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Connect to database
    engine = create_async_engine(settings.database_url, echo=False)
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)
    
    async with async_session_maker() as session:
        # Get all pairs
        all_pairs_result = await session.execute(select(Pair))
        all_pairs = list(all_pairs_result.scalars().all())
        
        print(f"\n📊 Всего пар в базе: {len(all_pairs)}")
        
        # Get active pairs
        active_pairs_result = await session.execute(
            select(Pair).where(
                Pair.status.in_([PairStatus.TRIAL.value, PairStatus.ACTIVE.value])
            )
        )
        active_pairs = list(active_pairs_result.scalars().all())
        
        print(f"✅ Активных пар (trial/active): {len(active_pairs)}")
        
        if len(active_pairs) == 0:
            print("\n⚠️  ПРОБЛЕМА: Нет активных пар!")
            print("   Проверьте статусы пар в базе данных.")
            
            # Show status breakdown
            status_counts = {}
            for pair in all_pairs:
                status = pair.status
                status_counts[status] = status_counts.get(status, 0) + 1
            
            print("\n📈 Распределение по статусам:")
            for status, count in status_counts.items():
                print(f"   {status}: {count}")
        else:
            print(f"\n👥 Проверка временных окон для активных пар:")
            
            for pair in active_pairs[:5]:  # Show first 5 pairs
                # Get users
                user_a_result = await session.execute(
                    select(User).where(User.id == pair.uid_a)
                )
                user_a = user_a_result.scalar_one()
                
                user_b_result = await session.execute(
                    select(User).where(User.id == pair.uid_b)
                )
                user_b = user_b_result.scalar_one()
                
                # Calculate local times
                local_dt_a = now_utc + timedelta(hours=user_a.utc_offset)
                local_time_obj_a = local_dt_a.time()
                
                local_dt_b = now_utc + timedelta(hours=user_b.utc_offset)
                local_time_obj_b = local_dt_b.time()
                
                # Check if in window
                user_a_in_window = MORNING_WINDOW_START <= local_time_obj_a < MORNING_WINDOW_END
                user_b_in_window = MORNING_WINDOW_START <= local_time_obj_b < MORNING_WINDOW_END
                
                print(f"\n  Пара ID {pair.id}:")
                print(f"    Пользователь A (ID {user_a.tg_id}):")
                print(f"      UTC offset: {user_a.utc_offset}")
                print(f"      Локальное время: {local_time_obj_a}")
                print(f"      В окне: {'✅' if user_a_in_window else '❌'}")
                print(f"    Пользователь B (ID {user_b.tg_id}):")
                print(f"      UTC offset: {user_b.utc_offset}")
                print(f"      Локальное время: {local_time_obj_b}")
                print(f"      В окне: {'✅' if user_b_in_window else '❌'}")
                print(f"    Отправить сообщение: {'✅ ДА' if (user_a_in_window or user_b_in_window) else '❌ НЕТ'}")
    
    await engine.dispose()
    
    print("\n" + "=" * 60)
    print("💡 Рекомендации:")
    print("   1. Убедитесь, что worker перезапущен после изменения .env")
    print("   2. Проверьте, что есть активные пары (status = 'trial' или 'active')")
    print("   3. Проверьте UTC offset пользователей (должен быть установлен при /start)")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
