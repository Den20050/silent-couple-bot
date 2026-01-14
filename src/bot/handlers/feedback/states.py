"""FSM states for feedback handlers."""

from aiogram.fsm.state import State, StatesGroup


class FeedbackStates(StatesGroup):
    """FSM states for feedback."""
    waiting_description = State()

