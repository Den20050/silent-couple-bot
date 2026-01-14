"""Проверка подписок для пар."""

import asyncio
from datetime import date

from src.core.bootstrap import bootstrap


async def check_subscriptions():
    """Проверить подписки для всех пар."""
    container = await bootstrap()
    
    today = date.today()
    
    print("=" * 60)
    print("ПРОВЕРКА ПОДПИСОК")
    print("=" * 60)
    print()
    print(f"Сегодня: {today}")
    print()
    
    async with container.session_factory() as session:
        from sqlalchemy import select
        from src.db.models import Pair, Subscription
        
        # Получить все пары
        pairs_result = await session.execute(select(Pair))
        all_pairs = pairs_result.scalars().all()
        
        print(f"Всего пар: {len(all_pairs)}")
        print()
        
        for pair in all_pairs:
            print(f"Пара ID: {pair.id}")
            print(f"  Статус пары: {pair.status}")
            
            # Получить подписку
            sub_result = await session.execute(
                select(Subscription).where(Subscription.pair_id == pair.id)
            )
            subscription = sub_result.scalar_one_or_none()
            
            if subscription:
                print(f"  Подписка ID: {subscription.id}")
                print(f"  Статус подписки: {subscription.status}")
                print(f"  Создана: {subscription.created_at.date()}")
                print(f"  Окончание периода: {subscription.period_end}")
                print(f"  Lifetime: {subscription.is_lifetime}")
                
                days_since_expiry = (today - subscription.period_end).days
                if subscription.period_end < today:
                    print(f"  ⚠️  Просрочена на {days_since_expiry} дней")
                else:
                    days_left = (subscription.period_end - today).days
                    print(f"  ✅ Дней осталось: {days_left}")
            else:
                print(f"  ⚠️  Подписка не найдена!")
            
            print()


if __name__ == "__main__":
    asyncio.run(check_subscriptions())
