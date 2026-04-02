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


def _week_inline_keyboard(events: list[dict]) -> InlineKeyboardMarkup:
    """Inline keyboard with ✏️ button for each event."""
    builder = InlineKeyboardBuilder()
    for event in events:
        event_id = event.get("id", "")
        summary = event.get("summary", "(без названия)")
        start = event.get("start", {})
        if "dateTime" in start:
            dt = datetime.fromisoformat(start["dateTime"])
            end_dt = datetime.fromisoformat(event["end"]["dateTime"])
            label = f"✏️ {dt.strftime('%d.%m %H:%M')}–{end_dt.strftime('%H:%M')} {summary}"
        else:
            label = f"✏️ {summary}"
        # Truncate label to 64 chars (Telegram limit)
        label = label[:64]
        builder.button(text=label, callback_data=f"edit_event:{event_id}")
    builder.adjust(1)
    return builder.as_markup()


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
        kb = _week_inline_keyboard(events) if events else None
        await message.answer(text, parse_mode="Markdown", reply_markup=admin_keyboard())
        if kb:
            await message.answer("Нажми ✏️ чтобы изменить событие:", reply_markup=kb)
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", reply_markup=admin_keyboard())


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
        "Напиши новые данные события:\n"
        "`название  ГГГГ-ММ-ДД  ЧЧ:ММ-ЧЧ:ММ`\n\n"
        "Например:\n`Созвон с Катей  2026-04-06  16:00-17:00`",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove(),
    )


@router.message(EditState.waiting_for_new_details, F.text)
async def handle_edit_details(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    event_id = data.get("editing_event_id")
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
        updated = update_event(event_id, title, date_str, start_time, end_time)
        await message.answer(
            f"✅ Обновлено: *{updated}*\n📅 {date_str} {start_time}–{end_time}",
            parse_mode="Markdown",
            reply_markup=admin_keyboard(),
        )
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
