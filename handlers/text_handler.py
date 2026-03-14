from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from services.ai_formatter import reformat_text
from services.platform_formatter import format_for_telegram, format_for_instagram

router = Router()


class TextState(StatesGroup):
    waiting_for_platform = State()


def _platform_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📱 Telegram", callback_data="platform:telegram")
    builder.button(text="📷 Instagram", callback_data="platform:instagram")
    builder.button(text="📲 Оба", callback_data="platform:both")
    builder.adjust(2, 1)
    return builder.as_markup()


@router.message(F.text)
async def handle_text(message: Message, state: FSMContext) -> None:
    await state.update_data(raw_text=message.text)
    await state.set_state(TextState.waiting_for_platform)
    await message.answer(
        "Для какой платформы форматируем?",
        reply_markup=_platform_keyboard(),
    )


@router.callback_query(TextState.waiting_for_platform, F.data.startswith("platform:"))
async def handle_platform(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()

    data = await state.get_data()
    raw_text = data.get("raw_text", "")
    await state.clear()

    platform = callback.data.split(":")[1]

    await callback.message.edit_text("⏳ Форматирую текст...")

    try:
        parts = await reformat_text(raw_text)
        hook = parts["hook"]
        tags = parts.get("tags", "")
        body = parts["body"]
        cta = parts["cta"]
        hashtags = parts.get("hashtags", [])
    except Exception:
        await callback.message.edit_text("❌ Ошибка при обращении к ИИ. Попробуй ещё раз.")
        return

    results = []

    if platform in ("telegram", "both"):
        tg_text = format_for_telegram(hook, body, tags, cta)
        results.append(f"📱 *Telegram:*\n\n{tg_text}")

    if platform in ("instagram", "both"):
        ig_text = format_for_instagram(hook, body, tags, cta, hashtags=hashtags)
        results.append(f"📷 Instagram:\n\n{ig_text}")

    output = "\n\n━━━━━━━━━━━━━━━━\n\n".join(results)
    await callback.message.edit_text(output, parse_mode="Markdown")
