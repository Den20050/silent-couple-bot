"""Feedback handlers."""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import Settings
from src.core.logger import get_logger
from src.core.messages import get_message
from src.db.repositories.users import UsersRepository
from src.bot.handlers.feedback.use_cases.send_feedback import send_feedback_to_admin
from src.bot.handlers.feedback.states import FeedbackStates
from src.services.messaging.user_command_session import track_user_command

logger = get_logger(__name__)

router = Router(name="feedback_handlers")


@router.message(Command("feedback"))
async def cmd_feedback(message: Message, session: AsyncSession, state: FSMContext) -> None:
    """Handle /feedback command - request description."""
    try:
        tg_id = message.from_user.id

        users_repo = UsersRepository(session)
        user = await users_repo.get_by_tg_id(tg_id)

        if not user:
            await message.answer(get_message("FEEDBACK_START_REQUIRED"))
            return

        await track_user_command(message)

        # Set FSM state and request description
        await state.set_state(FeedbackStates.waiting_description)
        
        text = get_message("FEEDBACK_DESCRIPTION_PROMPT")
        
        from src.services.messaging.templates import KeyboardTemplates
        keyboard = KeyboardTemplates.back_only()
        
        await message.answer(text, reply_markup=keyboard, parse_mode="HTML")
        
        logger.info(
            "Feedback description requested",
            tg_id=tg_id,
        )
    except Exception as e:
        logger.error("Error in cmd_feedback", error=str(e), exc_info=True)
        await message.answer(get_message("MENU_ERROR"))


@router.message(FeedbackStates.waiting_description, F.text & ~F.text.startswith("/"))
async def handle_feedback_description(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    settings: Settings,
) -> None:
    """Handle feedback description input."""
    try:
        tg_id = message.from_user.id
        
        # Verify we're in the correct state
        current_state = await state.get_state()
        if current_state != FeedbackStates.waiting_description:
            logger.debug(
                "handle_feedback_description called but state doesn't match",
                tg_id=tg_id,
                current_state=str(current_state),
                expected_state="FeedbackStates:waiting_description",
            )
            return
        
        logger.info(
            "Processing feedback description",
            tg_id=tg_id,
            message_length=len(message.text) if message.text else 0,
        )
        
        # Check username
        username = message.from_user.username
        if not username:
            logger.warning(
                "Feedback description submitted without username",
                tg_id=tg_id,
            )
            await state.clear()
            await message.answer(get_message("FEEDBACK_NO_USERNAME"))
            return
        
        # Get message text
        text = message.text or message.caption or ""
        if not text.strip():
            await message.answer("Пожалуйста, отправьте описание проблемы.")
            return
        
        logger.info(
            "Sending feedback to admin",
            tg_id=tg_id,
            username=username,
            text_preview=text[:50],
        )
        
        # Send feedback to admin
        success, response_message = await send_feedback_to_admin(
            message_text=text,
            tg_id=tg_id,
            username=username,
            session=session,
            settings=settings,
            bot=message.bot,
        )
        
        # Clear FSM state
        await state.clear()
        
        logger.info(
            "Feedback sent",
            tg_id=tg_id,
            success=success,
        )
        
        if success:
            await message.answer(response_message)
        else:
            await message.answer(response_message)
            
    except Exception as e:
        logger.error(
            "Error in handle_feedback_description",
            error=str(e),
            tg_id=message.from_user.id if message else None,
            exc_info=True,
        )
        await state.clear()
        await message.answer(get_message("MENU_ERROR"))


@router.message(Command("cancel"))
async def handle_feedback_cancel(
    message: Message,
    state: FSMContext,
) -> None:
    """Handle cancel command for feedback description input."""
    try:
        current_state = await state.get_state()
        if current_state == FeedbackStates.waiting_description:
            await state.clear()
            await message.answer("❌ Ввод описания отменен.")
        else:
            # Not in feedback state, ignore
            pass
    except Exception as e:
        logger.error("Error in handle_feedback_cancel", error=str(e), exc_info=True)
