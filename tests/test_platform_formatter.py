import pytest
from services.platform_formatter import (
    format_for_telegram,
    format_for_instagram,
    format_for_youtube,
    to_bold,
    to_italic,
    to_regular,
)

SECTIONS = [{"name": "Workshop", "dates": "13 April", "tags": "Beginners", "body": "Come and dance.", "schedule": None}]

# ── Font conversion ────────────────────────────────────────────────────────────

def test_bold_latin():
    assert to_bold("Hi") == "𝗛𝗶"

def test_italic_latin():
    assert to_italic("ab") == "𝘢𝘣"

def test_regular_latin():
    assert to_regular("Hi") == "𝖧𝗂"

def test_fonts_preserve_non_latin():
    assert to_bold("13 April!") == "𝟭𝟯 𝗔𝗽𝗿𝗶𝗹!"
    assert to_italic("Beginners / Intermediate") == "𝘉𝘦𝘨𝘪𝘯𝘯𝘦𝘳𝘴 / 𝘐𝘯𝘵𝘦𝘳𝘮𝘦𝘥𝘪𝘢𝘵𝘦"


# ── Telegram ──────────────────────────────────────────────────────────────────

def test_telegram_hook_is_bold():
    result = format_for_telegram("My Title", sections=SECTIONS)
    assert to_bold("My Title") in result

def test_telegram_has_date_and_location():
    result = format_for_telegram("Title", sections=SECTIONS)
    assert to_bold("13 April") in result

def test_telegram_hashtags_3_to_5():
    result = format_for_telegram("Title", sections=SECTIONS, hashtags=["dance", "workshop", "sreda"])
    assert "#dance" in result
    assert "#workshop" in result

def test_telegram_hashtags_not_more_than_5():
    tags = ["a", "b", "c", "d", "e", "f", "g"]
    result = format_for_telegram("Title", sections=SECTIONS, hashtags=tags)
    count = result.count("#")
    assert count <= 5

def test_telegram_link_is_clickable():
    result = format_for_telegram("Title", sections=SECTIONS, link="https://example.com")
    assert "[" in result and "](https://example.com)" in result

def test_telegram_no_excessive_emojis():
    result = format_for_telegram("Title", sections=SECTIONS)
    emoji_count = sum(1 for c in result if ord(c) > 127000)
    assert emoji_count < 10


# ── Instagram ─────────────────────────────────────────────────────────────────

def test_instagram_hook_is_bold():
    result = format_for_instagram("My Title", sections=SECTIONS)
    assert to_bold("My Title") in result

def test_instagram_exactly_5_hashtags():
    tags = ["a", "b", "c", "d", "e", "f", "g"]
    result = format_for_instagram("Title", sections=SECTIONS, hashtags=tags)
    count = sum(1 for line in result.split("\n") if line.startswith("#"))
    assert count == 5

def test_instagram_hashtags_at_end():
    result = format_for_instagram("Title", sections=SECTIONS, hashtags=["dance", "sreda"])
    lines = result.strip().split("\n")
    last_non_empty = [l for l in lines if l.strip()][-1]
    assert last_non_empty.startswith("#")

def test_instagram_body_is_regular():
    result = format_for_instagram("Title", sections=SECTIONS)
    assert to_regular("Come and dance.") in result

def test_instagram_has_separator():
    result = format_for_instagram("Title", sections=SECTIONS)
    assert "✦" in result


# ── YouTube ───────────────────────────────────────────────────────────────────

YT_DATA = {
    "description": "A live lecture exploring performance practices.",
    "ideal_for": ["Contact Improvisation", "Somatic practices"],
    "timecodes": "00:00 Introduction\n03:20 What is performance?",
    "speaker_name": "Alex Smith",
    "speaker_bio": "Art practitioner and choreographer.",
    "speaker_website": "https://alexsmith.com",
    "speaker_instagram": "@alexsmith",
    "produced_by": "SREDA",
    "collaborators": [{"name": "SEAMLESS", "instagram": "@seamless_mrp"}],
    "filmed_by": "Igor MindGarden",
    "edited_by": "Waxwood",
    "music": ["Theo Parrish - Henny Weed Buckdance"],
}

def test_youtube_hook_is_bold():
    result = format_for_youtube("My Lecture", youtube_data=YT_DATA, hashtags=["dance"])
    assert to_bold("My Lecture") in result

def test_youtube_has_description():
    result = format_for_youtube("Title", youtube_data=YT_DATA, hashtags=[])
    assert "A live lecture exploring performance practices." in result

def test_youtube_has_timecodes():
    result = format_for_youtube("Title", youtube_data=YT_DATA, hashtags=[])
    assert "00:00" in result
    assert "03:20" in result

def test_youtube_has_speaker():
    result = format_for_youtube("Title", youtube_data=YT_DATA, hashtags=[])
    assert "Alex Smith" in result

def test_youtube_has_produced_by():
    result = format_for_youtube("Title", youtube_data=YT_DATA, hashtags=[])
    assert "SREDA" in result

def test_youtube_has_credits():
    result = format_for_youtube("Title", youtube_data=YT_DATA, hashtags=[])
    assert "Igor MindGarden" in result
    assert "Waxwood" in result

def test_youtube_has_music():
    result = format_for_youtube("Title", youtube_data=YT_DATA, hashtags=[])
    assert "Theo Parrish" in result

def test_youtube_has_hashtags():
    result = format_for_youtube("Title", youtube_data=YT_DATA, hashtags=["dance", "sreda"])
    assert "#dance" in result

def test_youtube_ideal_for_section():
    result = format_for_youtube("Title", youtube_data=YT_DATA, hashtags=[])
    assert "Contact Improvisation" in result

def test_youtube_collaborators():
    result = format_for_youtube("Title", youtube_data=YT_DATA, hashtags=[])
    assert "SEAMLESS" in result
