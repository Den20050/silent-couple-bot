"""Start command handler."""

from datetime import datetime

from aiogram import Bot, Router, F
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    MenuButtonCommands,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from datetime import date, timedelta

from src.core.config import settings
from src.core.constants import (
    DeliveryChat,
    PairMode,
    PairStatus,
    SubscriptionStatus,
    TRIAL_PERIOD_DAYS,
)
from src.core.logger import get_logger
from src.core.messages import get_message, get_days_text
from src.db.repositories.pairs import PairsRepository
from src.db.repositories.subscriptions import SubscriptionsRepository
from src.db.repositories.pair_demo import PairDemoRepository
from src.db.repositories.users import UsersRepository
from src.db.models import LifetimePairHistory, Pair, Subscription
from src.services.telegram import get_bot, send_message_with_retry

logger = get_logger(__name__)

router = Router(name="start")




def get_mode_keyboard() -> InlineKeyboardMarkup:
    """Get mode selection keyboard."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="💬 Часто общаемся",
                    callback_data="mode_chat",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💔 Редко",
                    callback_data="mode_silent",
                ),
            ],
        ]
    )


async def handle_start_logic(
    message: Message, session: AsyncSession, state: FSMContext | None = None
) -> None:
    """Common logic for /start command (also works as restart)."""
    try:
        tg_id = message.from_user.id
        username = message.from_user.username
        message_text = message.text or ""
        start_param = message_text.split()[1] if len(message_text.split()) > 1 else None
        
        logger.info(
            "Handling start logic",
            tg_id=tg_id,
            username=username,
            message_text=message_text,
            start_param=start_param,
            message_id=message.message_id,
        )
        
        # Set Menu Button for this user
        try:
            bot = get_bot()
            menu_button = MenuButtonCommands()
            await bot.set_chat_menu_button(
                chat_id=message.chat.id, menu_button=menu_button
            )
            logger.info("Menu button set for user", tg_id=tg_id, chat_id=message.chat.id)
        except Exception as e:
            logger.warning(f"Failed to set menu button for user: {e}")
        
        users_repo = UsersRepository(session)
        pair_demo_repo = PairDemoRepository(session)
        pairs_repo = PairsRepository(session)
        
        # Get or create user
        user = await users_repo.get_by_tg_id(tg_id)
        if not user:
            # Extract IP from message (if available via webhook)
            # IP is set by webhook_server.py on the message object
            consent_ip = getattr(message, "ip", None)
            
            # Try to detect timezone from IP (if available)
            utc_offset = None
            if consent_ip:
                from src.services.timezone import detect_timezone_from_ip
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
        
        # Save user.id before any cache operations (to avoid MissingGreenlet error)
        user_id = user.id
        
        # ========================================================================
        # CRITICAL: Check if user already has an active pair FIRST
        # This check MUST happen before ANY other logic (consent, mode selection, invite links)
        # If pair exists, show message and EXIT immediately
        # ========================================================================
        
        # Flush any pending changes to ensure we see latest data
        await session.flush()
        
        # Find pair by user ID (we already have user.id, so use it directly)
        from sqlalchemy import select
        from src.db.models import Pair as PairModel
        
        try:
            # Use fresh query to find pair
            pair_result = await session.execute(
                select(PairModel).where(
                    (PairModel.uid_a == user_id) | (PairModel.uid_b == user_id)
                )
            )
            existing_pair = pair_result.scalar_one_or_none()
        except Exception as e:
            logger.error(
                "Error in pair check SQL query",
                tg_id=tg_id,
                user_id=user_id,
                error=str(e),
                exc_info=True,
            )
            existing_pair = None
        
        logger.info(
            "Pair check result (BEFORE ANY OTHER LOGIC)",
            tg_id=tg_id,
            user_id=user_id,
            username=username,
            has_pair=existing_pair is not None,
            pair_id=existing_pair.id if existing_pair else None,
        )
        
        if existing_pair:
            # User has a pair - check if demo was reset by admin
            logger.info(
                "User HAS pair - checking for demo reset",
                tg_id=tg_id,
                user_id=user_id,
                pair_id=existing_pair.id,
                pair_status=existing_pair.status,
            )
            
            # Get partner information
            partner_id = existing_pair.uid_b if existing_pair.uid_a == user_id else existing_pair.uid_a
            partner = await users_repo.get_by_id(partner_id)
            
            if not partner:
                logger.error(
                    "Partner not found",
                    tg_id=tg_id,
                    user_id=user_id,
                    pair_id=existing_pair.id,
                    partner_id=partner_id,
                )
                await message.answer(get_message("START_ACTIVE_PAIR_EXISTS"))
                return
            
            # Check if demo was reset by admin (pair status is PAST_DUE and no demo record exists)
            pair_demo_repo = PairDemoRepository(session)
            demo_was_reset = (
                existing_pair.status == PairStatus.PAST_DUE.value
                and not await pair_demo_repo.is_used(user_id, partner_id)
            )
            
            if demo_was_reset:
                # Admin reset demo - restore trial period
                logger.info(
                    "Demo was reset by admin - restoring trial period",
                    tg_id=tg_id,
                    pair_id=existing_pair.id,
                )
                
                # Get subscription
                subs_repo = SubscriptionsRepository(session)
                subscription = await subs_repo.get_by_pair_id(existing_pair.id)
                
                if subscription:
                    # Update subscription with new trial period
                    trial_end = date.today() + timedelta(days=TRIAL_PERIOD_DAYS)
                    
                    await session.execute(
                        update(Subscription)
                        .where(Subscription.id == subscription.id)
                        .values(
                            status=SubscriptionStatus.TRIAL.value,
                            period_end=trial_end,
                            is_lifetime=False,
                        )
                    )
                
                # Update pair status to trial
                pairs_repo = PairsRepository(session)
                await pairs_repo.update_status(existing_pair.id, PairStatus.TRIAL)
                
                # Create new demo record
                await pair_demo_repo.mark_pair(user_id, partner_id)
                
                await session.commit()
                
                # Notify both users about demo restoration
                partner_username = partner.username if partner.username else None
                partner_text = (
                    f"@{partner_username}"
                    if partner_username
                    else get_message("START_PARTNER_FALLBACK")
                )
                
                demo_restored_text = (
                    f"✅ Демо режим восстановлен!\n\n"
                    f"Пара с {partner_text} снова активна.\n"
                    f"Демо период: {TRIAL_PERIOD_DAYS} {get_days_text(TRIAL_PERIOD_DAYS)}"
                )
                
                try:
                    await message.answer(demo_restored_text)
                    # Notify partner
                    bot = await get_bot()
                    await send_message_with_retry(
                        bot=bot,
                        chat_id=partner.tg_id,
                        text=demo_restored_text,
                    )
                except Exception as e:
                    logger.error(
                        "Failed to send demo restored notification",
                        error=str(e),
                        tg_id=tg_id,
                        partner_tg_id=partner.tg_id,
                    )
                
                logger.info(
                    "Demo restored for pair",
                    tg_id=tg_id,
                    pair_id=existing_pair.id,
                )
                return
            
            # Normal case - pair exists, show pair message
            partner_username = partner.username if partner.username else None
            partner_text = (
                f"@{partner_username}"
                if partner_username
                else get_message("START_PARTNER_FALLBACK")
            )
            
            logger.info(
                "Showing pair message and EXITING (pair exists) - RETURNING NOW",
                tg_id=tg_id,
                partner_tg_id=partner.tg_id,
                partner_username=partner_username,
            )
            await message.answer(
                get_message("START_PAIR_WITH_PARTNER", partner_text=partner_text)
            )
            logger.info(
                "Pair message sent, EXITING handle_start_logic - RETURNING NOW",
                tg_id=tg_id,
                message_id=message.message_id,
                pair_id=existing_pair.id,
            )
            # CRITICAL: Exit here, don't continue to mode selection or invite links
            # This return MUST prevent any further execution
            return
        
        # At this point, user has NO pair - continue with onboarding flow
        logger.info(
            "User has NO pair - continuing with onboarding flow",
            tg_id=tg_id,
            user_id=user.id,
            has_consent=user.consent,
            preferred_mode=user.preferred_mode,
            start_param=start_param,
        )
        
        # Check if user has consent
        if not user.consent:
            # Show policy and ask for consent
            policy_keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text=get_message("START_POLICY_BUTTON"),
                            url="https://telegra.ph/YourPrivacy-07-01",  # TODO: Replace with actual URL
                        ),
                    ],
                ]
            )
            await message.answer(
                get_message("START_WELCOME"),
                reply_markup=policy_keyboard,
            )
            # Check if this is invite link flow
            if start_param:
                try:
                    partner_tg_id = int(start_param)
                    # Use special callback for invite flow
                    callback_data = f"consent_invite_{user.id}_{partner_tg_id}"
                except ValueError:
                    callback_data = f"consent_{user.id}"
            else:
                callback_data = f"consent_{user.id}"
            
            await message.answer(
                get_message("START_CONSENT_PROMPT"),
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=get_message("START_CONSENT_BUTTON"),
                                callback_data=callback_data,
                            ),
                        ],
                    ]
                ),
            )
            return
        
        # If start_param exists, it's an invite link
        if start_param:
            # start_param is partner's tg_id (User A - inviter)
            try:
                partner_tg_id = int(start_param)

                # Don't allow self-invite
                if partner_tg_id == tg_id:
                    await message.answer(get_message("START_CANNOT_INVITE_SELF"))
                    return

                partner = await users_repo.get_by_tg_id(partner_tg_id)
                if not partner:
                    await message.answer(get_message("START_PARTNER_NOT_FOUND"))
                    return

                # Partner (User A) must have consent and preferred mode
                if not partner.consent:
                    await message.answer(get_message("START_PARTNER_NO_CONSENT"))
                    return

                if not partner.preferred_mode:
                    await message.answer(get_message("START_PARTNER_NO_MODE"))
                    return

                # Current user (User B) must have consent
                if not user.consent:
                    # Show policy and ask for consent (without mode selection)
                    policy_keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(
                                    text="📄 Политика",
                                    url="https://telegra.ph/YourPrivacy-07-01",
                                ),
                            ],
                        ]
                    )
                    await message.answer(
            get_message("START_WELCOME"),
                        reply_markup=policy_keyboard,
                    )
                    await message.answer(
                        get_message("START_CONSENT_PROMPT"),
                        reply_markup=InlineKeyboardMarkup(
                            inline_keyboard=[
                                [
                                    InlineKeyboardButton(
                                        text=get_message("START_CONSENT_BUTTON"),
                                        callback_data=f"consent_invite_{user.id}_{partner_tg_id}",
                                    ),
                                ],
                            ]
                        ),
                    )
                    return

                # Check if pair already exists
                existing_pair = await pairs_repo.get_by_user_ids(user.id, partner.id)
                if existing_pair:
                    await message.answer(get_message("START_PAIR_ALREADY_CREATED"))
                    return

                # Check if this pair was previously broken with lifetime subscription
                uid_a, uid_b = (user.id, partner.id) if user.id < partner.id else (partner.id, user.id)
                lifetime_history = await session.execute(
                    select(LifetimePairHistory).where(
                        LifetimePairHistory.uid_a == uid_a,
                        LifetimePairHistory.uid_b == uid_b,
                    )
                )
                if lifetime_history.scalar_one_or_none():
                    await message.answer(get_message("START_LIFETIME_PAIR_BROKEN"))
                    return

                # Check if THIS PAIR already used demo
                pair_used_demo = await pair_demo_repo.is_used(user.id, partner.id)

                if pair_used_demo:
                    await message.answer(get_message("START_BOTH_DEMO_USED"))
                    return

                # Get delivery_chat from FSM state or use default
                delivery_chat = DeliveryChat.BOT_DM.value  # Default
                if state:
                    state_data = await state.get_data()
                    delivery_chat = state_data.get("delivery_chat", DeliveryChat.BOT_DM.value)
                
                # Create pair with partner's (User A) preferred mode
                pair = await pairs_repo.create(
                    uid_a=partner.id,  # Partner is uid_a (inviter)
                    uid_b=user.id,     # Current user is uid_b (invited)
                    mode=partner.preferred_mode,  # Use inviter's mode
                    delivery_chat=delivery_chat,
                )

                # Create subscription (trial) - 7 days
                subs_repo = SubscriptionsRepository(session)
                trial_end = date.today() + timedelta(days=TRIAL_PERIOD_DAYS)
                await subs_repo.create(
                    pair_id=pair.id,
                    payer_id=partner.id,  # Partner is the inviter
                    period_end=trial_end,
                )

                # Mark this pair as demo used
                await pair_demo_repo.mark_pair(user.id, partner.id)

                # Explicitly commit to ensure pair is saved before sending messages
                await session.commit()
                logger.info(
                    "Pair created and committed",
                    tg_id=tg_id,
                    partner_tg_id=partner_tg_id,
                    pair_id=pair.id,
                )

                # After commit, wrap message sending in try-except to prevent rollback
                # of already committed data if sending fails
                try:
                    mode_text = (
                        "💬 Чат" if partner.preferred_mode == "chat" else "💔 Безмолвие"
                    )
                    await message.answer(
                        get_message(
                            "START_PAIR_CREATED",
                            mode_text=mode_text,
                            days=TRIAL_PERIOD_DAYS,
                            days_text=get_days_text(TRIAL_PERIOD_DAYS),
                        )
                    )

                    # If pair_dm mode was selected, send anchor message
                    if delivery_chat == DeliveryChat.PAIR_DM.value:
                        await send_anchor_message_after_pair_creation(
                            message, session, pair.id, tg_id, partner_tg_id
                        )

                    # Notify partner
                    await send_message_with_retry(
                        chat_id=partner_tg_id,
                        text=get_message(
                            "START_PAIR_CREATED_PARTNER",
                            username=username or get_message("START_USERNAME_FALLBACK"),
                            days=TRIAL_PERIOD_DAYS,
                            days_text=get_days_text(TRIAL_PERIOD_DAYS),
                        ),
                    )
                except Exception as e:
                    # Log error but don't raise - pair is already committed
                    logger.error(
                        "Error sending messages after pair creation",
                        error=str(e),
                        pair_id=pair.id,
                        tg_id=tg_id,
                        partner_tg_id=partner_tg_id,
                        exc_info=True,
                    )
                    # Try to send at least basic message to user
                    try:
                        await message.answer(
                            get_message(
                                "START_PAIR_CREATED",
                                mode_text=mode_text if 'mode_text' in locals() else "💔 Безмолвие",
                                days=TRIAL_PERIOD_DAYS,
                                days_text=get_days_text(TRIAL_PERIOD_DAYS),
                            )
                        )
                    except Exception:
                        pass  # Ignore if this also fails
                
                return
            except ValueError:
                await message.answer(get_message("START_INVALID_INVITE_LINK"))
                return
        
        # At this point, user has NO pair (checked above)
        # Check if user already selected mode (for showing invite link to create a pair)
        if user.preferred_mode:
            # User already selected mode but has no pair yet, show invite link
            logger.info(
                "User has mode but no pair, showing invite link",
                tg_id=tg_id,
                preferred_mode=user.preferred_mode,
            )
            bot = get_bot()
            await show_invite_link(message, user.tg_id, user.preferred_mode, bot)
            return
        
        # User has no pair and no mode selected - ask for mode selection
        logger.info(
            "User has no pair and no mode, asking for mode selection",
            tg_id=tg_id,
        )
        await message.answer(
            get_message("START_MODE_SELECTION_PROMPT"),
            reply_markup=get_mode_keyboard(),
        )
    except Exception as e:
        logger.error("Error in handle_start_logic", error=str(e), exc_info=True)
        try:
            await message.answer(get_message("START_ERROR"))
        except:
            pass
        raise


@router.message(CommandStart())
async def cmd_start(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """Handle /start command - also works as restart."""
    tg_id = message.from_user.id
    try:
        logger.info(
            "/start command handler called",
            tg_id=tg_id,
            username=message.from_user.username,
        )
        
        # Clear FSM state (works as restart)
        await state.clear()
        
        # Call start logic
        await handle_start_logic(message, session, state)
    except Exception as e:
        logger.error("Error in cmd_start", error=str(e), exc_info=True)
        try:
            await message.answer(get_message("START_ERROR"))
        except:
            pass
        raise


@router.callback_query(F.data.startswith("consent_"))
async def handle_consent(
    callback: CallbackQuery, session: AsyncSession, state: FSMContext
) -> None:
    """Handle consent callback."""
    try:
        logger.info(
            "Consent callback received",
            callback_data=callback.data,
            tg_id=callback.from_user.id,
        )

        parts = callback.data.split("_")
        
        # Check if this is consent from invite link
        if len(parts) == 4 and parts[1] == "invite":
            # Format: consent_invite_{user_id}_{partner_tg_id}
            user_id = int(parts[2])
            partner_tg_id = int(parts[3])

            users_repo = UsersRepository(session)
            pair_demo_repo = PairDemoRepository(session)
            pairs_repo = PairsRepository(session)
            consent_ip = getattr(callback.message, "ip", None)

            # Update consent
            user = await users_repo.update_consent(
                tg_id=callback.from_user.id,
                consent=True,
                consent_ip=consent_ip,
            )

            if not user:
                logger.error(
                    "Failed to save consent", tg_id=callback.from_user.id
                )
                await callback.answer(
                    get_message("START_CONSENT_SAVE_ERROR"), show_alert=True
                )
                return

            logger.info(
                "Consent saved from invite", tg_id=callback.from_user.id
            )

            # Get partner
            partner = await users_repo.get_by_tg_id(partner_tg_id)
            if not partner or not partner.preferred_mode:
                await callback.answer(
                    "❌ Партнёр ещё не выбрал режим общения.",
                    show_alert=True,
                )
                return

            # Check if pair already exists
            existing_pair = await pairs_repo.get_by_user_ids(
                user.id, partner.id
            )
            if existing_pair:
                await callback.answer(
                    "✅ Пара уже создана!", show_alert=True
                )
                return

            # Check if this pair was previously broken with lifetime subscription
            uid_a, uid_b = (user.id, partner.id) if user.id < partner.id else (partner.id, user.id)
            lifetime_history = await session.execute(
                select(LifetimePairHistory).where(
                    LifetimePairHistory.uid_a == uid_a,
                    LifetimePairHistory.uid_b == uid_b,
                )
            )
            if lifetime_history.scalar_one_or_none():
                await callback.answer(
                    get_message("START_LIFETIME_PAIR_BROKEN"),
                    show_alert=True,
                )
                return

            # Check if THIS PAIR already used demo
            pair_used_demo = await pair_demo_repo.is_used(user.id, partner.id)

            if pair_used_demo:
                await callback.answer(
                    get_message("START_BOTH_DEMO_USED"),
                    show_alert=True,
                )
                return

            # Get delivery_chat from FSM state or use default
            # Note: We use invited user's delivery_chat preference (if available)
            # In future, we could store preferred_delivery_chat in User model
            delivery_chat = DeliveryChat.BOT_DM.value  # Default
            if state:
                state_data = await state.get_data()
                delivery_chat = state_data.get("delivery_chat", DeliveryChat.BOT_DM.value)
            
            # Create pair with partner's preferred mode
            pair = await pairs_repo.create(
                uid_a=partner.id,
                uid_b=user.id,
                mode=partner.preferred_mode,
                delivery_chat=delivery_chat,
            )

            # Create subscription (trial) - 7 days
            subs_repo = SubscriptionsRepository(session)
            trial_end = date.today() + timedelta(days=TRIAL_PERIOD_DAYS)
            await subs_repo.create(
                pair_id=pair.id,
                payer_id=partner.id,
                period_end=trial_end,
            )

            # Mark this pair as demo used
            await pair_demo_repo.mark_pair(user.id, partner.id)
            await session.commit()
            
            logger.info(
                "Pair created and committed (consent callback)",
                tg_id=callback.from_user.id,
                partner_tg_id=partner_tg_id,
                pair_id=pair.id,
            )

            # After commit, wrap message sending in try-except to prevent rollback
            # of already committed data if sending fails
            try:
                mode_text = (
                    "💬 Чат"
                    if partner.preferred_mode == "chat"
                    else "💔 Безмолвие"
                )
                await callback.answer(
                    get_message("START_PAIR_CREATED_ALERT"), show_alert=False
                )
                await callback.message.edit_text(
                    get_message(
                        "START_PAIR_CREATED",
                        mode_text=mode_text,
                        days=TRIAL_PERIOD_DAYS,
                        days_text=get_days_text(TRIAL_PERIOD_DAYS),
                    )
                )

                # If pair_dm mode was selected, send anchor message
                if delivery_chat == DeliveryChat.PAIR_DM.value:
                    await send_anchor_message_after_pair_creation(
                        callback, session, pair.id, user.tg_id, partner.tg_id
                    )

                # Notify partner
                username = (
                    callback.from_user.username
                    or get_message("START_USERNAME_FALLBACK")
                )
                await send_message_with_retry(
                    chat_id=partner_tg_id,
                    text=get_message(
                        "START_PAIR_CREATED_PARTNER",
                        username=username,
                        days=TRIAL_PERIOD_DAYS,
                        days_text=get_days_text(TRIAL_PERIOD_DAYS),
                    ),
                )
            except Exception as e:
                # Log error but don't raise - pair is already committed
                logger.error(
                    "Error sending messages after pair creation (consent callback)",
                    error=str(e),
                    pair_id=pair.id,
                    tg_id=callback.from_user.id,
                    partner_tg_id=partner_tg_id,
                    exc_info=True,
                )
                # Try to send at least basic message to user
                try:
                    await callback.answer(
                        get_message("START_PAIR_CREATED_ALERT"), show_alert=False
                    )
                except Exception:
                    pass  # Ignore if this also fails
            
            return

        # Regular consent (not from invite)
        user_id = int(parts[1])

        users_repo = UsersRepository(session)
        consent_ip = getattr(callback.message, "ip", None)

        user = await users_repo.update_consent(
            tg_id=callback.from_user.id,
            consent=True,
            consent_ip=consent_ip,
        )

        if user:
            logger.info("Consent saved", tg_id=callback.from_user.id)
            await callback.answer(get_message("START_CONSENT_ACCEPTED"))
            await callback.message.edit_text(
                get_message("START_MODE_SELECTION_PROMPT")
            )
            await callback.message.edit_reply_markup(
                reply_markup=get_mode_keyboard()
            )
        else:
            logger.error(
                "Failed to save consent", tg_id=callback.from_user.id
            )
            await callback.answer(
                get_message("START_CONSENT_SAVE_ERROR"), show_alert=True
            )
    except Exception as e:
        logger.error("Error in handle_consent", error=str(e), exc_info=True)
        await callback.answer(
                get_message("START_ERROR"), show_alert=True
        )


async def get_invite_link(tg_id: int, bot: Bot) -> str:
    """Generate invite link for user."""
    try:
        # Get bot username
        bot_info = await bot.get_me()
        bot_username = bot_info.username
        logger.debug("Bot info", username=bot_username, bot_id=bot_info.id)
        
        if not bot_username:
            # Fallback: use bot ID if username is not set
            bot_id = bot_info.id
            link = f"https://t.me/bot{bot_id}?start={tg_id}"
            logger.debug("Using bot ID fallback", link=link)
            return link
        
        # Use tg_id as invite code (simple approach)
        # In production, you might want to use a hash or separate invite_code field
        link = f"https://t.me/{bot_username}?start={tg_id}"
        logger.debug("Generated invite link", link=link)
        return link
    except Exception as e:
        logger.error("Error generating invite link", error=str(e), exc_info=True)
        raise


async def show_delivery_choice(callback: CallbackQuery) -> None:
    """Show delivery choice screen."""
    try:
        text = get_message("DELIVERY_CHOICE_TITLE")
        
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=get_message("DELIVERY_BOT_DM"),
                        callback_data="choose_delivery:bot_dm",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        text=get_message("DELIVERY_PAIR_DM"),
                        callback_data="choose_delivery:pair_dm",
                    ),
                ],
            ]
        )
        
        await callback.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        await callback.answer()
    except Exception as e:
        logger.error("Error showing delivery choice", error=str(e), exc_info=True)
        await callback.answer(get_message("START_ERROR"), show_alert=True)


async def show_invite_link(message_or_callback: Message | CallbackQuery, tg_id: int, mode: str, bot: Bot) -> None:
    """Show invite link to user."""
    try:
        logger.info("Generating invite link", tg_id=tg_id, mode=mode)
        invite_link = await get_invite_link(tg_id, bot)
        logger.info("Invite link generated", tg_id=tg_id, invite_link=invite_link)
        
        mode_text = "💬 Чат" if mode == "chat" else "💔 Безмолвие"

        text = get_message(
            "START_MODE_SELECTED_MESSAGE",
            mode_text=mode_text,
            invite_link=invite_link,
        )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=get_message("START_SHARE_BUTTON"),
                        url=f"https://t.me/share/url?url={invite_link}&text={get_message('START_SHARE_TEXT').replace(' ', '%20')}",
                    ),
                ],
            ]
        )

        if isinstance(message_or_callback, CallbackQuery):
            logger.info("Editing message with invite link", tg_id=tg_id)
            await message_or_callback.message.edit_text(
                text, reply_markup=keyboard, parse_mode=ParseMode.HTML
            )
            await message_or_callback.answer()
            logger.info("Invite link sent successfully", tg_id=tg_id)
        else:
            # Chat mode no longer requires /link - cards are sent directly to partner's chat
            pass
            logger.info("Sending message with invite link", tg_id=tg_id)
            await message_or_callback.answer(
                text, reply_markup=keyboard, parse_mode=ParseMode.HTML
            )
            logger.info("Invite link sent successfully", tg_id=tg_id)
    except Exception as e:
        logger.error("Error showing invite link", error=str(e), exc_info=True)
        error_text = get_message("START_INVITE_LINK_ERROR")
        try:
            if isinstance(message_or_callback, CallbackQuery):
                await message_or_callback.answer(error_text, show_alert=True)
            else:
                await message_or_callback.answer(error_text)
        except Exception as send_error:
            logger.error("Failed to send error message", error=str(send_error))


@router.callback_query(F.data == "mode_chat")
async def handle_mode_chat(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    """Handle chat mode selection."""
    try:
        logger.info("Callback received", callback_data=callback.data, tg_id=callback.from_user.id)
        users_repo = UsersRepository(session)
        tg_id = callback.from_user.id

        logger.info("Mode chat selected", tg_id=tg_id)

        # Save preferred mode
        user = await users_repo.update_preferred_mode(tg_id, "chat")
        if user:
            logger.info("Preferred mode saved", tg_id=tg_id, mode="chat")
            # Save mode in FSM state for delivery choice
            await state.update_data(preferred_mode="chat")
            # Show delivery choice instead of invite link
            await show_delivery_choice(callback)
        else:
            logger.error("Failed to save preferred mode", tg_id=tg_id)
            await callback.answer(get_message("START_MODE_SAVE_ERROR"), show_alert=True)
    except Exception as e:
        logger.error("Error in handle_mode_chat", error=str(e), exc_info=True)
        await callback.answer(get_message("START_ERROR"), show_alert=True)


@router.callback_query(F.data == "mode_silent")
async def handle_mode_silent(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    """Handle silent mode selection."""
    try:
        logger.info("Callback received", callback_data=callback.data, tg_id=callback.from_user.id)
        users_repo = UsersRepository(session)
        tg_id = callback.from_user.id

        logger.info("Mode silent selected", tg_id=tg_id)

        # Save preferred mode
        user = await users_repo.update_preferred_mode(tg_id, "silent")
        if user:
            logger.info("Preferred mode saved", tg_id=tg_id, mode="silent")
            # Save mode in FSM state for delivery choice
            await state.update_data(preferred_mode="silent")
            # Show delivery choice instead of invite link
            await show_delivery_choice(callback)
        else:
            logger.error("Failed to save preferred mode", tg_id=tg_id)
            await callback.answer(get_message("START_MODE_SAVE_ERROR"), show_alert=True)
    except Exception as e:
        logger.error("Error in handle_mode_silent", error=str(e), exc_info=True)
        await callback.answer(get_message("START_ERROR"), show_alert=True)


@router.callback_query(F.data.startswith("choose_delivery:"))
async def handle_delivery_choice(callback: CallbackQuery, session: AsyncSession, state: FSMContext) -> None:
    """Handle delivery choice selection."""
    try:
        delivery_type = callback.data.split(":")[1]  # bot_dm or pair_dm
        tg_id = callback.from_user.id
        
        logger.info("Delivery choice selected", tg_id=tg_id, delivery_type=delivery_type)
        
        # Get mode from FSM state
        state_data = await state.get_data()
        mode = state_data.get("preferred_mode", "silent")  # Default to silent if not found
        
        # Save delivery choice in FSM state
        await state.update_data(delivery_chat=delivery_type)
        
        if delivery_type == "pair_dm":
            # Send anchor message to both users in their private chat
            await send_anchor_message(callback, session, state, tg_id, mode)
        else:
            # bot_dm - just show invite link
            bot = get_bot()
            await show_invite_link(callback, tg_id, mode, bot)
            await state.clear()
            
    except Exception as e:
        logger.error("Error handling delivery choice", error=str(e), exc_info=True)
        await callback.answer(get_message("START_ERROR"), show_alert=True)


async def send_anchor_message(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    tg_id: int,
    mode: str,
) -> None:
    """Send anchor message to pair's private chat for getting chat_id."""
    try:
        from src.db.repositories.users import UsersRepository
        
        users_repo = UsersRepository(session)
        user = await users_repo.get_by_tg_id(tg_id)
        
        if not user:
            await callback.answer(get_message("START_ERROR"), show_alert=True)
            return
        
        # Get partner if pair exists
        pairs_repo = PairsRepository(session)
        pair = await pairs_repo.get_by_user_tg_id(tg_id)
        
        bot = get_bot()
        
        if pair:
            # Pair already exists - get partner
            from src.db.models import User
            partner_id = pair.uid_b if pair.uid_a == user.id else pair.uid_a
            partner_result = await session.execute(
                select(User).where(User.id == partner_id)
            )
            partner = partner_result.scalar_one_or_none()
            
            if partner:
                # Send anchor message to private chat
                anchor_text = get_message("ANCHOR_MESSAGE")
                anchor_keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=get_message("ANCHOR_BTN"),
                                callback_data=f"anchor_pair_chat:{pair.id}",
                            ),
                        ],
                    ]
                )
                
                # Send anchor message to partner's private chat
                # The button will be clicked in the private chat, giving us the chat_id
                try:
                    # Send anchor message to partner (they will click button in their private chat with user)
                    # We send to partner, and they forward/share it to their private chat with user
                    # Actually, we need to send it directly to the private chat
                    # But bot can't send to private chat between two users directly
                    # So we send to both users and ask them to forward/share to their private chat
                    
                    # Send anchor message to both users
                    # They need to forward it to their private chat and click button there
                    anchor_instruction = (
                        f"{anchor_text}\n\n"
                        "Перешлите это сообщение в ваш личный чат с партнёром и нажмите кнопку ▶️ там."
                    )
                    
                    # Send to current user
                    await bot.send_message(
                        chat_id=tg_id,
                        text=anchor_instruction,
                        reply_markup=anchor_keyboard,
                    )
                    
                    # Send to partner
                    await bot.send_message(
                        chat_id=partner.tg_id,
                        text=anchor_instruction,
                        reply_markup=anchor_keyboard,
                    )
                    
                    await callback.message.edit_text(
                        "✅ Сообщения отправлены обоим пользователям. "
                        "Перешлите сообщение в ваш личный чат с партнёром и нажмите кнопку ▶️ там."
                    )
                    await callback.answer()
                except Exception as e:
                    logger.error("Error sending anchor message", error=str(e), exc_info=True)
                    await callback.answer("Ошибка при отправке сообщения", show_alert=True)
        else:
            # No pair yet - save delivery choice and show invite link
            # When pair is created, we'll use this delivery_chat
            await state.update_data(delivery_chat="pair_dm")
            await show_invite_link(callback, tg_id, mode, bot)
            
    except Exception as e:
        logger.error("Error in send_anchor_message", error=str(e), exc_info=True)
        await callback.answer(get_message("START_ERROR"), show_alert=True)


@router.callback_query(F.data.startswith("anchor_pair_chat:"))
async def handle_anchor_pair_chat(callback: CallbackQuery, session: AsyncSession) -> None:
    """Handle anchor button click - get chat_id from private chat."""
    try:
        pair_id = int(callback.data.split(":")[1])
        chat_id = callback.message.chat.id
        tg_id = callback.from_user.id
        
        logger.info(
            "Anchor button clicked",
            pair_id=pair_id,
            chat_id=chat_id,
            tg_id=tg_id,
        )
        
        pairs_repo = PairsRepository(session)
        pair = await pairs_repo.get_by_id(pair_id)
        
        if not pair:
            await callback.answer("Пара не найдена", show_alert=True)
            return
        
        # Verify user is part of this pair
        from src.db.models import User
        user_result = await session.execute(
            select(User).where(User.tg_id == tg_id)
        )
        user = user_result.scalar_one_or_none()
        
        if not user or (user.id != pair.uid_a and user.id != pair.uid_b):
            await callback.answer("Вы не являетесь участником этой пары", show_alert=True)
            return
        
        # Get partner
        partner_id = pair.uid_b if user.id == pair.uid_a else pair.uid_a
        partner_result = await session.execute(
            select(User).where(User.id == partner_id)
        )
        partner = partner_result.scalar_one_or_none()
        
        if not partner:
            await callback.answer("Партнёр не найден", show_alert=True)
            return
        
        # Check if this is a private chat (not a group)
        if callback.message.chat.type != "private":
            await callback.answer(
                "Это не личный чат. Перешлите сообщение в ваш личный чат с партнёром.",
                show_alert=True
            )
            return
        
        # For private chat between user A and user B:
        # When bot receives callback from private chat, chat_id = the chat's ID
        # For private chat between two users, Telegram uses one of the user IDs as chat_id
        # Verify: chat_id should be either user's tg_id or partner's tg_id
        if chat_id != tg_id and chat_id != partner.tg_id:
            await callback.answer(
                "Неверный чат. Убедитесь, что вы переслали сообщение в ваш личный чат с партнёром.",
                show_alert=True
            )
            return
        
        # Use chat_id as private_chat_id
        # This is the ID of the private chat between the two users
        private_chat_id = chat_id
        
        # Update pair with private_chat_id
        await session.execute(
            update(Pair)
            .where(Pair.id == pair_id)
            .values(
                private_chat_id=private_chat_id,
                delivery_chat=DeliveryChat.PAIR_DM.value,
            )
        )
        await session.commit()
        
        # Delete anchor message
        try:
            await callback.message.delete()
        except Exception:
            pass  # Ignore if deletion fails
        
        # Send confirmation to user
        await callback.answer("✅ Чат подключён!", show_alert=False)
        
        # Send confirmation message
        bot = get_bot()
        await bot.send_message(
            chat_id=chat_id,
            text="✅ Чат подключён! Теперь пожелания будут приходить сюда.",
        )
        
        # Notify partner
        try:
            await bot.send_message(
                chat_id=partner.tg_id,
                text="✅ Ваш партнёр подключил личный чат. Пожелания теперь будут приходить туда.",
            )
        except Exception:
            pass  # Ignore if notification fails
            
    except Exception as e:
        logger.error("Error handling anchor pair chat", error=str(e), exc_info=True)
        await callback.answer("Ошибка при подключении чата", show_alert=True)


async def send_anchor_message_after_pair_creation(
    message_or_callback: Message | CallbackQuery,
    session: AsyncSession,
    pair_id: int,
    user_tg_id: int,
    partner_tg_id: int,
) -> None:
    """Send anchor message after pair creation for pair_dm mode."""
    try:
        anchor_text = get_message("ANCHOR_MESSAGE")
        anchor_keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text=get_message("ANCHOR_BTN"),
                        callback_data=f"anchor_pair_chat:{pair_id}",
                    ),
                ],
            ]
        )
        
        anchor_instruction = (
            f"{anchor_text}\n\n"
            "Перешлите это сообщение в ваш личный чат с партнёром и нажмите кнопку ▶️ там."
        )
        
        bot = get_bot()
        
        # Send to both users
        await bot.send_message(
            chat_id=user_tg_id,
            text=anchor_instruction,
            reply_markup=anchor_keyboard,
        )
        
        await bot.send_message(
            chat_id=partner_tg_id,
            text=anchor_instruction,
            reply_markup=anchor_keyboard,
        )
        
        # Send instruction message
        if isinstance(message_or_callback, CallbackQuery):
            await message_or_callback.message.answer(
                "✅ Сообщения отправлены обоим пользователям. "
                "Перешлите сообщение в ваш личный чат с партнёром и нажмите кнопку ▶️ там."
            )
        else:
            await message_or_callback.answer(
                "✅ Сообщения отправлены обоим пользователям. "
                "Перешлите сообщение в ваш личный чат с партнёром и нажмите кнопку ▶️ там."
            )
    except Exception as e:
        logger.error("Error sending anchor message after pair creation", error=str(e), exc_info=True)

