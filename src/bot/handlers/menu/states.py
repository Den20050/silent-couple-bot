"""FSM states for menu handlers."""

from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    """FSM states for admin actions."""
    waiting_tg_id = State()
    waiting_tariff = State()
    waiting_broadcast_message = State()
    waiting_pair_selection = State()

