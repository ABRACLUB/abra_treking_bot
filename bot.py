"""
Бот для трекинга целей участников группы.
Структура:
- Пользователь задаёт цель один раз (базовая линия, куда идёт, слабое звено, первый шаг)
- Каждую пятницу в 17:00 бот запрашивает недельный отчёт
"""

import asyncio
import logging
from datetime import datetime, time

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import BOT_TOKEN, ADMIN_ID
from database import Database
from states import GoalForm, ReportForm

# Логирование
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Инициализация
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
db = Database("goals.db")
scheduler = AsyncIOScheduler(timezone="Europe/Moscow")


# ─────────────────────────────────────────────
# СТАРТ
# ─────────────────────────────────────────────

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name

    existing = db.get_goal(user_id)
    if existing:
        await message.answer(
            f"👋 Привет, @{username}!\n\n"
            f"Твоя цель уже зафиксирована. Используй /goal чтобы посмотреть её, "
            f"или /report чтобы оставить отчёт вручную.",
            reply_markup=main_keyboard()
        )
        return

    await message.answer(
        f"👋 Привет, @{username}!\n\n"
        f"Давай зафиксируем твою цель на 90 дней. Я задам 4 вопроса.\n\n"
        f"<b>Вопрос 1/4</b>\n"
        f"📍 <b>Где я сейчас</b> — стартовая цифра / baseline.\n\n"
        f"Напиши одним сообщением, например:\n"
        f"<i>«Выручка 200к/мес», «Вес 94 кг», «0 клиентов»</i>",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(GoalForm.baseline)


# ─────────────────────────────────────────────
# ФОРМА ЦЕЛИ (4 шага)
# ─────────────────────────────────────────────

@dp.message(GoalForm.baseline)
async def goal_baseline(message: Message, state: FSMContext):
    await state.update_data(baseline=message.text.strip())
    await message.answer(
        f"✅ Записал.\n\n"
        f"<b>Вопрос 2/4</b>\n"
        f"🎯 <b>Куда хочу за 90 дней</b> — целевая цифра.\n\n"
        f"Например: <i>«500к/мес», «Вес 85 кг», «10 клиентов»</i>",
        parse_mode="HTML"
    )
    await state.set_state(GoalForm.target)


@dp.message(GoalForm.target)
async def goal_target(message: Message, state: FSMContext):
    await state.update_data(target=message.text.strip())
    await message.answer(
        f"✅ Записал.\n\n"
        f"<b>Вопрос 3/4</b>\n"
        f"🔍 <b>Что мешает</b> — слабое звено.\n\n"
        f"Например: <i>«Нет системы продаж», «Откладываю тренировки», «Не умею делегировать»</i>",
        parse_mode="HTML"
    )
    await state.set_state(GoalForm.weak_point)


@dp.message(GoalForm.weak_point)
async def goal_weak_point(message: Message, state: FSMContext):
    await state.update_data(weak_point=message.text.strip())
    await message.answer(
        f"✅ Записал.\n\n"
        f"<b>Вопрос 4/4</b>\n"
        f"👣 <b>Первый шаг на эту неделю</b> — конкретное действие.\n\n"
        f"Например: <i>«Позвонить 5 клиентам», «Записаться в зал», «Делегировать отчёт Ивану»</i>",
        parse_mode="HTML"
    )
    await state.set_state(GoalForm.first_step)


@dp.message(GoalForm.first_step)
async def goal_first_step(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    first_step = message.text.strip()

    db.save_goal(
        user_id=user_id,
        username=username,
        baseline=data["baseline"],
        target=data["target"],
        weak_point=data["weak_point"],
        first_step=first_step,
    )

    summary = (
        f"🏁 <b>Цель зафиксирована!</b>\n\n"
        f"👤 @{username}\n"
        f"📍 Где сейчас: {data['baseline']}\n"
        f"🎯 Куда за 90 дней: {data['target']}\n"
        f"🔍 Что мешает: {data['weak_point']}\n"
        f"👣 Первый шаг: {first_step}\n\n"
        f"Каждую <b>пятницу в 17:00</b> я напомню оставить недельный отчёт. 💪"
    )

    await message.answer(summary, parse_mode="HTML", reply_markup=main_keyboard())
    await state.clear()

    # Уведомить админа
    if ADMIN_ID:
        await bot.send_message(
            ADMIN_ID,
            f"📥 Новая цель от @{username} (id: {user_id})\n\n{summary}",
            parse_mode="HTML"
        )


# ─────────────────────────────────────────────
# ПРОСМОТР СВОЕЙ ЦЕЛИ
# ─────────────────────────────────────────────

@dp.message(Command("goal"))
@dp.message(F.text == "🎯 Моя цель")
async def show_goal(message: Message):
    user_id = message.from_user.id
    goal = db.get_goal(user_id)

    if not goal:
        await message.answer(
            "У тебя ещё нет зафиксированной цели. Напиши /start чтобы начать.",
            reply_markup=main_keyboard()
        )
        return

    created = goal["created_at"][:10]
    await message.answer(
        f"🎯 <b>Твоя цель</b> (зафиксирована {created})\n\n"
        f"📍 Где сейчас: {goal['baseline']}\n"
        f"🏁 Куда за 90 дней: {goal['target']}\n"
        f"🔍 Слабое звено: {goal['weak_point']}\n"
        f"👣 Первый шаг: {goal['first_step']}",
        parse_mode="HTML",
        reply_markup=main_keyboard()
    )


# ─────────────────────────────────────────────
# СБРОС ЦЕЛИ (начать заново)
# ─────────────────────────────────────────────

@dp.message(Command("reset"))
async def reset_goal(message: Message, state: FSMContext):
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="✅ Да, сбросить"), KeyboardButton(text="❌ Отмена")]],
        resize_keyboard=True
    )
    await message.answer(
        "⚠️ Ты хочешь сбросить текущую цель и начать заново?\n"
        "Все отчёты сохранятся, но цель будет перезаписана.",
        reply_markup=kb
    )
    await state.set_state(GoalForm.confirm_reset)


@dp.message(GoalForm.confirm_reset)
async def confirm_reset(message: Message, state: FSMContext):
    if message.text == "✅ Да, сбросить":
        db.delete_goal(message.from_user.id)
        await state.clear()
        await message.answer(
            "Цель сброшена. Напиши /start чтобы задать новую.",
            reply_markup=main_keyboard()
        )
    else:
        await state.clear()
        await message.answer("Хорошо, ничего не меняем.", reply_markup=main_keyboard())


# ─────────────────────────────────────────────
# РУЧНОЙ ОТЧЁТ
# ─────────────────────────────────────────────

@dp.message(Command("report"))
@dp.message(F.text == "📋 Отчёт")
async def cmd_report(message: Message, state: FSMContext):
    goal = db.get_goal(message.from_user.id)
    if not goal:
        await message.answer("Сначала зафикси цель — напиши /start.")
        return

    await message.answer(
        f"📋 <b>Недельный отчёт</b>\n\n"
        f"<b>Вопрос 1/3</b>\n"
        f"✅ <b>Что сделал с прошлого раза?</b>\n\n"
        f"Напиши в одну-две строки:",
        parse_mode="HTML",
        reply_markup=ReplyKeyboardRemove()
    )
    await state.set_state(ReportForm.done)


@dp.message(ReportForm.done)
async def report_done(message: Message, state: FSMContext):
    await state.update_data(done=message.text.strip())
    await message.answer(
        f"✅ Записал.\n\n"
        f"<b>Вопрос 2/3</b>\n"
        f"📈 <b>Какая цифра сдвинулась?</b>\n\n"
        f"Например: <i>«Было 200к → стало 230к», «Вес 94 → 93»</i>",
        parse_mode="HTML"
    )
    await state.set_state(ReportForm.metric)


@dp.message(ReportForm.metric)
async def report_metric(message: Message, state: FSMContext):
    await state.update_data(metric=message.text.strip())
    await message.answer(
        f"✅ Записал.\n\n"
        f"<b>Вопрос 3/3</b>\n"
        f"🚧 <b>Где застрял / нужна помощь?</b>\n\n"
        f"Если всё ок — напиши «Всё идёт по плану»",
        parse_mode="HTML"
    )
    await state.set_state(ReportForm.stuck)


@dp.message(ReportForm.stuck)
async def report_stuck(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = message.from_user.id
    username = message.from_user.username or message.from_user.first_name
    stuck = message.text.strip()

    db.save_report(
        user_id=user_id,
        done=data["done"],
        metric=data["metric"],
        stuck=stuck,
    )

    summary = (
        f"📋 <b>Отчёт принят!</b>\n\n"
        f"👤 @{username}\n"
        f"✅ Что сделал: {data['done']}\n"
        f"📈 Цифра: {data['metric']}\n"
        f"🚧 Застрял: {stuck}"
    )

    await message.answer(summary, parse_mode="HTML", reply_markup=main_keyboard())
    await state.clear()

    if ADMIN_ID:
        await bot.send_message(ADMIN_ID, f"📥 Новый отчёт\n\n{summary}", parse_mode="HTML")


# ─────────────────────────────────────────────
# ИСТОРИЯ ОТЧЁТОВ
# ─────────────────────────────────────────────

@dp.message(Command("history"))
@dp.message(F.text == "📊 История")
async def show_history(message: Message):
    reports = db.get_reports(message.from_user.id, limit=5)
    if not reports:
        await message.answer("Отчётов пока нет. Отправь первый через /report.")
        return

    text = "📊 <b>Последние отчёты:</b>\n\n"
    for r in reports:
        date = r["created_at"][:10]
        text += (
            f"🗓 <b>{date}</b>\n"
            f"✅ {r['done']}\n"
            f"📈 {r['metric']}\n"
            f"🚧 {r['stuck']}\n\n"
        )

    await message.answer(text, parse_mode="HTML", reply_markup=main_keyboard())


# ─────────────────────────────────────────────
# ADMIN: список всех участников
# ─────────────────────────────────────────────

@dp.message(Command("all_goals"))
async def admin_all_goals(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    goals = db.get_all_goals()
    if not goals:
        await message.answer("Пока нет ни одной зафиксированной цели.")
        return

    text = f"👥 <b>Все участники ({len(goals)}):</b>\n\n"
    for g in goals:
        text += (
            f"👤 @{g['username']}\n"
            f"📍 {g['baseline']} → 🏁 {g['target']}\n"
            f"🔍 {g['weak_point']}\n\n"
        )

    await message.answer(text, parse_mode="HTML")


# ─────────────────────────────────────────────
# ПЯТНИЧНАЯ РАССЫЛКА
# ─────────────────────────────────────────────

async def friday_reminder():
    """Отправляется каждую пятницу в 17:00 МСК всем у кого есть цель."""
    goals = db.get_all_goals()
    logger.info(f"Пятничная рассылка: {len(goals)} участников")

    for goal in goals:
        try:
            await bot.send_message(
                goal["user_id"],
                f"⏰ <b>Пятничный отчёт!</b>\n\n"
                f"Напомню твою цель:\n"
                f"📍 {goal['baseline']} → 🏁 {goal['target']}\n\n"
                f"Нажми /report или кнопку ниже, чтобы оставить отчёт за неделю 👇",
                parse_mode="HTML",
                reply_markup=report_keyboard()
            )
        except Exception as e:
            logger.warning(f"Не удалось отправить напоминание {goal['user_id']}: {e}")


# ─────────────────────────────────────────────
# КЛАВИАТУРЫ
# ─────────────────────────────────────────────

def main_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎯 Моя цель"), KeyboardButton(text="📋 Отчёт")],
            [KeyboardButton(text="📊 История")],
        ],
        resize_keyboard=True
    )


def report_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📋 Отчёт")]],
        resize_keyboard=True
    )


# ─────────────────────────────────────────────
# ЗАПУСК
# ─────────────────────────────────────────────

async def main():
    db.init()

    # Пятница = day_of_week=4 (пн=0), 17:00 МСК
    scheduler.add_job(friday_reminder, "cron", day_of_week="fri", hour=17, minute=0)
    scheduler.start()

    logger.info("Бот запущен ✅")
    await dp.start_polling(bot, skip_updates=True)


if __name__ == "__main__":
    asyncio.run(main())
