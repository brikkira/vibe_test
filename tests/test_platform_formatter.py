import pytest
from services.platform_formatter import (
    format_for_telegram,
    format_for_instagram,
    to_bold,
    to_italic,
    to_regular,
)


# --- Font conversion tests ---

def test_bold_latin():
    assert to_bold("Hi") == "𝗛𝗶"

def test_italic_latin():
    assert to_italic("ab") == "𝘢𝘣"

def test_regular_latin():
    assert to_regular("Hi") == "𝖧𝗂"

def test_fonts_preserve_non_latin():
    assert to_bold("13 April!") == "𝟭𝟯 𝗔𝗽𝗿𝗶𝗹!"
    assert to_italic("Beginners / Intermediate") == "𝘉𝘦𝘨𝘪𝘯𝘯𝘦𝘳𝘴 / 𝘐𝘯𝘵𝘦𝘳𝘮𝘦𝘥𝘪𝘢𝘵𝘦"


# --- Telegram format tests ---

def test_telegram_hook_is_bold():
    result = format_for_telegram("Title", "Body text", "Tags here", "Register now")
    assert to_bold("Title") in result

def test_telegram_tags_are_italic():
    result = format_for_telegram("Title", "Body text", "Tags here", "Register now")
    assert to_italic("Tags here") in result

def test_telegram_body_is_regular():
    result = format_for_telegram("Title", "Body text", "Tags here", "Register now")
    assert to_regular("Body text") in result

def test_telegram_cta_is_bold():
    result = format_for_telegram("Title", "Body text", "Tags here", "Register now")
    assert to_bold("Register now") in result

def test_telegram_no_hashtags():
    result = format_for_telegram("Title", "Body text", "Tags", "CTA", hashtags=["dance", "movement"])
    assert "#dance" not in result


# --- Instagram format tests ---

def test_instagram_hook_is_bold():
    result = format_for_instagram("Title", "Body text", "Tags here", "Register now")
    assert to_bold("Title") in result

def test_instagram_tags_are_italic():
    result = format_for_instagram("Title", "Body text", "Tags here", "Register now")
    assert to_italic("Tags here") in result

def test_instagram_body_is_regular():
    result = format_for_instagram("Title", "Body text", "Tags here", "Register now")
    assert to_regular("Body text") in result

def test_instagram_has_hashtags():
    result = format_for_instagram("T", "B", "Tags", "CTA", hashtags=["dance", "movement"])
    assert "#dance" in result
    assert "#movement" in result

def test_instagram_hashtags_at_end():
    result = format_for_instagram("T", "B", "Tags", "CTA", hashtags=["dance"])
    assert result.index("#dance") > result.index(to_bold("CTA"))
