"""Invite flow handler for pair creation."""

from enum import Enum

from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import DeliveryChat, TRIAL_PERIOD_DAYS
from src.core.logger import get_logger
from src.core.messages import get_message, get_days_text
from src.db.models import User
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.users import UsersRepository
from src.services.telegram.bot_provider import BotProvider
from src.services.telegram.messenger import TelegramMessenger

from src.domain.services.pair_onboarding import (
    PairCreationBlockReason,
    PairOnboardingService,
)
from src.bot.handlers.start.services.pair_service import format_partner_text
from src.bot.handlers.start.ui.builders import (
    get_consent_keyboard,
    get_invite_link_keyboard,
)

logger = get_logger(__name__)


class InviteLinkResult(str, Enum):
    """Outcome of processing an invite link."""

    PAIR_CREATED = "pair_created"
    PAYMENT_REQUIRED = "payment_required"
    PENDING_CONSENT = "pending_consent"
    FAILED = "failed"


def _build_pay_required_keyboard(pair_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=get_message("WORKER_WISH_PAY_BUTTON"),
                    callback_data=f"pay_select_currency_{pair_id}",
                )
            ]
        ]
    )


class InviteFlow:
    """Handles invite link flow for pair creation."""
    
    def __init__(
        self,
        bot_provider: BotProvider,
        messenger: TelegramMessenger,
    ) -> None:
        """Initialize invite flow.
        
        Args:
            bot_provider: Bot provider for getting bot instance
            messenger: Telegram messenger for sending messages
        """
        self.bot_provider = bot_provider
        self.messenger = messenger
    
    async def get_invite_link(self, tg_id: int) -> str:
        """Generate invite link for user.
        
        Args:
            tg_id: User Telegram ID
            
        Returns:
            Invite link URL
        """
        bot = self.bot_provider.get_bot()
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        
        if not bot_username:
            bot_id = bot_info.id
            return f"https://t.me/bot{bot_id}?start={tg_id}"
        
        return f"https://t.me/{bot_username}?start={tg_id}"
    
    async def show_invite_link(
        self,
        message_or_callback: Message | CallbackQuery,
        tg_id: int,
        mode: str,
    ) -> None:
        """Show invite link to user.
        
        Args:
            message_or_callback: Message or CallbackQuery object
            tg_id: User Telegram ID
            mode: Selected mode ("chat" or "silent")
        """
        invite_link = await self.get_invite_link(tg_id)
        
        mode_text = "💬 Чат" if mode == "chat" else "💔 Безмолвие"
        text = get_message(
            "START_MODE_SELECTED_MESSAGE",
            mode_text=mode_text,
            invite_link=invite_link,
        )
        keyboard = get_invite_link_keyboard(invite_link)
        
        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.message.edit_text(
                text, reply_markup=keyboard, parse_mode=ParseMode.HTML
            )
            await message_or_callback.answer()
        else:
            await message_or_callback.answer(
                text, reply_markup=keyboard, parse_mode=ParseMode.HTML
            )
    
    async def process_invite_link(
        self,
        message: Message,
        start_param: str,
        user: User,
        session: AsyncSession,
        state: FSMContext | None = None,
        pair_onboarding_service: PairOnboardingService | None = None,
    ) -> InviteLinkResult:
        """Process invite link and create pair if valid.
        
        Args:
            message: Message object
            start_param: Start parameter (partner tg_id)
            user: Current user
            session: Database session
            state: FSM context
            
        Returns:
            InviteLinkResult describing what happened
        """
        try:
            partner_tg_id = int(start_param)
            tg_id = message.from_user.id
            
            # Don't allow self-invite
            if partner_tg_id == tg_id:
                await message.answer(get_message("START_CANNOT_INVITE_SELF"))
                return InviteLinkResult.FAILED
            
            users_repo = UsersRepository(session)
            pairs_repo = PairsRepository(session)
            partner = await users_repo.get_by_tg_id(partner_tg_id)
            if not partner:
                await message.answer(get_message("START_PARTNER_NOT_FOUND"))
                return InviteLinkResult.FAILED
            
            # Partner must have consent unless they already have any pairs
            partner_pairs = await pairs_repo.get_all_by_user_tg_id(partner_tg_id)
            if not partner.consent and not partner_pairs:
                await message.answer(get_message("START_PARTNER_NO_CONSENT"))
                return InviteLinkResult.FAILED
            
            if not partner.preferred_mode:
                await message.answer(get_message("START_PARTNER_NO_MODE"))
                return InviteLinkResult.FAILED
            
            # Current user must have consent unless they already have any pairs
            user_pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)
            if not user.consent and not user_pairs:
                from src.bot.handlers.start.ui.builders import get_policy_keyboard
                await message.answer(
                    get_message("START_WELCOME"),
                    reply_markup=get_policy_keyboard(),
                )
                await message.answer(
                    get_message("START_CONSENT_PROMPT"),
                    reply_markup=get_consent_keyboard(
                        f"consent_invite_{user.id}_{partner_tg_id}"
                    ),
                )
                return InviteLinkResult.PENDING_CONSENT
            
            # Use domain service for pair onboarding
            if not pair_onboarding_service:
                pair_onboarding_service = PairOnboardingService(session)
            
            validation = await pair_onboarding_service.validate_pair_creation(
                user.id, partner.id
            )
            if not validation.ok:
                if validation.reason == PairCreationBlockReason.DEMO_USED:
                    existing_pair = await pairs_repo.get_by_user_ids(user.id, partner.id)
                    if existing_pair:
                        await message.answer(get_message("START_PAIR_ALREADY_CREATED"))
                        return InviteLinkResult.FAILED

                    delivery_chat = DeliveryChat.BOT_DM.value
                    pair = await pair_onboarding_service.create_pair_from_invite_requires_payment(
                        inviter_id=partner.id,
                        invited_id=user.id,
                        inviter_mode=partner.preferred_mode,
                        delivery_chat=delivery_chat,
                    )
                    await self._send_payment_required_notifications(
                        message, pair, user, partner, session
                    )
                    return InviteLinkResult.PAYMENT_REQUIRED

                if validation.message:
                    await message.answer(validation.message)
                return InviteLinkResult.FAILED
            
            # Double-check: if pair was already created (race condition protection)
            existing_pair = await pairs_repo.get_by_user_ids(user.id, partner.id)
            if existing_pair:
                logger.warning(
                    "Pair already exists, skipping creation",
                    tg_id=tg_id,
                    partner_tg_id=partner_tg_id,
                    pair_id=existing_pair.id,
                )
                await message.answer(get_message("START_PAIR_ALREADY_CREATED"))
                return InviteLinkResult.FAILED
            
            delivery_chat = DeliveryChat.BOT_DM.value
            
            # Create pair using domain service
            pair = await pair_onboarding_service.create_pair_from_invite(
                inviter_id=partner.id,
                invited_id=user.id,
                inviter_mode=partner.preferred_mode,
                delivery_chat=delivery_chat,
            )
            
            logger.info(
                "Pair created from invite",
                tg_id=tg_id,
                partner_tg_id=partner_tg_id,
                pair_id=pair.id,
            )
            
            # Send notifications
            await self._send_pair_created_notifications(
                message, pair, user, partner, session
            )
            
            return InviteLinkResult.PAIR_CREATED
        except ValueError:
            await message.answer(get_message("START_INVALID_INVITE_LINK"))
            return InviteLinkResult.FAILED
    
    async def _send_payment_required_notifications(
        self,
        message: Message,
        pair,
        user: User,
        partner: User,
        session: AsyncSession,
    ) -> None:
        """Notify both users that the pair needs payment (demo already used)."""
        pairs_repo = PairsRepository(session)
        invitee_nickname = pairs_repo.get_my_nickname_for_partner(pair, partner.id)
        invitee_text = format_partner_text(user.username, invitee_nickname)

        keyboard = _build_pay_required_keyboard(pair.id)
        pay_text = get_message("START_BOTH_DEMO_USED")

        await message.answer(
            pay_text,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )
        await self.messenger.send_message(
            chat_id=partner.tg_id,
            text=get_message(
                "START_PAIR_RECONNECTED_REQUIRES_PAYMENT",
                partner_text=invitee_text,
            ),
            reply_markup=keyboard,
            save_message=False,
        )
        logger.info(
            "Payment required notifications sent (demo already used)",
            pair_id=pair.id,
            invited_tg_id=user.tg_id,
            inviter_tg_id=partner.tg_id,
        )

    async def _send_pair_created_notifications(
        self,
        message: Message,
        pair,
        user: User,
        partner: User,
        session: AsyncSession,
    ) -> None:
        """Send notifications after pair creation.
        
        Args:
            message: Message object
            pair: Created pair
            user: Current user
            partner: Partner user
            session: Database session
        """
        mode_text = (
            "💬 Чат"
            if partner.preferred_mode == "chat"
            else "💔 Безмолвие"
        )
        
        try:
            await message.answer(
                get_message(
                    "START_PAIR_CREATED",
                    mode_text=mode_text,
                    days=TRIAL_PERIOD_DAYS,
                    days_text=get_days_text(TRIAL_PERIOD_DAYS),
                )
            )
            
            # Notify partner (with duplicate prevention using Redis)
            username = message.from_user.username or get_message("START_USERNAME_FALLBACK")
            
            # Use Redis to prevent duplicate notifications
            notification_sent = False
            try:
                from src.core.redis_client import create_redis_client
                redis_client = await create_redis_client(
                    socket_connect_timeout=2, socket_timeout=2
                )
                if redis_client:
                    notification_key = f"pair_created_notification:{pair.id}:{partner.tg_id}"
                    # Try to set with NX (only if not exists) to prevent duplicates
                    set_result = await redis_client.set(
                        notification_key, "1", ex=3600, nx=True  # Expires in 1 hour
                    )
                    if set_result:
                        # Key was set, we can send notification
                        notification_sent = True
                    else:
                        # Key already exists - notification already sent
                        logger.warning(
                            "Pair created notification already sent (Redis), skipping duplicate",
                            pair_id=pair.id,
                            partner_tg_id=partner.tg_id,
                            key=notification_key,
                        )
            except Exception as e:
                logger.warning(
                    "Failed to check Redis for duplicate notification, sending anyway",
                    error=str(e),
                    pair_id=pair.id,
                )
                notification_sent = True  # Send anyway if Redis check fails
            
            if notification_sent:
                await self.messenger.send_message(
                    chat_id=partner.tg_id,
                    text=get_message(
                        "START_PAIR_CREATED_PARTNER",
                        username=username,
                        days=TRIAL_PERIOD_DAYS,
                        days_text=get_days_text(TRIAL_PERIOD_DAYS),
                    ),
                    save_message=False,
                )
            
            # Request nickname from both users
            await self._request_nickname_from_users(
                pair, user, partner, session
            )
        except Exception as e:
            logger.error(
                "Error sending notifications after pair creation",
                error=str(e),
                pair_id=pair.id,
                tg_id=user.tg_id,
                partner_tg_id=partner.tg_id,
                exc_info=True,
            )
            try:
                await message.answer(
                    get_message(
                        "START_PAIR_CREATED",
                        mode_text=mode_text,
                        days=TRIAL_PERIOD_DAYS,
                        days_text=get_days_text(TRIAL_PERIOD_DAYS),
                    )
                )
            except Exception:
                pass
    
    async def _request_nickname_from_users(
        self,
        pair,
        user: User,
        partner: User,
        session: AsyncSession,
    ) -> None:
        """Request nickname from both users after pair creation.
        
        Args:
            pair: Created pair object
            user: Current user (invited)
            partner: Partner user (inviter)
            session: Database session
        """
        try:
            # Use Redis to store nickname request state for both users
            # This allows handlers to check if user should enter nickname
            try:
                from src.core.redis_client import create_redis_client
                redis_client = await create_redis_client(
                    socket_connect_timeout=2, socket_timeout=2
                )
                if redis_client:
                    # Set state keys for both users (expires in 1 hour)
                    user_state_key = f"pair_creation_nickname:{pair.id}:{user.tg_id}"
                    partner_state_key = f"pair_creation_nickname:{pair.id}:{partner.tg_id}"
                    
                    # Store pair_id:user_id format (expires in 1 hour)
                    await redis_client.set(
                        user_state_key,
                        f"{pair.id}:{user.id}",
                        ex=3600
                    )
                    await redis_client.set(
                        partner_state_key,
                        f"{pair.id}:{partner.id}",
                        ex=3600
                    )
            except Exception as e:
                logger.warning(
                    "Failed to set Redis keys for nickname state",
                    error=str(e),
                )
            
            # Send nickname request to both users
            nickname_prompt = get_message("START_NICKNAME_PROMPT")
            
            await self.messenger.send_message(
                chat_id=user.tg_id,
                text=nickname_prompt,
                save_message=False,
            )
            
            await self.messenger.send_message(
                chat_id=partner.tg_id,
                text=nickname_prompt,
                save_message=False,
            )

            expand_prompt = get_message("START_EXPAND_CIRCLE_PROMPT")
            await self.messenger.send_message(
                chat_id=user.tg_id,
                text=expand_prompt,
                save_message=False,
            )
            await self.messenger.send_message(
                chat_id=partner.tg_id,
                text=expand_prompt,
                save_message=False,
            )
            
            logger.info(
                "Nickname requests sent to both users",
                pair_id=pair.id,
                user_tg_id=user.tg_id,
                partner_tg_id=partner.tg_id,
            )
        except Exception as e:
            logger.error(
                "Error requesting nickname from users",
                error=str(e),
                pair_id=pair.id,
                user_tg_id=user.tg_id,
                partner_tg_id=partner.tg_id,
                exc_info=True,
            )
    
