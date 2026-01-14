"""Use case for sending feedback."""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.logger import get_logger
from src.core.messages import get_message
from src.core.redis_client import create_redis_client
from src.db.repositories.subscriptions import SubscriptionsRepository
from src.db.repositories.users import UsersRepository

logger = get_logger(__name__)


async def send_feedback_to_admin(
    message_text: str,
    tg_id: int,
    username: str,
    session: AsyncSession,
    settings: Settings,
    bot,
) -> tuple[bool, str]:
    """Send feedback message to admin.
    
    Args:
        message_text: Feedback message text
        tg_id: Telegram user ID
        username: Telegram username (required)
        session: Database session
        settings: Settings instance
        bot: Bot instance
        
    Returns:
        Tuple of (success: bool, response_message: str)
    """
    try:
        # Check if username is provided (required)
        if not username:
            return False, get_message("FEEDBACK_NO_USERNAME")
        
        # Check if user exists
        users_repo = UsersRepository(session)
        user = await users_repo.get_by_tg_id(tg_id)
        
        if not user:
            # User not registered, ignore message
            return False, ""
        
        # Check if admin is configured
        if not settings.admin_tg_id:
            logger.warning("Admin tg_id not configured, cannot forward feedback")
            return False, get_message("FEEDBACK_ADMIN_NOT_CONFIGURED")
        
        # Check if there's an active ticket (within TTL)
        redis_client = await create_redis_client()
        ticket_key = f"{settings.redis_key_prefix_feedback_ticket}:{tg_id}"
        has_active_ticket = False
        
        if redis_client:
            try:
                existing_ticket = await redis_client.get(ticket_key)
                if existing_ticket:
                    has_active_ticket = True
                    logger.info(
                        "User has active feedback ticket",
                        tg_id=tg_id,
                        ticket_key=ticket_key,
                    )
            except Exception as e:
                logger.warning(
                    "Error checking Redis for active ticket",
                    error=str(e),
                    tg_id=tg_id,
                )
        
        # If there's an active ticket, this is a new message = new ticket
        # We'll create a new ticket anyway, but log it
        if has_active_ticket:
            logger.info(
                "Creating new ticket (previous ticket expired or new message)",
                tg_id=tg_id,
            )
        
        # Get payment IDs for the last 6 months
        subscriptions_repo = SubscriptionsRepository(session)
        payment_ids = await subscriptions_repo.get_payment_ids_by_payer(
            payer_id=user.id,
            months=6,
        )
        
        # Prepare message for admin
        admin_message = (
            f"💬 <b>Обратная связь от пользователя</b>\n\n"
            f"👤 Пользователь: @{username} (ID: {tg_id})\n"
        )
        
        if payment_ids:
            payment_ids_text = ", ".join(payment_ids)
            admin_message += f"💳 ID платежей за последние 6 мес: {payment_ids_text}\n\n"
        else:
            admin_message += "💳 Платежей за последние 6 мес не найдено\n\n"
        
        admin_message += f"📝 Сообщение:\n\n{message_text}"
        
        # Send admin message
        await bot.send_message(
            chat_id=settings.admin_tg_id,
            text=admin_message,
            parse_mode="HTML",
        )
        
        # Create ticket in Redis (TTL: 72 hours)
        if redis_client:
            try:
                ttl_seconds = settings.feedback_ticket_ttl_hours * 3600
                await redis_client.setex(
                    ticket_key,
                    ttl_seconds,
                    str(datetime.now().isoformat()),
                )
                logger.info(
                    "Feedback ticket created in Redis",
                    tg_id=tg_id,
                    ticket_key=ticket_key,
                    ttl_hours=settings.feedback_ticket_ttl_hours,
                )
            except Exception as e:
                logger.warning(
                    "Error creating ticket in Redis",
                    error=str(e),
                    tg_id=tg_id,
                )
        
        logger.info(
            "Feedback message forwarded to admin",
            user_tg_id=tg_id,
            username=username,
            admin_tg_id=settings.admin_tg_id,
            payment_ids_count=len(payment_ids),
        )
        
        return True, get_message("FEEDBACK_SENT")
        
    except Exception as e:
        logger.error("Error in send_feedback_to_admin", error=str(e), exc_info=True)
        return False, get_message("FEEDBACK_ERROR")
