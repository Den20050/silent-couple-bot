"""Micro-Surprise logic for Chat Mode."""

import random
from datetime import datetime

from src.core.constants import (
    MICRO_SURPRISE_MORNING_CAPTIONS,
    MICRO_SURPRISE_EVENING_CAPTIONS,
    MICRO_SURPRISE_MIN_HOURS,
)
from src.core.messages import get_message


def get_caption_with_surprise(
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
        tuple: (caption, is_surprise_used)
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
            hours_passed = (datetime.utcnow() - daily_state.last_surprise_at).total_seconds() / 3600
            if hours_passed >= MICRO_SURPRISE_MIN_HOURS:
                use_surprise = True
    
    if use_surprise:
        caption = random.choice(surprise_captions)
        return caption, True
    else:
        return standard_caption, False

