"""Восстановление статуса past_due для пар с истекшими подписками."""

import asyncio
from datetime import date

from src.core.bootstrap import bootstrap
from src.core.constants import PairStatus, SubscriptionStatus


async def restore_past_due_status():
    """Вернуть пары с истекшими подписками в статус past_due."""
    container = await bootstrap()
    
    today = date.today()
    
    print("=" * 60)
    print("ВОССТАНОВЛЕНИЕ СТАТУСА PAST_DUE")
    print("=" * 60)
    print()
    print(f"Сегодня: {today}")
    print()
    
    async with container.session_factory() as session:
        from sqlalchemy import select
        from src.db.models import Pair, Subscription
        from src.db.repositories.pairs import PairsRepository
        from src.db.repositories.subscriptions import SubscriptionsRepository
        
        pairs_repo = PairsRepository(session)
        subs_repo = SubscriptionsRepository(session)
        
        # Получить все пары
        pairs_result = await session.execute(select(Pair))
        all_pairs = pairs_result.scalars().all()
        
        print(f"Всего пар: {len(all_pairs)}")
        print()
        
        for pair in all_pairs:
            print(f"Пара ID: {pair.id}")
            print(f"  Текущий статус: {pair.status}")
            
            # Получить подписку
            subscription = await subs_repo.get_by_pair_id(pair.id)
            
            if subscription:
                print(f"  Подписка ID: {subscription.id}")
                print(f"  Статус подписки: {subscription.status}")
                print(f"  Текущий период окончания: {subscription.period_end}")
                
                # Восстановить исходные даты окончания (из логов выше)
                original_dates = {
                    1: date(2026, 1, 6),  # Пара 1: период закончился 06.01.2026
                    2: date(2026, 1, 8),  # Пара 2: период закончился 08.01.2026
                }
                
                original_period_end = original_dates.get(pair.id)
                
                if original_period_end:
                    print(f"  Исходный период окончания: {original_period_end}")
                    
                    # Вернуть период окончания на исходную дату
                    from sqlalchemy import update
                    stmt = (
                        update(Subscription)
                        .where(Subscription.id == subscription.id)
                        .values(period_end=original_period_end)
                    )
                    await session.execute(stmt)
                    print(f"  ✅ Период окончания восстановлен на: {original_period_end}")
                    
                    # Вернуть статус подписки на trial
                    stmt = (
                        update(Subscription)
                        .where(Subscription.id == subscription.id)
                        .values(status=SubscriptionStatus.TRIAL.value)
                    )
                    await session.execute(stmt)
                    print(f"  ✅ Статус подписки изменен на: trial")
                    
                    # Вернуть статус пары на past_due
                    await pairs_repo.update_status(pair.id, PairStatus.PAST_DUE)
                    print(f"  ✅ Статус пары изменен на: past_due")
                else:
                    print(f"  ⚠️  Исходная дата не найдена для пары {pair.id}")
            else:
                print(f"  ⚠️  Подписка не найдена")
            
            await session.commit()
            print()
        
        print("=" * 60)
        print("ГОТОВО!")
        print("=" * 60)
        print()
        print("Пары с истекшими подписками возвращены в статус past_due.")
        print("Вечерние сообщения для них отправляться не будут.")


if __name__ == "__main__":
    asyncio.run(restore_past_due_status())
