import os
import re

from aiogram import Router, F
from aiogram.filters import CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.ai_formatter import reformat_text
from services.platform_formatter import (
    format_for_telegram,
    format_for_instagram,
    format_for_youtube,
)

router = Router()

ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_ID", "0"))

_URL_RE = re.compile(r'https?://\S+')
_EARLY_BIRD_RE = re.compile(r'early\s*bird', re.IGNORECASE)


class TextState(StatesGroup):
    waiting_for_platform = State()
    waiting_for_text = State()
    waiting_for_early_bird = State()
    waiting_for_link_confirm = State()
    waiting_for_link = State()


# ── Keyboards ──────────────────────────────────────────────────────────────────

def _platform_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📱 Telegram", callback_data="platform:telegram")
    builder.button(text="📷 Instagram", callback_data="platform:instagram")
    builder.button(text="▶️ YouTube", callback_data="platform:youtube")
    builder.button(text="📲 All three", callback_data="platform:all")
    builder.adjust(2, 2)
    return builder.as_markup()


def _no_early_bird_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="No Early Bird", callback_data="early_bird:none")
    return builder.as_markup()


def _link_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Yes, add link", callback_data="link_confirm:yes")
    builder.button(text="❌ No link", callback_data="link_confirm:no")
    builder.adjust(2)
    return builder.as_markup()


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_link(text: str) -> tuple[str, str | None]:
    match = _URL_RE.search(text)
    if match:
        link = match.group()
        clean = _URL_RE.sub('', text).strip()
        return clean, link
    return text, None


def _has_early_bird(text: str) -> bool:
    return bool(_EARLY_BIRD_RE.search(text))


async def _ask_for_link_or_format(state: FSMContext, message: Message) -> None:
    data = await state.get_data()
    platform = data.get("platform", "telegram")
    # YouTube doesn't need a registration link
    if data.get("link") or platform == "youtube":
        await _do_format(state, message)
    else:
        await state.set_state(TextState.waiting_for_link_confirm)
        await message.answer(
            "Is there a registration link?",
            reply_markup=_link_confirm_keyboard(),
        )


async def _do_format(state: FSMContext, message: Message) -> None:
    data = await state.get_data()
    raw_text  = data.get("raw_text", "")
    link      = data.get("link")
    early_bird = data.get("early_bird")
    platform  = data.get("platform", "telegram")
    await state.clear()

    if early_bird and early_bird != "none":
        raw_text = f"{raw_text}\n\nEarly Bird: until {early_bird}"

    loading = await message.answer("⏳ Formatting your text...")

    try:
        parts = await reformat_text(raw_text)

        hook        = parts.get("hook", "")
        sections    = parts.get("sections") or []
        about_label = parts.get("about_label") or None
        about_name  = parts.get("about_name") or None
        about_bio   = parts.get("about_bio") or None
        early_bird  = parts.get("early_bird") or None
        cta         = parts.get("cta", "")

        hashtags_tg  = parts.get("hashtags_telegram") or []
        hashtags_ig  = parts.get("hashtags_instagram") or []
        hashtags_yt  = parts.get("hashtags_youtube") or []
        youtube_data = parts.get("youtube") or {}

        # Fallback for old schema
        if not sections:
            sections = [{
                "name": None,
                "dates": parts.get("schedule"),
                "tags": parts.get("tags", ""),
                "body": parts.get("body", ""),
                "schedule": None,
            }]

    except Exception:
        await loading.edit_text("❌ AI error. Please try again.")
        return

    common_kwargs = dict(
        sections=sections,
        cta=cta,
        about_label=about_label,
        about_name=about_name,
        about_bio=about_bio,
        early_bird=early_bird,
        link=link,
    )

    results = []

    if platform in ("telegram", "all"):
        tg_text = format_for_telegram(hook, hashtags=hashtags_tg, **common_kwargs)
        results.append(("📱 Telegram", tg_text))

    if platform in ("instagram", "all"):
        ig_text = format_for_instagram(hook, hashtags=hashtags_ig, **common_kwargs)
        results.append(("📷 Instagram", ig_text))

    if platform in ("youtube", "all"):
        yt_text = format_for_youtube(hook, youtube_data=youtube_data, hashtags=hashtags_yt)
        results.append(("▶️ YouTube", yt_text))

    output = "\n\n━━━━━━━━━━━━━━━━\n\n".join(
        f"{label}:\n\n{text}" for label, text in results
    )
    await loading.edit_text(output)


# ── Handlers ───────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    if message.from_user.id == ADMIN_ID:
        from handlers.schedule_handler import admin_keyboard
        await message.answer(
            "Привет! Выбери что хочешь сделать:",
            reply_markup=admin_keyboard(),
        )
    else:
        await state.set_state(TextState.waiting_for_platform)
        await message.answer("Choose platform:", reply_markup=_platform_keyboard())


@router.message(F.text == "✍️ Контент")
async def handle_content_button(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(TextState.waiting_for_platform)
    await message.answer("Выбери платформу:", reply_markup=_platform_keyboard())


@router.message(StateFilter(None), F.text)
async def handle_no_state(message: Message, state: FSMContext) -> None:
    if message.from_user.id == ADMIN_ID:
        from handlers.schedule_handler import admin_keyboard
        await message.answer(
            "Выбери что хочешь сделать:",
            reply_markup=admin_keyboard(),
        )
        return
    await state.set_state(TextState.waiting_for_platform)
    await message.answer("Choose platform:", reply_markup=_platform_keyboard())


@router.message(TextState.waiting_for_platform, F.text)
async def handle_platform_text(message: Message, state: FSMContext) -> None:
    await message.answer(
        "Please choose a platform using the buttons:",
        reply_markup=_platform_keyboard(),
    )


@router.callback_query(TextState.waiting_for_platform, F.data.startswith("platform:"))
async def handle_platform(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    platform = callback.data.split(":")[1]
    await state.update_data(platform=platform)
    await state.set_state(TextState.waiting_for_text)
    await callback.message.edit_text("Send me your text:")


@router.message(TextState.waiting_for_text, F.text)
async def handle_text(message: Message, state: FSMContext) -> None:
    clean_text, link = _extract_link(message.text)
    await state.update_data(raw_text=clean_text, link=link)

    data = await state.get_data()
    platform = data.get("platform", "telegram")

    # YouTube doesn't need Early Bird
    if platform == "youtube":
        await _do_format(state, message)
    elif _has_early_bird(clean_text):
        await _ask_for_link_or_format(state, message)
    else:
        await state.set_state(TextState.waiting_for_early_bird)
        await message.answer(
            "Early Bird deadline? (or press button if none)",
            reply_markup=_no_early_bird_keyboard(),
        )


@router.message(TextState.waiting_for_early_bird, F.text)
async def handle_early_bird_text(message: Message, state: FSMContext) -> None:
    await state.update_data(early_bird=message.text.strip())
    await _ask_for_link_or_format(state, message)


@router.callback_query(TextState.waiting_for_early_bird, F.data == "early_bird:none")
async def handle_early_bird_none(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(early_bird="none")
    await callback.message.edit_text("Got it, no Early Bird.")
    await _ask_for_link_or_format(state, callback.message)


@router.callback_query(TextState.waiting_for_link_confirm, F.data.startswith("link_confirm:"))
async def handle_link_confirm(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    answer = callback.data.split(":")[1]
    if answer == "yes":
        await state.set_state(TextState.waiting_for_link)
        await callback.message.edit_text("Send me the registration link:")
    else:
        await callback.message.edit_text("OK, no link.")
        await _do_format(state, callback.message)


@router.message(TextState.waiting_for_link, F.text)
async def handle_link(message: Message, state: FSMContext) -> None:
    await state.update_data(link=message.text.strip())
    await _do_format(state, message)
