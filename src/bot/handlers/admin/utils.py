"""Admin utilities."""

from src.core.config import Settings


def is_admin(tg_id: int, settings_instance: Settings) -> bool:
    """Check if user is admin."""
    return settings_instance.admin_tg_id is not None and tg_id == settings_instance.admin_tg_id

