from aiogram.fsm.state import State, StatesGroup

class BotStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_mode = State()
    video_mode = State()
    music_mode = State()
