"""Application service for pair management."""

from aiogram.types import Message

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.core.messages import get_message
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.users import UsersRepository
from src.domain.services.pair_onboarding import PairOnboardingService

logger = get_logger(__name__)


class PairApplicationService:
    """Application service for pair-related use cases.
    
    Coordinates domain services and repositories
    to implement pair management use cases.
    """
    
    def __init__(
        self,
        session: AsyncSession,
        pair_onboarding_service: PairOnboardingService,
    ) -> None:
        """Initialize pair application service.
        
        Args:
            session: Database session
            pair_onboarding_service: Domain service for pair onboarding
        """
        self._session = session
        self._pair_onboarding_service = pair_onboarding_service
        self._users_repo = UsersRepository(session)
        self._pairs_repo = PairsRepository(session)
    
    async def handle_create_pair_command(
        self,
        message: Message,
    ) -> tuple[bool, str, dict | None]:
        """Handle /create_pair command - show mode selection for creating new pair.
        
        Args:
            message: Message object
            
        Returns:
            Tuple of (success: bool, message_text: str, reply_markup: dict | None)
        """
        try:
            tg_id = message.from_user.id
            
            user = await self._users_repo.get_by_tg_id(tg_id)
            
            if not user:
                return False, get_message("MENU_USER_NOT_FOUND"), None
            
            # Check if user has consent (skip if user already has any pairs)
            user_pairs = await self._pairs_repo.get_all_by_user_tg_id(tg_id)
            if not user.consent and not user_pairs:
                return False, (
                    "Для создания пары необходимо принять пользовательское соглашение. "
                    "Используйте команду /start"
                ), None
            
            # Always show mode selection (same as first time)
            from src.bot.handlers.start.ui.builders import get_mode_keyboard
            
            return True, get_message("START_MODE_SELECTION_PROMPT"), get_mode_keyboard().model_dump()
        except Exception as e:
            logger.error("Error in handle_create_pair_command", error=str(e), exc_info=True)
            return False, get_message("MENU_ERROR"), None

