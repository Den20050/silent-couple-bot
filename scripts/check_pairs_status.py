"""Проверка статуса всех пар в базе данных."""

import asyncio
from datetime import date, datetime

from src.core.bootstrap import bootstrap
from src.core.config import settings
from src.worker.services.time_window_service import TimeWindowService


async def check_pairs_status():
    """Проверить статус всех пар."""
    container = await bootstrap()
    
    now_utc = datetime.utcnow()
    today = date.today()
    
    print("=" * 60)
    print("ПРОВЕРКА ВСЕХ ПАР В БАЗЕ ДАННЫХ")
    print("=" * 60)
    print()
    
    async with container.session_factory() as session:
        from sqlalchemy import select
        from src.db.models import Pair, User
        
        # Получить ВСЕ пары
        pairs_result = await session.execute(select(Pair))
        all_pairs = pairs_result.scalars().all()
        
        print(f"Всего пар в базе: {len(all_pairs)}")
        print()
        
        if not all_pairs:
            print("⚠️  Нет пар в базе данных")
            return
        
        # Статистика по статусам
        status_counts = {}
        for pair in all_pairs:
            status_counts[pair.status] = status_counts.get(pair.status, 0) + 1
        
        print("Статистика по статусам:")
        for status, count in status_counts.items():
            print(f"  {status}: {count}")
        print()
        
        # Показать все пары
        for pair in all_pairs:
            print(f"Пара ID: {pair.id}")
            print(f"  Статус: {pair.status}")
            print(f"  Режим: {pair.mode}")
            print(f"  UID A: {pair.uid_a}")
            print(f"  UID B: {pair.uid_b}")
            print(f"  Создана: {pair.created_at}")
            print(f"  Обновлена: {pair.updated_at}")
            
            # Получить пользователей
            try:
                user_a_result = await session.execute(
                    select(User).where(User.id == pair.uid_a)
                )
                user_a = user_a_result.scalar_one()
                
                user_b_result = await session.execute(
                    select(User).where(User.id == pair.uid_b)
                )
                user_b = user_b_result.scalar_one()
                
                print(f"  Пользователь A: {user_a.tg_id} (UTC offset: {user_a.utc_offset})")
                print(f"  Пользователь B: {user_b.tg_id} (UTC offset: {user_b.utc_offset})")
                
                # Проверить локальное время пользователей
                user_a_local_time = TimeWindowService.get_user_local_time(now_utc, user_a.utc_offset)
                user_b_local_time = TimeWindowService.get_user_local_time(now_utc, user_b.utc_offset)
                
                user_a_in_window = TimeWindowService.is_in_evening_window(user_a_local_time)
                user_b_in_window = TimeWindowService.is_in_evening_window(user_b_local_time)
                
                print(f"  Локальное время A: {user_a_local_time} - {'✅ В окне' if user_a_in_window else '❌ Не в окне'}")
                print(f"  Локальное время B: {user_b_local_time} - {'✅ В окне' if user_b_in_window else '❌ Не в окне'}")
                
            except Exception as e:
                print(f"  ⚠️  Ошибка при получении пользователей: {e}")
            
            print()
        
        print("=" * 60)
        print("ПРОВЕРКА: Какие пары считаются 'активными'?")
        print("=" * 60)
        print()
        print("Код ищет пары со статусом: 'trial' или 'active'")
        print()
        
        active_pairs = [p for p in all_pairs if p.status in ('trial', 'active')]
        print(f"Найдено активных пар: {len(active_pairs)}")
        
        if active_pairs:
            print("Активные пары:")
            for pair in active_pairs:
                print(f"  - Пара ID: {pair.id}, статус: {pair.status}")
        else:
            print("⚠️  Нет пар со статусом 'trial' или 'active'")
            print()
            print("Возможные причины:")
            print("  1. Пары имеют другой статус (например, 'past_due')")
            print("  2. Пары были удалены или деактивированы")
            print("  3. Проблема с подключением к базе данных")


if __name__ == "__main__":
    asyncio.run(check_pairs_status())
