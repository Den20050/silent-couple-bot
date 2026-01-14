"""Link command handler (Chat Mode)."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.core.messages import get_message
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.users import UsersRepository

logger = get_logger(__name__)

router = Router(name="link")


@router.message(Command("link"))
async def cmd_link(message: Message, session: AsyncSession) -> None:
    """Handle /link command (deprecated - Chat Mode no longer requires this)."""
    tg_id = message.from_user.id
    
    users_repo = UsersRepository(session)
    pairs_repo = PairsRepository(session)
    
    user = await users_repo.get_by_tg_id(tg_id)
    if not user:
        await message.answer(get_message("LINK_START_REQUIRED"))
        return
    
    pair = await pairs_repo.get_by_user_tg_id(tg_id)
    if not pair:
        await message.answer(get_message("LINK_NO_PAIR"))
        return
    
    # Inform user that /link is no longer needed
    await message.answer(get_message("LINK_DEPRECATED_INFO"))

