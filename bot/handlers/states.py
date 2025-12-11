from aiogram.fsm.state import State, StatesGroup


class TestStates(StatesGroup):
    waiting_full_name = State()
    choosing_role = State()
    answering = State()
