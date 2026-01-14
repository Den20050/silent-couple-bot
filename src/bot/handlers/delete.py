"""Delete command handler (GDPR)."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.core.logger import get_logger
from src.core.messages import get_message
from src.db.repositories.users import UsersRepository
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.subscriptions import SubscriptionsRepository
from src.db.models import User, LifetimePairHistory

logger = get_logger(__name__)

router = Router(name="delete")


@router.message(Command("delete"))
async def cmd_delete(message: Message, session: AsyncSession) -> None:
    """Handle /delete command (GDPR right to erasure)."""
    tg_id = message.from_user.id
    
    users_repo = UsersRepository(session)
    pairs_repo = PairsRepository(session)
    subs_repo = SubscriptionsRepository(session)
    
    user = await users_repo.get_by_tg_id(tg_id)
    
    if not user:
        await message.answer(get_message("DELETE_DATA_NOT_FOUND"))
        return
    
    # Check if user has a pair with lifetime subscription
    pair = await pairs_repo.get_by_user_tg_id(tg_id)
    if pair:
        subscription = await subs_repo.get_by_pair_id(pair.id)
        if subscription and subscription.is_lifetime:
            # Save to lifetime_pair_history before deletion
            # Get partner ID
            partner_id = pair.uid_b if pair.uid_a == user.id else pair.uid_a
            
            # Ensure uid_a < uid_b for consistency
            uid_a, uid_b = (user.id, partner_id) if user.id < partner_id else (partner_id, user.id)
            
            # Check if this pair is already in history (shouldn't happen, but safety check)
            existing_history = await session.execute(
                select(LifetimePairHistory).where(
                    LifetimePairHistory.uid_a == uid_a,
                    LifetimePairHistory.uid_b == uid_b,
                )
            )
            if not existing_history.scalar_one_or_none():
                # Add to lifetime_pair_history
                lifetime_history = LifetimePairHistory(
                    uid_a=uid_a,
                    uid_b=uid_b,
                )
                session.add(lifetime_history)
                await session.flush()
                
                logger.info(
                    "Lifetime pair broken - added to history",
                    tg_id=tg_id,
                    user_id=user.id,
                    partner_id=partner_id,
                    pair_id=pair.id,
                )
    
    # Delete user (CASCADE will delete pairs, subscriptions, etc.)
    # But pair_demo remains (protection against demo reuse for the pair)
    # lifetime_pair_history remains (to prevent re-activation)
    await session.delete(user)
    await session.commit()
    
    logger.info("User data deleted", tg_id=tg_id)
    
    await message.answer(get_message("DELETE_SUCCESS"))

