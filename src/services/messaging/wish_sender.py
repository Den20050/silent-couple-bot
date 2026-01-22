"""Service for sending wishes to partners."""

from datetime import date
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from redis.asyncio import Redis

from src.core.constants import PicType, PairStatus
from src.core.logger import get_logger
from src.core.messages import get_message
from src.services.messaging.wish_request_prompt_refresher import refresh_aggregated_wish_prompt
from src.services.messaging.wish_photo_message_id import wish_photo_message_id_key
from src.db.repositories.daily_state import DailyStateRepository
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.users import UsersRepository
from src.services.image import ImageService
from src.services.messaging.caption_service import CaptionService
from src.core.protocols.messenger import MessengerProtocol

logger = get_logger(__name__)

_WISH_PHOTO_MESSAGE_ID_TTL_SECONDS = 72 * 3600

class WishSenderService:
    """Service for sending wishes to partners."""

    def __init__(
        self,
        session: AsyncSession,
        telegram_messenger: MessengerProtocol,
        redis: Redis | None = None,
    ):
        """Initialize wish sender service.

        Args:
            session: Database session
            telegram_messenger: Telegram messenger instance
            redis: Optional Redis client (used for tracking wish photo message_id)
        """
        self.session = session
        self.telegram_messenger = telegram_messenger
        self._redis = redis
        self.pairs_repo = PairsRepository(session)
        self.daily_state_repo = DailyStateRepository(session)
        self.users_repo = UsersRepository(session)
        self.image_service = ImageService(session)
        self.caption_service = CaptionService(session)

    async def send_wish_to_partner(
        self,
        pair,
        user_id: int,
        tg_id: int,
        pic_type: str,
        today: date,
    ) -> tuple[bool, Optional[str]]:
        """Send wish to a single partner.

        Args:
            pair: Pair object
            user_id: User ID of the sender
            tg_id: Telegram ID of the sender
            pic_type: Picture type ("morning" or "evening")
            today: Current date

        Returns:
            Tuple of (success: bool, partner_nickname: Optional[str])
        """
        # Get users
        user_a = await self.users_repo.get_by_id(pair.uid_a)
        user_b = await self.users_repo.get_by_id(pair.uid_b)
        if not user_a or not user_b:
            return False, None

        # Check if subscription is past due
        if pair.status == PairStatus.PAST_DUE.value:
            return False, None

        # Get daily state
        daily_state = await self.daily_state_repo.get_or_create(pair.id, today)

        # Skip if already sent today
        if pic_type == "morning":
            if daily_state.morning_initiator is not None or daily_state.morning_sent_at is not None:
                return False, None
        else:  # evening
            if daily_state.evening_initiator is not None or daily_state.evening_sent_at is not None:
                return False, None

        # Get random image
        pic_type_enum = PicType.MORNING if pic_type == "morning" else PicType.EVENING
        file_id = await self.image_service.get_random_image(pair.id, pic_type_enum)
        if not file_id:
            return False, None

        # Try to atomically set initiator
        if pic_type == "morning":
            success = await self.daily_state_repo.set_morning_initiator(
                pair_id=pair.id,
                day=today,
                initiator_id=user_id,
                file_id=file_id,
            )
        else:  # evening
            success = await self.daily_state_repo.set_evening_initiator(
                pair_id=pair.id,
                day=today,
                initiator_id=user_id,
                file_id=file_id,
            )

        if not success:
            # Someone already pressed for this pair
            return False, None

        # Commit initiator setting
        await self.session.commit()

        # Get partner
        partner = user_b if user_a.tg_id == tg_id else user_a

        # Refresh daily_state
        daily_state = await self.daily_state_repo.get_by_pair_and_day(pair.id, today)

        # Build caption with surprise logic
        caption, is_surprise = await self.caption_service.build_wish_caption(
            pair=pair,
            sender_user_id=user_id,
            pic_type=pic_type,
            daily_state=daily_state,
            include_surprise=True,
        )

        # Update last_surprise_at if surprise was used
        if is_surprise:
            await self.daily_state_repo.update_last_surprise_at(pair.id, today)
            await self.session.commit()

        # Create reply markup
        button_text = get_message("RESPOND_BUTTON")
        callback_prefix = "tap_morning" if pic_type == "morning" else "tap_evening"
        reply_markup = {
            "inline_keyboard": [
                [
                    {
                        "text": button_text,
                        "callback_data": f"{callback_prefix}_{pair.id}_{tg_id}",
                    },
                ],
            ],
        }

        # Send photo to partner
        msg = await self.telegram_messenger.send_photo(
            chat_id=partner.tg_id,
            photo=file_id,
            caption=caption,
            reply_markup=reply_markup,
        )

        # Store wish photo message_id so reminders can disable the old respond button later.
        if self._redis is not None:
            try:
                key = wish_photo_message_id_key(
                    tg_id=partner.tg_id,
                    pair_id=pair.id,
                    pic_type=pic_type,
                    day=today,
                )
                await self._redis.setex(key, _WISH_PHOTO_MESSAGE_ID_TTL_SECONDS, str(msg.message_id))
            except Exception as e:
                logger.debug(
                    "Failed to store wish photo message_id (ignored)",
                    pair_id=pair.id,
                    pic_type=pic_type,
                    error=str(e),
                )

        # Best-effort: refresh partner's aggregated prompt so "send wish" CTA is gone for this pair.
        await refresh_aggregated_wish_prompt(
            session=self.session,
            telegram_messenger=self.telegram_messenger,
            tg_id=partner.tg_id,
            pic_type=pic_type,
            day=today,
        )

        # Get partner nickname for confirmation message
        partner_nickname = self.pairs_repo.get_my_nickname_for_partner(pair, user_id)
        if not partner_nickname:
            partner_nickname = "партнёру"

        # Commit after successful send
        await self.session.commit()

        return True, partner_nickname

    async def send_wish_to_all_partners(
        self,
        active_pairs: list,
        user_id: int,
        tg_id: int,
        pic_type: str,
        today: date,
    ) -> tuple[int, list[str]]:
        """Send wish to all active partners.

        Args:
            active_pairs: List of active pairs
            user_id: User ID of the sender
            tg_id: Telegram ID of the sender
            pic_type: Picture type ("morning" or "evening")
            today: Current date

        Returns:
            Tuple of (sent_count: int, partner_nicknames: list[str])
        """
        sent_count = 0
        partner_nicknames = []

        for pair in active_pairs:
            try:
                success, partner_nickname = await self.send_wish_to_partner(
                    pair=pair,
                    user_id=user_id,
                    tg_id=tg_id,
                    pic_type=pic_type,
                    today=today,
                )

                if success:
                    partner_nicknames.append(partner_nickname)
                    sent_count += 1
            except Exception as e:
                logger.error(
                    f"Error sending {pic_type} wish to partner",
                    pair_id=pair.id,
                    error=str(e),
                    exc_info=True,
                )
                await self.session.rollback()
                continue

        return sent_count, partner_nicknames

