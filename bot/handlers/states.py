from aiogram.fsm.state import State, StatesGroup


class TestStates(StatesGroup):
    waiting_full_name = State()
    waiting_position = State()
    answering = State()
