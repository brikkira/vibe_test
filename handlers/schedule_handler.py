import os
import re
from datetime import datetime

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.calendar_service import (
    get_today_events, get_week_events, get_week_events_raw,
    add_event, update_event,
)

router = Router()

ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))


class AddState(StatesGroup):
    waiting_for_details = State()


class EditState(StatesGroup):
    waiting_for_new_details = State()


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


DAY_NAMES_RU = {0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"}
DAY_NAMES_FULL = {0: "Понедельник", 1: "Вторник", 2: "Среда", 3: "Четверг",
                  4: "Пятница", 5: "Суббота", 6: "Воскресенье"}


def _week_by_day(events: list[dict]) -> list[tuple[str, InlineKeyboardMarkup]]:
    """Returns list of (day_header_text, keyboard) tuples — one per day."""
    from collections import OrderedDict

    by_day: OrderedDict[str, list] = OrderedDict()
    for event in events:
        start = event.get("start", {})
        date_key = (start.get("date") or start.get("dateTime", "")[:10])
        by_day.setdefault(date_key, []).append(event)

    result = []
    for date_key, day_events in by_day.items():
        dt = datetime.fromisoformat(date_key)
        day_header = f"*{DAY_NAMES_FULL[dt.weekday()]}, {dt.strftime('%d.%m')}*"

        builder = InlineKeyboardBuilder()
        for event in day_events:
            event_id = event.get("id", "")
            summary = event.get("summary", "(без названия)")
            start = event.get("start", {})
            if "dateTime" in start:
                edt = datetime.fromisoformat(start["dateTime"])
                end_dt = datetime.fromisoformat(event["end"]["dateTime"])
                label = f"✏️ {edt.strftime('%H:%M')}–{end_dt.strftime('%H:%M')} {summary}"
            else:
                label = f"✏️ {summary}"
            builder.button(text=label[:64], callback_data=f"edit_event:{event_id}")
        builder.adjust(1)
        result.append((day_header, builder.as_markup()))
    return result


def _parse_event_text(text: str):
    """Parse 'название  ГГГГ-ММ-ДД  ЧЧ:ММ-ЧЧ:ММ', returns (title, date, start, end) or None."""
    parts = re.split(r"\s{2,}|\t", text.strip())
    if len(parts) == 3:
        title, date_str, time_range = parts
    else:
        m = re.match(
            r"(.+?)\s+(\d{4}-\d{2}-\d{2})\s+(\d{1,2}:\d{2})[-–](\d{1,2}:\d{2})", text
        )
        if not m:
            return None
        title, date_str, start_time, end_time = m.groups()
        return title.strip(), date_str.strip(), start_time.strip(), end_time.strip()

    time_parts = re.split(r"[-–]", time_range)
    if len(time_parts) != 2:
        return None
    return title.strip(), date_str.strip(), time_parts[0].strip(), time_parts[1].strip()


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
        events = get_week_events_raw()
        await message.answer(text, parse_mode="Markdown", reply_markup=admin_keyboard())
        if events:
            await message.answer("✏️ Нажми на событие чтобы изменить:")
            for day_header, kb in _week_by_day(events):
                await message.answer(day_header, parse_mode="Markdown", reply_markup=kb)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", reply_markup=admin_keyboard())


@router.callback_query(F.data == "noop")
async def handle_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("edit_event:"))
async def handle_edit_event(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.from_user.id != ADMIN_ID:
        await callback.answer()
        return
    await callback.answer()
    event_id = callback.data.split(":", 1)[1]
    await state.update_data(editing_event_id=event_id)
    await state.set_state(EditState.waiting_for_new_details)
    await callback.message.answer(
        "Напиши что изменить — как тебе удобно:\n\n"
        "Например:\n"
        "• _Созвон с Катей, 6 апреля, 16:00–17:00_\n"
        "• _CI Class, завтра, 11 утра до 2 дня_\n"
        "• _Jump Academy, пятница, 13:00–16:00_",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(EditState.waiting_for_new_details, F.text)
async def handle_edit_details(message: Message, state: FSMContext) -> None:
    from datetime import date
    from services.ai_formatter import parse_event_nlp

    data = await state.get_data()
    event_id = data.get("editing_event_id")
    await state.clear()

    processing = await message.answer("⏳ Разбираю...")
    try:
        today = date.today().isoformat()
        parsed = await parse_event_nlp(message.text, today)
    except Exception as e:
        await processing.edit_text(f"❌ Ошибка AI: {e}", reply_markup=admin_keyboard())
        return

    title = parsed.get("title")
    date_str = parsed.get("date")
    start_time = parsed.get("start_time")
    end_time = parsed.get("end_time")

    if not all([title, date_str, start_time, end_time]):
        missing = [f for f, v in [("название", title), ("дата", date_str),
                                   ("начало", start_time), ("конец", end_time)] if not v]
        await processing.edit_text(
            f"❌ Не смогла разобрать: {', '.join(missing)}. Попробуй написать чётче.",
            reply_markup=admin_keyboard(),
        )
        return

    try:
        updated = update_event(event_id, title, date_str, start_time, end_time)
        await processing.edit_text(
            f"✅ Обновлено: *{updated}*\n📅 {date_str} {start_time}–{end_time}",
            parse_mode="Markdown",
            reply_markup=admin_keyboard(),
        )
    except Exception as e:
        await processing.edit_text(f"❌ Ошибка: {e}", reply_markup=admin_keyboard())


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

    parsed = _parse_event_text(message.text)
    if not parsed:
        await message.answer(
            "❌ Не смогла разобрать. Формат:\n`название  ГГГГ-ММ-ДД  ЧЧ:ММ-ЧЧ:ММ`",
            parse_mode="Markdown",
            reply_markup=admin_keyboard(),
        )
        return

    title, date_str, start_time, end_time = parsed
    try:
        created = add_event(title, date_str, start_time, end_time)
        await message.answer(
            f"✅ Добавлено: *{created}*\n📅 {date_str} {start_time}–{end_time}",
            parse_mode="Markdown",
            reply_markup=admin_keyboard(),
        )
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", reply_markup=admin_keyboard())
