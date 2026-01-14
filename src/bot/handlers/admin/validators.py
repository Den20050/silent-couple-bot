"""Validators for admin handlers and use cases."""

# Re-export common validators used in admin handlers
from src.bot.validators.user import validate_user_exists

__all__ = [
    "validate_user_exists",
]

