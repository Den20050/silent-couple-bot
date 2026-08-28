"""Onboarding service - user creation, consent, mode selection."""

from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logger import get_logger
from src.db.repositories.users import UsersRepository

logger = get_logger(__name__)


async def get_or_create_user(
    message: Message, session: AsyncSession
) -> tuple[object, bool]:
    """Get or create user from message.

    Returns:
        tuple: (user, is_new_user)
    """
    tg_id = message.from_user.id
    username = message.from_user.username

    users_repo = UsersRepository(session)

    user = await users_repo.get_by_tg_id(tg_id)
    if user:
        return user, False

    consent_ip = getattr(message, "ip", None)
    user = await users_repo.create(
        tg_id=tg_id,
        username=username,
        consent_ip=consent_ip,
    )

    logger.info("New user created (timezone pending Mini App sync)", tg_id=tg_id)
    await session.flush()

    return user, True


async def update_user_consent(
    tg_id: int,
    session: AsyncSession,
    consent_ip: str | None = None,
) -> object | None:
    """Update user consent."""
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
    """Update user preferred mode."""
    users_repo = UsersRepository(session)

    user = await users_repo.update_preferred_mode(tg_id, mode)

    if user:
        logger.info("Preferred mode saved", tg_id=tg_id, mode=mode)
    else:
        logger.error("Failed to save preferred mode", tg_id=tg_id)

    return user
