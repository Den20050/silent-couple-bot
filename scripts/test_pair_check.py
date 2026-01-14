"""Test pair check for specific user."""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select
from src.core.config import settings
from src.db.base import async_session_maker
from src.db.models import User, Pair


async def test_pair_check(tg_id: int):
    """Test pair check for specific user."""
    async with async_session_maker() as session:
        # Get user
        user_result = await session.execute(
            select(User).where(User.tg_id == tg_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user:
            print(f"❌ User with tg_id={tg_id} not found")
            return
        
        print(f"\n👤 User: @{user.username or 'без имени'}")
        print(f"   - tg_id: {user.tg_id}")
        print(f"   - id: {user.id}")
        print(f"   - Consent: {user.consent}")
        print(f"   - Preferred mode: {user.preferred_mode}")
        
        # Check pair using the same logic as in handle_start_logic
        pair_result = await session.execute(
            select(Pair).where(
                (Pair.uid_a == user.id) | (Pair.uid_b == user.id)
            )
        )
        existing_pair = pair_result.scalar_one_or_none()
        
        print(f"\n🔍 Pair check result:")
        print(f"   - has_pair: {existing_pair is not None}")
        
        if existing_pair:
            print(f"   - pair_id: {existing_pair.id}")
            print(f"   - pair_uid_a: {existing_pair.uid_a}")
            print(f"   - pair_uid_b: {existing_pair.uid_b}")
            print(f"   - user.id matches uid_a: {existing_pair.uid_a == user.id}")
            print(f"   - user.id matches uid_b: {existing_pair.uid_b == user.id}")
            
            # Get partner
            partner_id = existing_pair.uid_b if existing_pair.uid_a == user.id else existing_pair.uid_a
            partner_result = await session.execute(
                select(User).where(User.id == partner_id)
            )
            partner = partner_result.scalar_one_or_none()
            
            if partner:
                print(f"   - partner: @{partner.username or 'без имени'} (tg_id: {partner.tg_id}, id: {partner.id})")
            else:
                print(f"   - partner: NOT FOUND (id: {partner_id})")
        else:
            print(f"   - ❌ No pair found!")
            
            # Show all pairs for debugging
            all_pairs_result = await session.execute(select(Pair))
            all_pairs = all_pairs_result.scalars().all()
            print(f"\n📋 All pairs in database ({len(all_pairs)} total):")
            for pair in all_pairs:
                user_a_result = await session.execute(select(User).where(User.id == pair.uid_a))
                user_a = user_a_result.scalar_one_or_none()
                user_b_result = await session.execute(select(User).where(User.id == pair.uid_b))
                user_b = user_b_result.scalar_one_or_none()
                
                print(f"   Pair {pair.id}:")
                print(f"     - uid_a: {pair.uid_a} (@{user_a.username if user_a else 'не найден'})")
                print(f"     - uid_b: {pair.uid_b} (@{user_b.username if user_b else 'не найден'})")
                print(f"     - matches user.id={user.id}: {pair.uid_a == user.id or pair.uid_b == user.id}")


if __name__ == "__main__":
    # Test for second user (accepted invite)
    tg_id = 241753408
    asyncio.run(test_pair_check(tg_id))

