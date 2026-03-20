"""Payment handlers."""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.constants import SUPPORTED_CURRENCIES
from src.core.logger import get_logger
from src.core.messages import get_message
from src.services.application.payment import PaymentApplicationService

logger = get_logger(__name__)

router = Router(name="pay_handlers")


@router.message(Command("pay"))
async def cmd_pay(
    message: Message,
    session: AsyncSession,
    payment_application_service: PaymentApplicationService,
) -> None:
    """Handle /pay command."""
    tg_id = message.from_user.id
    
    # Check if user has multiple pairs
    from src.db.repositories.pairs import PairsRepository
    pairs_repo = PairsRepository(session)
    all_pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)
    
    if len(all_pairs) > 1:
        # Show pair selection
        success, message_text, keyboard = await payment_application_service.show_pair_selection(tg_id=tg_id)
        if success:
            await message.answer(message_text, reply_markup=keyboard)
        else:
            await message.answer(message_text)
    else:
        # Single pair - show currency selection directly
        success, message_text, keyboard = await payment_application_service.show_currencies(tg_id=tg_id)
        if success:
            await message.answer(message_text, reply_markup=keyboard)
        else:
            await message.answer(message_text)


@router.callback_query(F.data == "pay_now")
async def handle_pay_now_callback(
    callback: CallbackQuery,
    session: AsyncSession,
    payment_application_service: PaymentApplicationService,
) -> None:
    """Handle pay_now callback from menu or notifications."""
    tg_id = callback.from_user.id
    
    # Check if user has multiple pairs
    from src.db.repositories.pairs import PairsRepository
    pairs_repo = PairsRepository(session)
    all_pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)
    
    if len(all_pairs) > 1:
        # Show pair selection
        success, message_text, keyboard = await payment_application_service.show_pair_selection(tg_id=tg_id)
        if success:
            await callback.message.edit_text(message_text, reply_markup=keyboard)
        else:
            await callback.answer(message_text, show_alert=True)
    else:
        # Single pair - show currency selection directly
        success, message_text, keyboard = await payment_application_service.show_currencies(tg_id=tg_id)
        if success:
            await callback.message.edit_text(message_text, reply_markup=keyboard)
        else:
            await callback.answer(message_text, show_alert=True)
    await callback.answer()


@router.callback_query(F.data.startswith("pay_select_currency"))
async def handle_pay_select_currency(
    callback: CallbackQuery,
    payment_application_service: PaymentApplicationService,
) -> None:
    """Handle currency selection (with optional pair_id)."""
    tg_id = callback.from_user.id
    
    # Extract pair_id if present: pay_select_currency_{pair_id} or just pay_select_currency
    parts = callback.data.split("_")
    pair_id = None
    if len(parts) == 4 and parts[0] == "pay" and parts[1] == "select" and parts[2] == "currency":
        try:
            pair_id = int(parts[3])
        except ValueError:
            pass
    
    success, message_text, keyboard = await payment_application_service.show_currencies(
        tg_id=tg_id,
        pair_id=pair_id,
    )
    
    await callback.message.edit_text(message_text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("select_currency_"))
async def handle_select_currency(
    callback: CallbackQuery,
    payment_application_service: PaymentApplicationService,
) -> None:
    """Handle currency selection (with optional pair_id)."""
    tg_id = callback.from_user.id
    
    # Extract currency_code and optional pair_id
    # Format: select_currency_{currency_code} or select_currency_{currency_code}_{pair_id}
    parts = callback.data.replace("select_currency_", "").split("_")
    currency_code = parts[0]
    pair_id = None
    
    if len(parts) > 1:
        try:
            pair_id = int(parts[1])
        except ValueError:
            pass
    
    # Currency validation is done in application service (raises ValidationError on invalid)
    success, message_text, keyboard = await payment_application_service.show_tariffs(
        tg_id=tg_id,
        currency_code=currency_code,
        pair_id=pair_id,
    )
    
    await callback.message.edit_text(message_text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data == "select_tariff_from_expired")
async def handle_select_tariff_from_expired(
    callback: CallbackQuery,
    session: AsyncSession,
    payment_application_service: PaymentApplicationService,
) -> None:
    """Handle 'Выбрать тариф' button from expired demo notification."""
    tg_id = callback.from_user.id
    
    # Check if user has multiple pairs
    from src.db.repositories.pairs import PairsRepository
    pairs_repo = PairsRepository(session)
    all_pairs = await pairs_repo.get_all_by_user_tg_id(tg_id)
    
    if len(all_pairs) > 1:
        # Show pair selection
        success, message_text, keyboard = await payment_application_service.show_pair_selection(tg_id=tg_id)
        if success:
            await callback.message.edit_text(message_text, reply_markup=keyboard)
        else:
            await callback.answer(message_text, show_alert=True)
    else:
        # Single pair - show currency selection directly
        success, message_text, keyboard = await payment_application_service.show_currencies(tg_id=tg_id)
        if success:
            await callback.message.edit_text(message_text, reply_markup=keyboard)
        else:
            await callback.answer(message_text, show_alert=True)
    await callback.answer()


@router.callback_query(F.data.startswith("pay_select_pair_"))
async def handle_select_pair(
    callback: CallbackQuery,
    payment_application_service: PaymentApplicationService,
) -> None:
    """Handle pair selection for payment."""
    tg_id = callback.from_user.id
    pair_id = int(callback.data.replace("pay_select_pair_", ""))
    
    try:
        # Show currency selection for selected pair
        success, message_text, keyboard = (
            await payment_application_service.show_currencies(
                tg_id=tg_id,
                pair_id=pair_id,
            )
        )
        await callback.message.edit_text(message_text, reply_markup=keyboard)
        await callback.answer()
    except Exception as exc:
        from src.bot.exceptions import BotException

        if isinstance(exc, BotException):
            message_text = exc.message or get_message(exc.message_key)
            await callback.answer(message_text, show_alert=True)
            return
        logger.error(
            "Error in handle_select_pair",
            tg_id=tg_id,
            pair_id=pair_id,
            error=str(exc),
            exc_info=True,
        )
        await callback.answer(get_message("PAY_ERROR"), show_alert=True)


@router.callback_query(F.data.startswith("select_tariff_"))
async def handle_select_tariff(
    callback: CallbackQuery,
    payment_application_service: PaymentApplicationService,
) -> None:
    """Handle tariff selection - show terms confirmation."""
    tg_id = callback.from_user.id
    # Format: select_tariff_{plan_id}_{currency_code} or select_tariff_{plan_id}_{currency_code}_{pair_id}
    parts = callback.data.replace("select_tariff_", "").split("_")
    
    pair_id = None
    if len(parts) >= 3:
        # Check if last part is a number (pair_id)
        try:
            potential_pair_id = int(parts[-1])
            # If it's a valid pair_id (reasonable range), use it
            if 1 <= potential_pair_id <= 999999:
                pair_id = potential_pair_id
                parts = parts[:-1]  # Remove pair_id from parts
        except ValueError:
            pass
    
    if len(parts) < 2:
        # Backward compatibility: try to extract from old format
        plan_id = parts[0] if parts else ""
        currency_code = "RUB"  # Default to RUB
    else:
        # Format: plan_id_currency_code
        # Handle plan_id that might contain underscores (like "1_month")
        # Last part is currency_code, everything before is plan_id
        currency_code = parts[-1]
        plan_id = "_".join(parts[:-1])
    
    # Currency validation is done in application service (raises ValidationError on invalid)
    # Fallback to RUB for backward compatibility
    from src.core.constants import SUPPORTED_CURRENCIES
    if currency_code not in SUPPORTED_CURRENCIES:
        currency_code = "RUB"
    
    # Show terms confirmation page instead of creating payment immediately
    success, message_text, keyboard = await payment_application_service.show_terms_confirmation(
        tg_id=tg_id,
        plan_id=plan_id,
        currency_code=currency_code,
        pair_id=pair_id,
    )
    
    await callback.message.edit_text(message_text, reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_and_pay_"))
async def handle_confirm_and_pay(
    callback: CallbackQuery,
    payment_application_service: PaymentApplicationService,
) -> None:
    """Handle terms confirmation and create payment."""
    tg_id = callback.from_user.id
    # Format: confirm_and_pay_{plan_id}_{currency_code} or confirm_and_pay_{plan_id}_{currency_code}_{pair_id}
    parts = callback.data.replace("confirm_and_pay_", "").split("_")
    
    pair_id = None
    if len(parts) >= 3:
        # Check if last part is a number (pair_id)
        try:
            potential_pair_id = int(parts[-1])
            # If it's a valid pair_id (reasonable range), use it
            if 1 <= potential_pair_id <= 999999:
                pair_id = potential_pair_id
                parts = parts[:-1]  # Remove pair_id from parts
        except ValueError:
            pass
    
    if len(parts) < 2:
        # Backward compatibility: try to extract from old format
        plan_id = parts[0] if parts else ""
        currency_code = "RUB"  # Default to RUB
    else:
        # Format: plan_id_currency_code
        # Handle plan_id that might contain underscores (like "1_month")
        # Last part is currency_code, everything before is plan_id
        currency_code = parts[-1]
        plan_id = "_".join(parts[:-1])
    
    # Currency validation is done in application service (raises ValidationError on invalid)
    # Fallback to RUB for backward compatibility
    from src.core.constants import SUPPORTED_CURRENCIES
    if currency_code not in SUPPORTED_CURRENCIES:
        currency_code = "RUB"
    
    # User confirmed terms - create payment
    success, message_text, keyboard = await payment_application_service.create_payment_for_tariff(
        tg_id=tg_id,
        plan_id=plan_id,
        currency_code=currency_code,
        pair_id=pair_id,
    )
    
    await callback.message.edit_text(message_text, reply_markup=keyboard)
    await callback.answer(get_message("PAY_LINK_CREATED"))


@router.callback_query(F.data == "pay_back_to_menu")
async def handle_pay_back_to_menu(
    callback: CallbackQuery,
    session: AsyncSession,  # noqa: ARG001
) -> None:
    """Handle back to menu from payment tariffs - delete message."""
    try:
        # Delete the message with tariffs
        await callback.message.delete()
        await callback.answer()
    except Exception as e:
        logger.error(
            "Error in handle_pay_back_to_menu",
            error=str(e),
            exc_info=True,
        )
        # If deletion fails, try to answer anyway
        try:
            await callback.answer()
        except Exception:
            pass

