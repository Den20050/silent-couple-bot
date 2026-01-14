"""Mode validation utilities."""

from src.bot.exceptions import ValidationError
from src.core.logger import get_logger
from src.core.messages import get_message

logger = get_logger(__name__)

VALID_MODES = {"chat", "silent"}


def validate_mode(mode: str, error_message_key: str = "SETTINGS_ERROR") -> None:
    """Validate pair mode.
    
    Args:
        mode: Mode to validate ("chat" or "silent")
        error_message_key: Message key for error
        
    Raises:
        ValidationError: If mode is invalid
    """
    if mode not in VALID_MODES:
        logger.warning(
            "Invalid mode",
            mode=mode,
            valid_modes=VALID_MODES,
        )
        raise ValidationError(
            message_key=error_message_key,
            message=get_message(error_message_key),
        )

