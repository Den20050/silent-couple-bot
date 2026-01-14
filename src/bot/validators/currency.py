"""Currency validation utilities."""

from src.bot.exceptions import ValidationError
from src.core.constants import SUPPORTED_CURRENCIES
from src.core.logger import get_logger
from src.core.messages import get_message

logger = get_logger(__name__)


def validate_currency(currency_code: str, error_message_key: str = "PAY_ERROR") -> None:
    """Validate currency code.
    
    Args:
        currency_code: Currency code to validate
        error_message_key: Message key for error
        
    Raises:
        ValidationError: If currency code is invalid
    """
    if currency_code not in SUPPORTED_CURRENCIES:
        logger.warning(
            "Invalid currency code",
            currency_code=currency_code,
            supported_currencies=SUPPORTED_CURRENCIES,
        )
        raise ValidationError(
            message_key=error_message_key,
            message=get_message(error_message_key),
        )

