"""Проверка статуса вечерней отправки сообщений."""

import asyncio
from datetime import date, datetime

from src.core.bootstrap import bootstrap
from src.core.config import settings
from src.db.repositories.daily_state import DailyStateRepository
from src.db.repositories.pairs import PairsRepository
from src.worker.services.time_window_service import TimeWindowService


async def check_evening_status():
    """Проверить статус вечерней отправки."""
    container = await bootstrap()
    
    now_utc = datetime.utcnow()
    today = date.today()
    
    print("=" * 60)
    print("ПРОВЕРКА СТАТУСА ВЕЧЕРНЕЙ ОТПРАВКИ")
    print("=" * 60)
    print()
    print(f"Текущее время UTC: {now_utc}")
    print(f"Текущее время MSK (UTC+3): {datetime.now()}")
    print()
    print(f"Вечернее окно: {settings.evening_start} - {settings.evening_end}")
    print(f"  (по локальному времени пользователя)")
    print()
    
    async with container.session_factory() as session:
        pairs_repo = PairsRepository(session)
        daily_state_repo = DailyStateRepository(session)
        
        # Получить активные пары
        pairs = await pairs_repo.get_active_pairs()
        print(f"Активных пар: {len(pairs)}")
        print()
        
        if not pairs:
            print("⚠️  Нет активных пар - вечерние сообщения не будут отправлены")
            return
        
        from sqlalchemy import select
        from src.db.models import User
        
        for pair in pairs:
            print(f"Пара ID: {pair.id}")
            print(f"  Статус: {pair.status}")
            print(f"  Режим: {pair.mode}")
            
            # Получить пользователей
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
            
            # Проверить daily_state
            daily_state = await daily_state_repo.get_or_create(pair.id, today)
            
            if daily_state.evening_initiator is not None:
                print(f"  ⚠️  Вечернее сообщение УЖЕ отправлено сегодня")
                print(f"     Инициатор: {daily_state.evening_initiator}")
                print(f"     Отправлено: {daily_state.evening_sent_at}")
            else:
                print(f"  ✅ Вечернее сообщение ЕЩЕ НЕ отправлено сегодня")
                
                if user_a_in_window or user_b_in_window:
                    print(f"  ✅ Будет отправлено при следующем запуске worker (если worker запущен)")
                else:
                    print(f"  ⚠️  НЕ будет отправлено - ни один пользователь не в окне")
            
            print()
        
        print("=" * 60)
        print("ВЫВОД:")
        print("=" * 60)
        print()
        print("Worker запускается каждую минуту и проверяет:")
        print("  1. Есть ли активные пары")
        print("  2. Находится ли хотя бы один пользователь в паре в вечернем окне")
        print("  3. Было ли уже отправлено вечернее сообщение сегодня")
        print()
        print("Если все условия выполнены - отправляется запрос на пожелание.")
        print()
        print(f"Окно открыто до {settings.evening_end} по локальному времени пользователя.")
        print("После этого времени вечерние сообщения не будут отправлены до завтра.")


if __name__ == "__main__":
    asyncio.run(check_evening_status())
