"""Service for building captions for wishes and responses."""

import random
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import CHAT_MORNING_CAPTIONS, CHAT_EVENING_CAPTIONS
from src.core.logger import get_logger
from src.core.messages import get_message
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.users import UsersRepository

logger = get_logger(__name__)


class CaptionService:
    """Service for building captions for wishes and responses."""

    def __init__(self, session: AsyncSession):
        """Initialize caption service.

        Args:
            session: Database session
        """
        self.session = session
        self.pairs_repo = PairsRepository(session)
        self.users_repo = UsersRepository(session)

    async def build_wish_caption(
        self,
        pair,
        sender_user_id: int,
        pic_type: str,
    ) -> str:
        """Build caption for wish photo with nickname.

        Args:
            pair: Pair object
            sender_user_id: User ID of the sender
            pic_type: Picture type ("morning" or "evening")

        Returns:
            Formatted caption with nickname prefix
        """
        caption = self._get_standard_caption(
            pair_mode=pair.mode,
            pic_type=pic_type,
        )
        return await self._format_caption_with_nickname(
            caption=caption,
            pair=pair,
            sender_user_id=sender_user_id,
        )

    async def build_response_caption(
        self,
        pair,
        sender_user_id: int,
        pic_type: str,
    ) -> str:
        """Build caption for response photo with nickname.

        Args:
            pair: Pair object
            sender_user_id: User ID of the sender (responder)
            pic_type: Picture type ("morning" or "evening")

        Returns:
            Formatted caption with nickname prefix
        """
        caption = self._get_standard_caption(
            pair_mode=pair.mode, pic_type=pic_type
        )
        return await self._format_caption_with_nickname(
            caption=caption,
            pair=pair,
            sender_user_id=sender_user_id,
        )

    def _get_standard_caption(
        self,
        pair_mode: str,
        pic_type: str,
    ) -> str:
        """Get caption based on mode and picture type.

        Chat mode: random pick from a pool of 15 warm captions.
        Silent mode: fixed contextual caption.

        Args:
            pair_mode: Pair mode ("chat" or "silent")
            pic_type: Picture type ("morning" or "evening")

        Returns:
            Caption text
        """
        if pair_mode == "chat":
            if pic_type == "morning":
                return random.choice(CHAT_MORNING_CAPTIONS)
            else:
                return random.choice(CHAT_EVENING_CAPTIONS)
        else:  # silent
            if pic_type == "morning":
                return get_message("CAPTION_SILENT_MORNING")
            else:
                return get_message("CAPTION_SILENT_EVENING")

    async def _format_caption_with_nickname(
        self,
        caption: str,
        pair,
        sender_user_id: int,
    ) -> str:
        """Format caption with partner nickname or username at the beginning.

        Args:
            caption: Original caption text
            pair: Pair object
            sender_user_id: User ID of the sender (to determine which
                nickname to use)

        Returns:
            Formatted caption with nickname prefix
        """
        partner_nickname = self.pairs_repo.get_partner_nickname(
            pair,
            sender_user_id,
        )
        if partner_nickname:
            return f"от {partner_nickname}. {caption}"

        sender_user = await self.users_repo.get_by_id(sender_user_id)
        if sender_user and sender_user.username:
            return f"от @{sender_user.username}. {caption}"
        return f"от близкого человека. {caption}"
