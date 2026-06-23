from aiogram.fsm.state import State, StatesGroup


class GoalForm(StatesGroup):
    baseline = State()       # Где я сейчас
    target = State()         # Куда хочу за 90 дней
    weak_point = State()     # Что мешает
    first_step = State()     # Первый шаг на эту неделю
    confirm_reset = State()  # Подтверждение сброса цели


class ReportForm(StatesGroup):
    done = State()    # Что сделал с прошлого раза
    metric = State()  # Какая цифра сдвинулась
    stuck = State()   # Где застрял / нужна помощь
