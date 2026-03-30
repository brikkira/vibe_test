import os
import re

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from services.calendar_service import get_today_events, get_week_events, add_event

router = Router()

ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

# Matches: "15:00-16:00 Созвон с Катей 2026-04-05"
# or:      "Созвон с Катей завтра 15:00-16:00"
ADD_RE = re.compile(
    r"(?P<time>\d{1,2}:\d{2}[-–]\d{1,2}:\d{2})\s+(?P<title>.+?)\s+(?P<date>\d{4}-\d{2}-\d{2})"
    r"|(?P<title2>.+?)\s+(?P<date2>\d{4}-\d{2}-\d{2})\s+(?P<time2>\d{1,2}:\d{2}[-–]\d{1,2}:\d{2})"
)


class AddState(StatesGroup):
    waiting_for_details = State()


def _is_admin(message: Message) -> bool:
    return message.from_user.id == ADMIN_ID


@router.message(Command("today"))
async def cmd_today(message: Message) -> None:
    if not _is_admin(message):
        return
    try:
        text = get_today_events()
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("week"))
async def cmd_week(message: Message) -> None:
    if not _is_admin(message):
        return
    try:
        text = get_week_events()
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")


@router.message(Command("add"))
async def cmd_add(message: Message, state: FSMContext) -> None:
    if not _is_admin(message):
        return
    await state.set_state(AddState.waiting_for_details)
    await message.answer(
        "Напиши событие в формате:\n"
        "`название  ГГГГ-ММ-ДД  ЧЧ:ММ-ЧЧ:ММ`\n\n"
        "Например:\n`Созвон с Катей  2026-04-05  15:00-16:00`",
        parse_mode="Markdown",
    )


@router.message(AddState.waiting_for_details, F.text)
async def handle_add_details(message: Message, state: FSMContext) -> None:
    await state.clear()
    text = message.text.strip()

    # Parse: "Title  YYYY-MM-DD  HH:MM-HH:MM"
    parts = re.split(r"\s{2,}|\t", text)
    if len(parts) == 3:
        title, date_str, time_range = parts
    else:
        # Try single-space split as fallback
        m = re.match(
            r"(.+?)\s+(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})[-–](\d{1,2}:\d{2})", text
        )
        if not m:
            await message.answer(
                "❌ Не смогла разобрать. Формат:\n`название  ГГГГ-ММ-ДД  ЧЧ:ММ-ЧЧ:ММ`",
                parse_mode="Markdown",
            )
            return
        title, date_str, start_time, end_time = m.groups()
        time_range = f"{start_time}-{end_time}"

    time_parts = re.split(r"[-–]", time_range)
    if len(time_parts) != 2:
        await message.answer("❌ Не смогла разобрать время. Формат: `15:00-16:00`", parse_mode="Markdown")
        return

    start_time, end_time = time_parts
    try:
        created = add_event(title.strip(), date_str.strip(), start_time.strip(), end_time.strip())
        await message.answer(f"✅ Добавлено: *{created}*\n📅 {date_str} {start_time}–{end_time}", parse_mode="Markdown")
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}")
