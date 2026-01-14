"""Service for sending responses to wishes."""

from datetime import date
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import PicType
from src.core.logger import get_logger
from src.db.repositories.daily_state import DailyStateRepository
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.users import UsersRepository
from src.services.image import ImageService
from src.services.messaging.caption_service import CaptionService
from src.core.protocols.messenger import MessengerProtocol

logger = get_logger(__name__)


class ResponseSenderService:
    """Service for sending responses to wishes."""

    def __init__(
        self,
        session: AsyncSession,
        telegram_messenger: MessengerProtocol,
    ):
        """Initialize response sender service.

        Args:
            session: Database session
            telegram_messenger: Telegram messenger instance
        """
        self.session = session
        self.telegram_messenger = telegram_messenger
        self.pairs_repo = PairsRepository(session)
        self.daily_state_repo = DailyStateRepository(session)
        self.users_repo = UsersRepository(session)
        self.image_service = ImageService(session)
        self.caption_service = CaptionService(session)

    async def send_response(
        self,
        pair_id: int,
        check_day: date,
        tg_id: int,
        initiator_tg_id: int,
        pic_type: str,
    ) -> tuple[bool, Optional[str]]:
        """Send response to a wish from partner.

        Args:
            pair_id: Pair ID
            check_day: Day to check (for reminders, might be previous day)
            tg_id: Telegram ID of the responder
            initiator_tg_id: Telegram ID of the initiator (from callback_data)
            pic_type: Picture type ("morning" or "evening")

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
            error_message is None on success, otherwise contains error key
        """
        # Get pair and users
        pair = await self.pairs_repo.get_by_id(pair_id)
        if not pair:
            return False, "CALLBACK_PAIR_NOT_FOUND"

        user_a = await self.users_repo.get_by_id(pair.uid_a)
        user_b = await self.users_repo.get_by_id(pair.uid_b)
        if not user_a or not user_b:
            return False, "CALLBACK_ERROR_GENERIC"

        # Verify that current user is part of the pair
        if tg_id not in [user_a.tg_id, user_b.tg_id]:
            return False, "CALLBACK_ACCESS_DENIED"

        # Get daily state
        daily_state = await self.daily_state_repo.get_by_pair_and_day(pair_id, check_day)
        if not daily_state:
            return False, "CALLBACK_WISH_NOT_SENT_YET"

        # Check if wish exists
        if pic_type == "morning":
            if daily_state.morning_initiator is None:
                return False, "CALLBACK_WISH_NOT_SENT_YET"
            initiator_user_id = daily_state.morning_initiator
        else:  # evening
            if daily_state.evening_initiator is None:
                return False, "CALLBACK_WISH_NOT_SENT_YET"
            initiator_user_id = daily_state.evening_initiator

        # Check if already responded
        if pic_type == "morning":
            if daily_state.morning_responded_at is not None:
                return False, "CALLBACK_ALREADY_RESPONDED"
        else:  # evening
            if daily_state.evening_responded_at is not None:
                return False, "CALLBACK_ALREADY_RESPONDED"

        # Verify initiator from callback_data
        current_user = await self.users_repo.get_by_tg_id(tg_id)
        if not current_user:
            return False, "CALLBACK_USER_NOT_FOUND"

        initiator_user = await self.users_repo.get_by_tg_id(initiator_tg_id)
        if not initiator_user:
            return False, "CALLBACK_ERROR_GENERIC"

        # Check if current user is trying to respond to their own wish
        if initiator_tg_id == tg_id:
            return False, "CALLBACK_ALREADY_SENT_WISH"

        # Verify that the initiator from callback_data is still the current initiator
        if initiator_user_id != initiator_user.id:
            # The initiator has changed - partner might have sent their own wish
            if initiator_user_id == current_user.id:
                return False, "CALLBACK_PARTNER_ALREADY_SENT"
            else:
                return False, "CALLBACK_WISH_NOT_SENT_YET"

        # Mark response
        if pic_type == "morning":
            success = await self.daily_state_repo.set_morning_response(pair_id, check_day)
        else:  # evening
            success = await self.daily_state_repo.set_evening_response(pair_id, check_day)

        if not success:
            return False, "CALLBACK_SAVE_RESPONSE_ERROR"

        # Get random image for response
        pic_type_enum = PicType.MORNING if pic_type == "morning" else PicType.EVENING
        file_id = await self.image_service.get_random_image(pair_id, pic_type_enum)
        if not file_id:
            return False, "CALLBACK_NO_IMAGES_AVAILABLE"

        # Send response photo to initiator
        initiator_user_obj = user_a if initiator_user_id == user_a.id else user_b
        initiator_tg_id_final = initiator_user_obj.tg_id

        # Build caption for response
        sender_user = user_a if user_a.tg_id == tg_id else user_b
        sender_user_id = sender_user.id

        caption = await self.caption_service.build_response_caption(
            pair=pair,
            sender_user_id=sender_user_id,
            pic_type=pic_type,
        )

        # Send photo to initiator
        await self.telegram_messenger.send_photo(
            chat_id=initiator_tg_id_final,
            photo=file_id,
            caption=caption,
        )

        return True, None

