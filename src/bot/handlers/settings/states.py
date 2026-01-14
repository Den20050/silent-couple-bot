"""FSM states for settings handlers."""

from aiogram.fsm.state import State, StatesGroup


class SettingsStates(StatesGroup):
    """FSM states for settings."""
    waiting_nickname = State()
    selecting_partner = State()

