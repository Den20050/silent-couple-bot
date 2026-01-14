"""Nickname validation utilities."""

import re
from typing import Optional

from src.bot.exceptions import ValidationError
from src.core.logger import get_logger
from src.core.messages import get_message

logger = get_logger(__name__)

# Nickname validation regex: only letters, numbers, and spaces
NICKNAME_PATTERN = re.compile(r'^[a-zA-Zа-яА-ЯёЁ0-9\s]+$')


def validate_nickname_format(nickname: str) -> None:
    """Validate nickname format.
    
    Args:
        nickname: Nickname to validate
        
    Raises:
        ValidationError: If nickname format is invalid
    """
    if not nickname or len(nickname.strip()) == 0:
        raise ValidationError(
            message_key="SETTINGS_NICKNAME_INVALID",
            message="❌ Некорректное имя. Используйте только буквы, цифры и пробелы.",
        )
    
    if len(nickname) > 50:
        raise ValidationError(
            message_key="SETTINGS_NICKNAME_TOO_LONG",
            message="❌ Имя слишком длинное. Максимум 50 символов.",
        )
    
    if not NICKNAME_PATTERN.match(nickname):
        raise ValidationError(
            message_key="SETTINGS_NICKNAME_INVALID",
            message="❌ Некорректное имя. Используйте только буквы, цифры и пробелы.",
        )


def validate_nickname_optional(nickname: Optional[str]) -> None:
    """Validate optional nickname (can be None for clearing).
    
    Args:
        nickname: Nickname to validate (None is allowed)
        
    Raises:
        ValidationError: If nickname format is invalid (when not None)
    """
    if nickname is not None:
        validate_nickname_format(nickname)

