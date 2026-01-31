"""Use case for resetting demo."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.core.messages import get_message
from src.db.models import User
from src.db.repositories.pair_demo import PairDemoRepository
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.users import UsersRepository

logger = get_logger(__name__)


async def reset_demo_for_user(
    tg_id: int,
    session: AsyncSession,
) -> tuple[bool, str]:
    """Reset demo for user.
    
    Args:
        tg_id: Telegram user ID
        session: Database session
        
    Returns:
        Tuple of (success: bool, message_text: str)
    """
    try:
        pair_demo_repo = PairDemoRepository(session)
        users_repo = UsersRepository(session)
        pairs_repo = PairsRepository(session)

        # Get user by tg_id
        user = await users_repo.get_by_tg_id(tg_id)
        if not user:
            return False, get_message("MENU_USER_NOT_FOUND_FORMAT", tg_id=tg_id)

        # Get all pairs for this user
        pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)
        
        if not pairs:
            return False, (
                f"ℹ️ Пользователь {tg_id} не состоит ни в одной паре. "
                "Для сброса демо нужна активная пара."
            )
        elif len(pairs) == 1:
            # Only one pair - reset demo immediately
            pair = pairs[0]
            # Get both users from pair
            user_a_result = await session.execute(
                select(User).where(User.id == pair.uid_a)
            )
            user_a = user_a_result.scalar_one()

            user_b_result = await session.execute(
                select(User).where(User.id == pair.uid_b)
            )
            user_b = user_b_result.scalar_one()

            removed = await pair_demo_repo.remove_pair(user_a.tg_id, user_b.tg_id)
            
            await session.commit()

            if removed:
                message_text = (
                    f"✅ Демо режим сброшен для пары:\n"
                    f"  • {user_a.tg_id}\n"
                    f"  • {user_b.tg_id}\n\n"
                    f"Пара может создать новую пару с демо периодом."
                )
                
                logger.info(
                    "Demo reset by admin for pair",
                    pair_id=pair.id,
                    uid_a=pair.uid_a,
                    uid_b=pair.uid_b,
                )
                return True, message_text
            else:
                return False, (
                    f"ℹ️ Пара пользователя {tg_id} не найдена в списке использовавших демо."
                )
        else:
            # Multiple pairs - suggest using /admin_reset_demo command for selection
            return False, (
                f"ℹ️ Пользователь {tg_id} состоит в {len(pairs)} паре(ах).\n\n"
                "Для выбора конкретной пары используйте команду /admin_reset_demo "
                "и следуйте инструкциям."
            )
    except Exception as e:
        logger.error("Error resetting demo", error=str(e), exc_info=True)
        await session.rollback()
        return False, get_message("ADMIN_RESET_DEMO_ERROR")

