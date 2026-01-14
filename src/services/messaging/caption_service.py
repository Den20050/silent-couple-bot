"""Service for building captions for wishes and responses."""

import random
from datetime import datetime
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import (
    MICRO_SURPRISE_MORNING_CAPTIONS,
    MICRO_SURPRISE_EVENING_CAPTIONS,
    MICRO_SURPRISE_MIN_HOURS,
)
from src.core.logger import get_logger
from src.core.messages import get_message
from src.db.repositories.daily_state import DailyStateRepository
from src.db.repositories.pairs import PairsRepository

logger = get_logger(__name__)


class CaptionService:
    """Service for building captions with surprise logic and nickname formatting."""

    def __init__(self, session: AsyncSession):
        """Initialize caption service.

        Args:
            session: Database session
        """
        self.session = session
        self.pairs_repo = PairsRepository(session)
        self.daily_state_repo = DailyStateRepository(session)

    async def build_wish_caption(
        self,
        pair,
        sender_user_id: int,
        pic_type: str,
        daily_state,
        include_surprise: bool = True,
    ) -> tuple[str, bool]:
        """Build caption for wish with Micro-Surprise logic and nickname.

        Args:
            pair: Pair object
            sender_user_id: User ID of the sender
            pic_type: Picture type ("morning" or "evening")
            daily_state: DailyState object with last_surprise_at
            include_surprise: Whether to include Micro-Surprise logic (default: True)

        Returns:
            Tuple of (caption, is_surprise_used)
        """
        # Get base caption with surprise logic if enabled
        if include_surprise and pair.mode == "chat":
            caption, is_surprise = self._get_caption_with_surprise(
                pair_mode=pair.mode,
                pic_type=pic_type,
                daily_state=daily_state,
            )
        else:
            caption = self._get_standard_caption(
                pair_mode=pair.mode,
                pic_type=pic_type,
            )
            is_surprise = False

        # Format caption with nickname
        caption = self._format_caption_with_nickname(
            caption=caption,
            pair=pair,
            sender_user_id=sender_user_id,
        )

        return caption, is_surprise

    async def build_response_caption(
        self,
        pair,
        sender_user_id: int,
        pic_type: str,
    ) -> str:
        """Build caption for response.

        Args:
            pair: Pair object
            sender_user_id: User ID of the sender (responder)
            pic_type: Picture type ("morning" or "evening")

        Returns:
            Formatted caption with nickname
        """
        # Get base caption based on mode
        if pair.mode == "chat":
            caption = get_message("RESPONSE_RECEIVED_CHAT")
        else:
            if pic_type == "morning":
                caption = get_message("RESPONSE_MORNING_SILENT")
            else:
                caption = get_message("RESPONSE_EVENING_SILENT")

        # Format caption with nickname
        caption = self._format_caption_with_nickname(
            caption=caption,
            pair=pair,
            sender_user_id=sender_user_id,
        )

        return caption

    def _get_caption_with_surprise(
        self,
        pair_mode: str,
        pic_type: str,
        daily_state,
    ) -> tuple[str, bool]:
        """Get caption with Micro-Surprise logic for Chat Mode.

        Args:
            pair_mode: Pair mode ("chat" or "silent")
            pic_type: Picture type ("morning" or "evening")
            daily_state: DailyState object with last_surprise_at

        Returns:
            Tuple of (caption, is_surprise_used)
        """
        if pair_mode != "chat":
            # Silent Mode: standard captions
            if pic_type == "morning":
                return get_message("CAPTION_SILENT_MORNING"), False
            else:  # evening
                return get_message("CAPTION_SILENT_EVENING"), False

        # Chat Mode: check for Micro-Surprise
        if pic_type == "morning":
            standard_caption = get_message("CAPTION_CHAT_MORNING")
            surprise_captions = MICRO_SURPRISE_MORNING_CAPTIONS
        else:  # evening
            standard_caption = get_message("CAPTION_CHAT_EVENING")
            surprise_captions = MICRO_SURPRISE_EVENING_CAPTIONS

        # Check if we should use surprise (1 in 4 chance, but only if >= 72 hours passed)
        use_surprise = False
        if random.randint(1, 4) == 1:
            if daily_state.last_surprise_at is None:
                # First time - allow surprise
                use_surprise = True
            else:
                # Check if >= 72 hours passed
                hours_passed = (
                    (datetime.utcnow() - daily_state.last_surprise_at).total_seconds() / 3600
                )
                if hours_passed >= MICRO_SURPRISE_MIN_HOURS:
                    use_surprise = True

        if use_surprise:
            caption = random.choice(surprise_captions)
            return caption, True
        else:
            return standard_caption, False

    def _get_standard_caption(
        self,
        pair_mode: str,
        pic_type: str,
    ) -> str:
        """Get standard caption based on mode and picture type.

        Args:
            pair_mode: Pair mode ("chat" or "silent")
            pic_type: Picture type ("morning" or "evening")

        Returns:
            Standard caption text
        """
        if pair_mode == "chat":
            if pic_type == "morning":
                return get_message("CAPTION_CHAT_MORNING")
            else:
                return get_message("CAPTION_CHAT_EVENING")
        else:  # silent
            if pic_type == "morning":
                return get_message("CAPTION_SILENT_MORNING")
            else:
                return get_message("CAPTION_SILENT_EVENING")

    def _format_caption_with_nickname(
        self,
        caption: str,
        pair,
        sender_user_id: int,
    ) -> str:
        """Format caption with partner nickname at the beginning.

        Args:
            caption: Original caption text
            pair: Pair object
            sender_user_id: User ID of the sender (to determine which nickname to use)

        Returns:
            Formatted caption with nickname prefix
        """
        # Get partner nickname (how recipient calls sender)
        partner_nickname = self.pairs_repo.get_partner_nickname(pair, sender_user_id)

        if partner_nickname:
            # Add nickname at the beginning: "от мама. Доброе утро!"
            return f"от {partner_nickname}. {caption}"
        else:
            # No nickname set, return original caption
            return caption

