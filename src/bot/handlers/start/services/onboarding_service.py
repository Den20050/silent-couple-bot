"""Onboarding service - user creation, consent, mode selection."""

from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.logger import get_logger
from src.db.repositories.users import UsersRepository
from src.services.timezone import detect_timezone_from_ip

logger = get_logger(__name__)


async def get_or_create_user(
    message: Message, session: AsyncSession
) -> tuple[object, bool]:
    """
    Get or create user from message.
    
    Returns:
        tuple: (user, is_new_user)
    """
    tg_id = message.from_user.id
    username = message.from_user.username
    
    users_repo = UsersRepository(session)
    
    # Get existing user
    user = await users_repo.get_by_tg_id(tg_id)
    if user:
        return user, False
    
    # In webhook mode, Telegram sends updates from Telegram servers,
    # so request IP is not a reliable user IP. We keep consent_ip for audit only.
    consent_ip = getattr(message, "ip", None)
    
    # Try to detect timezone from IP (if available)
    utc_offset = None
    if settings.timezone_detect_from_ip_enabled and consent_ip:
        try:
            utc_offset = await detect_timezone_from_ip(consent_ip)
        except Exception as e:
            logger.warning(
                "Failed to detect timezone from IP",
                ip=consent_ip,
                error=str(e),
            )
    
    # Use default if detection failed
    if utc_offset is None:
        utc_offset = 3  # Default: UTC+3 (Moscow)
    
    # Create user
    user = await users_repo.create(
        tg_id=tg_id,
        username=username,
        consent_ip=consent_ip,
    )
    
    # Set timezone (create sets default, but we want detected/default)
    if utc_offset != user.utc_offset:
        await users_repo.update_utc_offset(tg_id, utc_offset)
        logger.info(
            "User timezone set",
            tg_id=tg_id,
            utc_offset=utc_offset,
            detected_from_ip=consent_ip is not None,
        )
    
    logger.info("New user created", tg_id=tg_id, utc_offset=utc_offset)
    # Flush to ensure user is available in current transaction
    await session.flush()
    
    return user, True


async def update_user_consent(
    tg_id: int,
    session: AsyncSession,
    consent_ip: str | None = None,
) -> object | None:
    """
    Update user consent.
    
    Returns:
        User object if successful, None otherwise
    """
    users_repo = UsersRepository(session)
    
    user = await users_repo.update_consent(
        tg_id=tg_id,
        consent=True,
        consent_ip=consent_ip,
    )
    
    if user:
        from datetime import datetime
        from src.db.models import ConsentAudit

        session.add(
            ConsentAudit(
                tg_id=tg_id,
                consented_at=user.consent_dt or datetime.utcnow(),
                consent_ip=consent_ip,
            )
        )
        await session.flush()
        logger.info("Consent saved", tg_id=tg_id)
    else:
        logger.error("Failed to save consent", tg_id=tg_id)
    
    return user


async def update_user_preferred_mode(
    tg_id: int,
    mode: str,
    session: AsyncSession,
) -> object | None:
    """
    Update user preferred mode.
    
    Args:
        tg_id: Telegram user ID
        mode: Mode string ("chat" or "silent")
        session: Database session
        
    Returns:
        User object if successful, None otherwise
    """
    users_repo = UsersRepository(session)
    
    user = await users_repo.update_preferred_mode(tg_id, mode)
    
    if user:
        logger.info("Preferred mode saved", tg_id=tg_id, mode=mode)
    else:
        logger.error("Failed to save preferred mode", tg_id=tg_id)
    
    return user
