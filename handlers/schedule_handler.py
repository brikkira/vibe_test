import os
import re

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove

from services.calendar_service import get_today_events, get_week_events, add_event

router = Router()

ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))


class AddState(StatesGroup):
    waiting_for_details = State()


def admin_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📆 Сегодня"), KeyboardButton(text="🗓 Неделя")],
            [KeyboardButton(text="➕ Добавить событие"), KeyboardButton(text="✍️ Контент")],
        ],
        resize_keyboard=True,
    )


def _is_admin(message: Message) -> bool:
    return message.from_user.id == ADMIN_ID


@router.message(Command("today"))
@router.message(F.text == "📆 Сегодня")
async def cmd_today(message: Message, state: FSMContext) -> None:
    if not _is_admin(message):
        return
    await state.clear()
    try:
        text = get_today_events()
        await message.answer(text, parse_mode="Markdown", reply_markup=admin_keyboard())
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", reply_markup=admin_keyboard())


@router.message(Command("week"))
@router.message(F.text == "🗓 Неделя")
async def cmd_week(message: Message, state: FSMContext) -> None:
    if not _is_admin(message):
        return
    await state.clear()
    try:
        text = get_week_events()
        await message.answer(text, parse_mode="Markdown", reply_markup=admin_keyboard())
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", reply_markup=admin_keyboard())


@router.message(Command("add"))
@router.message(F.text == "➕ Добавить событие")
async def cmd_add(message: Message, state: FSMContext) -> None:
    if not _is_admin(message):
        return
    await state.clear()
    await state.set_state(AddState.waiting_for_details)
    await message.answer(
        "Напиши событие в формате:\n"
        "`название  ГГГГ-ММ-ДД  ЧЧ:ММ-ЧЧ:ММ`\n\n"
        "Например:\n`Созвон с Катей  2026-04-05  15:00-16:00`",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(AddState.waiting_for_details, F.text)
async def handle_add_details(message: Message, state: FSMContext) -> None:
    await state.clear()
    text = message.text.strip()

    parts = re.split(r"\s{2,}|\t", text)
    if len(parts) == 3:
        title, date_str, time_range = parts
    else:
        m = re.match(
            r"(.+?)\s+(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})[-–](\d{1,2}:\d{2})", text
        )
        if not m:
            await message.answer(
                "❌ Не смогла разобрать. Формат:\n`название  ГГГГ-ММ-ДД  ЧЧ:ММ-ЧЧ:ММ`",
                parse_mode="Markdown",
                reply_markup=admin_keyboard(),
            )
            return
        title, date_str, start_time, end_time = m.groups()
        time_range = f"{start_time}-{end_time}"

    time_parts = re.split(r"[-–]", time_range)
    if len(time_parts) != 2:
        await message.answer(
            "❌ Формат времени: `15:00-16:00`",
            parse_mode="Markdown",
            reply_markup=admin_keyboard(),
        )
        return

    start_time, end_time = time_parts
    try:
        created = add_event(title.strip(), date_str.strip(), start_time.strip(), end_time.strip())
        await message.answer(
            f"✅ Добавлено: *{created}*\n📅 {date_str} {start_time}–{end_time}",
            parse_mode="Markdown",
            reply_markup=admin_keyboard(),
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", reply_markup=admin_keyboard())
