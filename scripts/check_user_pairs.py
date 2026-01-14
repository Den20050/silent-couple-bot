"""Проверка, в каких парах участвует пользователь."""

import asyncio
from src.core.bootstrap import bootstrap


async def check_user_pairs():
    """Проверить, в каких парах участвует каждый пользователь."""
    container = await bootstrap()
    
    async with container.session_factory() as session:
        from sqlalchemy import select
        from src.db.models import Pair, User
        
        # Получить все пары со статусом past_due
        pairs_result = await session.execute(
            select(Pair).where(Pair.status == 'past_due')
        )
        pairs = pairs_result.scalars().all()
        
        print("=" * 60)
        print("ПРОВЕРКА ПАР И ПОЛЬЗОВАТЕЛЕЙ")
        print("=" * 60)
        print()
        
        print(f"Пары со статусом past_due: {len(pairs)}")
        print()
        
        for pair in pairs:
            print(f"Пара ID: {pair.id}")
            print(f"  uid_a: {pair.uid_a}")
            print(f"  uid_b: {pair.uid_b}")
            
            # Получить пользователей
            user_a_result = await session.execute(
                select(User).where(User.id == pair.uid_a)
            )
            user_a = user_a_result.scalar_one()
            
            user_b_result = await session.execute(
                select(User).where(User.id == pair.uid_b)
            )
            user_b = user_b_result.scalar_one()
            
            print(f"  Пользователь A: tg_id={user_a.tg_id}")
            print(f"  Пользователь B: tg_id={user_b.tg_id}")
            print()
        
        # Проверить, какие пользователи участвуют в нескольких парах
        from collections import Counter
        user_ids = [p.uid_a for p in pairs] + [p.uid_b for p in pairs]
        counts = Counter(user_ids)
        
        print("=" * 60)
        print("ПОЛЬЗОВАТЕЛИ В НЕСКОЛЬКИХ ПАРАХ:")
        print("=" * 60)
        print()
        
        for user_id, count in counts.items():
            if count > 1:
                user_result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = user_result.scalar_one()
                print(f"User ID {user_id} (tg_id={user.tg_id}): участвует в {count} парах")
                
                # Найти пары этого пользователя
                user_pairs = [p for p in pairs if p.uid_a == user_id or p.uid_b == user_id]
                for p in user_pairs:
                    print(f"  - Пара {p.id}")
        
        print()
        print("=" * 60)
        print("ВЫВОД:")
        print("=" * 60)
        print()
        print("Если пользователь участвует в нескольких парах,")
        print("он получит уведомление от каждой пары.")
        print()
        print("Если уведомления отправляются и утром, и вечером,")
        print("то количество сообщений = количество пар × 2 (утро + вечер)")


if __name__ == "__main__":
    asyncio.run(check_user_pairs())
