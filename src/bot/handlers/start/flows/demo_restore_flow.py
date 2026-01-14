"""Demo restore flow handler."""

from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import TRIAL_PERIOD_DAYS
from src.core.logger import get_logger
from src.core.messages import get_message, get_days_text
from src.db.models import Pair, User
from src.db.repositories.users import UsersRepository
from src.services.telegram.messenger import TelegramMessenger

from src.bot.handlers.start.services.pair_service import format_partner_text
from src.domain.services.pair_onboarding import PairOnboardingService
from src.db.repositories.pairs import PairsRepository

logger = get_logger(__name__)


class DemoRestoreFlow:
    """Handles demo restoration flow."""
    
    def __init__(self, messenger: TelegramMessenger) -> None:
        """Initialize demo restore flow.
        
        Args:
            messenger: Telegram messenger for sending messages
        """
        self.messenger = messenger
    
    async def check_and_restore(
        self,
        message: Message,
        existing_pair: Pair,
        user_id: int,
        partner_id: int,
        session: AsyncSession,
        pair_onboarding_service: PairOnboardingService | None = None,
    ) -> bool:
        """Check if demo should be restored and restore it.
        
        Args:
            message: Message object
            existing_pair: Existing pair
            user_id: Current user ID
            partner_id: Partner user ID
            session: Database session
            
        Returns:
            True if demo was restored, False otherwise
        """
        # Use domain service for demo restoration
        if not pair_onboarding_service:
            pair_onboarding_service = PairOnboardingService(session)
        
        demo_restored = await pair_onboarding_service.check_and_restore_demo(
            pair=existing_pair,
            user_id=user_id,
            partner_id=partner_id,
        )
        
        if not demo_restored:
            return False
        
        # Get partner information
        users_repo = UsersRepository(session)
        partner = await users_repo.get_by_id(partner_id)
        
        if not partner:
            logger.error(
                "Partner not found for demo restore",
                user_id=user_id,
                partner_id=partner_id,
                pair_id=existing_pair.id,
            )
            return False
        
        # Notify both users about demo restoration
        # Get nickname that user gave to partner
        pairs_repo = PairsRepository(session)
        partner_nickname = pairs_repo.get_my_nickname_for_partner(existing_pair, user_id)
        partner_text = format_partner_text(partner.username, partner_nickname)
        demo_restored_text = (
            f"✅ Демо режим восстановлен!\n\n"
            f"Пара с {partner_text} снова активна.\n"
            f"Демо период: {TRIAL_PERIOD_DAYS} {get_days_text(TRIAL_PERIOD_DAYS)}"
        )
        
        try:
            await message.answer(demo_restored_text)
            await self.messenger.send_message(
                chat_id=partner.tg_id,
                text=demo_restored_text,
                save_message=False,
            )
        except Exception as e:
            logger.error(
                "Failed to send demo restored notification",
                error=str(e),
                tg_id=message.from_user.id,
                partner_tg_id=partner.tg_id,
            )
        
        logger.info(
            "Demo restored for pair",
            tg_id=message.from_user.id,
            pair_id=existing_pair.id,
        )
        
        return True
