import io
import json
import os
from datetime import date

from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from services.voice_service import transcribe_audio
from services.calendar_service import get_today_events, get_week_events, add_event
from services.ai_formatter import _get_client

router = Router()

ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

TODAY_KEYWORDS = ["сегодня", "что у меня", "мое расписание", "моё расписание", "мой день"]
WEEK_KEYWORDS = ["неделя", "неделю", "на неделе", "эту неделю", "эта неделя", "всю неделю"]
ADD_KEYWORDS = ["добавь", "запиши", "поставь", "добавить", "создай", "создать", "занеси", "внеси"]


def _detect_intent(text: str) -> str:
    t = text.lower()
    if any(k in t for k in ADD_KEYWORDS):
        return "add"
    if any(k in t for k in TODAY_KEYWORDS):
        return "today"
    if any(k in t for k in WEEK_KEYWORDS):
        return "week"
    return "unknown"


async def _parse_event(text: str) -> dict | None:
    today = date.today().isoformat()
    client = _get_client()
    response = await client.chat.completions.create(
        model="openai/gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    f"Today is {today}. Extract event details from Russian text. "
                    "Return JSON: {\"title\": \"...\", \"date\": \"YYYY-MM-DD\", "
                    "\"start\": \"HH:MM\", \"end\": \"HH:MM\"}. "
                    "If no end time mentioned, add 1 hour. "
                    "If date is relative ('завтра', 'в пятницу'), compute it from today. "
                    "Return {\"error\": true} if cannot parse."
                ),
            },
            {"role": "user", "content": text},
        ],
        response_format={"type": "json_object"},
    )
    try:
        data = json.loads(response.choices[0].message.content)
        if data.get("error"):
            return None
        if data.get("title") and data.get("date") and data.get("start"):
            return data
    except Exception:
        pass
    return None


@router.message(F.voice)
async def handle_voice(message: Message, state: FSMContext, bot: Bot) -> None:
    if message.from_user.id != ADMIN_ID:
        return

    processing_msg = await message.answer("🎙 Слушаю...")

    try:
        file_io = io.BytesIO()
        await bot.download(message.voice.file_id, destination=file_io)
        file_io.seek(0)
        audio_bytes = file_io.read()
    except Exception as e:
        await processing_msg.edit_text(f"❌ Не смогла скачать аудио: {e}")
        return

    try:
        text = await transcribe_audio(audio_bytes)
    except Exception as e:
        await processing_msg.edit_text(f"❌ Не смогла расшифровать: {e}")
        return

    await processing_msg.edit_text(f"🎙 Услышала: _{text}_")

    from handlers.schedule_handler import admin_keyboard

    intent = _detect_intent(text)

    if intent == "today":
        result = get_today_events()
        await message.answer(result, parse_mode="Markdown", reply_markup=admin_keyboard())

    elif intent == "week":
        result = get_week_events()
        await message.answer(result, parse_mode="Markdown", reply_markup=admin_keyboard())

    elif intent == "add":
        event = await _parse_event(text)
        if event:
            try:
                created = add_event(
                    event["title"],
                    event["date"],
                    event["start"],
                    event.get("end", ""),
                )
                await message.answer(
                    f"✅ Добавила: *{created}*\n📅 {event['date']} {event['start']}–{event.get('end', '')}",
                    parse_mode="Markdown",
                    reply_markup=admin_keyboard(),
                )
            except Exception as e:
                await message.answer(f"❌ Ошибка: {e}", reply_markup=admin_keyboard())
        else:
            await message.answer(
                "Не смогла разобрать событие 🤔\n"
                "Попробуй так: «Добавь созвон с Катей завтра в 15:00»",
                reply_markup=admin_keyboard(),
            )

    else:
        await message.answer(
            "Не поняла команду. Скажи, например:\n"
            "• «Что у меня сегодня?»\n"
            "• «Покажи расписание на неделю»\n"
            "• «Добавь созвон с Катей завтра в 15:00»",
            reply_markup=admin_keyboard(),
        )
