"""Script to cleanup all user data from database."""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from src.core.config import settings
from src.core.logger import configure_logging, get_logger
from src.db.models import DailyState, Pair, Subscription, User, UserDemo

logger = get_logger(__name__)

# Create engine
engine = create_async_engine(settings.database_url, echo=False)
async_session_maker = async_sessionmaker(engine, expire_on_commit=False)


async def cleanup_all_users() -> None:
    """Cleanup all user data from database."""
    configure_logging(settings.log_level)
    
    async with async_session_maker() as session:
        # Count current records
        users_count = await session.execute(select(func.count(User.id)))
        pairs_count = await session.execute(select(func.count(Pair.id)))
        subscriptions_count = await session.execute(select(func.count(Subscription.id)))
        daily_states_count = await session.execute(select(func.count(DailyState.pair_id)))
        user_demo_count = await session.execute(select(func.count(UserDemo.tg_id)))
        
        users_total = users_count.scalar() or 0
        pairs_total = pairs_count.scalar() or 0
        subscriptions_total = subscriptions_count.scalar() or 0
        daily_states_total = daily_states_count.scalar() or 0
        user_demo_total = user_demo_count.scalar() or 0
        
        print(f"\n📊 Текущее состояние БД:")
        print(f"   Пользователей: {users_total}")
        print(f"   Пар: {pairs_total}")
        print(f"   Подписок: {subscriptions_total}")
        print(f"   Состояний дня: {daily_states_total}")
        print(f"   Демо записей: {user_demo_total}")
        
        if users_total == 0:
            print(f"\n✅ БД уже пуста. Очистка не требуется.")
            await engine.dispose()
            return
        
        # Ask for confirmation
        print(f"\n⚠️  ВНИМАНИЕ: Будут удалены ВСЕ пользовательские данные!")
        print(f"   Это включает:")
        print(f"   - Всех пользователей")
        print(f"   - Все пары")
        print(f"   - Все подписки")
        print(f"   - Все состояния дня")
        print(f"   - Все демо записи")
        print(f"\n   ⚠️  Картинки (pics_pool) НЕ будут удалены!")
        print(f"\n   Продолжить? (yes/no): ", end="")
        
        confirmation = input().strip().lower()
        if confirmation != "yes":
            print("❌ Очистка отменена.")
            await engine.dispose()
            return
        
        print(f"\n🗑️  Удаление данных...")
        
        # Delete in correct order (respecting foreign keys)
        # 1. Daily states (references pairs)
        stmt = delete(DailyState)
        result = await session.execute(stmt)
        daily_states_deleted = result.rowcount or 0
        print(f"   Удалено состояний дня: {daily_states_deleted}")
        
        # 2. Subscriptions (references pairs)
        stmt = delete(Subscription)
        result = await session.execute(stmt)
        subscriptions_deleted = result.rowcount or 0
        print(f"   Удалено подписок: {subscriptions_deleted}")
        
        # 3. Pairs (references users)
        stmt = delete(Pair)
        result = await session.execute(stmt)
        pairs_deleted = result.rowcount or 0
        print(f"   Удалено пар: {pairs_deleted}")
        
        # 4. User demo (references users by tg_id, but tg_id is not FK)
        stmt = delete(UserDemo)
        result = await session.execute(stmt)
        user_demo_deleted = result.rowcount or 0
        print(f"   Удалено демо записей: {user_demo_deleted}")
        
        # 5. Users (last, as other tables reference it)
        stmt = delete(User)
        result = await session.execute(stmt)
        users_deleted = result.rowcount or 0
        print(f"   Удалено пользователей: {users_deleted}")
        
        await session.commit()
        
        print(f"\n✅ Очистка завершена!")
        print(f"   Всего удалено:")
        print(f"   - Пользователей: {users_deleted}")
        print(f"   - Пар: {pairs_deleted}")
        print(f"   - Подписок: {subscriptions_deleted}")
        print(f"   - Состояний дня: {daily_states_deleted}")
        print(f"   - Демо записей: {user_demo_deleted}")
        
        # Verify
        users_count_after = await session.execute(select(func.count(User.id)))
        pairs_count_after = await session.execute(select(func.count(Pair.id)))
        users_after = users_count_after.scalar() or 0
        pairs_after = pairs_count_after.scalar() or 0
        
        print(f"\n📊 Результат:")
        print(f"   Пользователей в БД: {users_after}")
        print(f"   Пар в БД: {pairs_after}")
        
        if users_after == 0 and pairs_after == 0:
            print(f"\n✅ Все пользовательские данные успешно удалены!")
            print(f"   Картинки (pics_pool) сохранены и готовы к использованию.")
        else:
            print(f"⚠️  Осталось данных. Возможно, произошла ошибка.")
    
    await engine.dispose()


if __name__ == "__main__":
    import asyncio
    asyncio.run(cleanup_all_users())

