import json
import os
from openai import AsyncOpenAI
from dotenv import load_dotenv

load_dotenv()

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY", "placeholder"),
        )
    return _client


client = _get_client()

_SYSTEM_PROMPT = """You are a content editor for SREDA (movement education / contemporary dance).

RULES:
1. Preserve original phrasing as closely as possible
2. Return ONLY plain ASCII text in JSON fields — no Unicode fonts (𝗮𝗯𝗰, 𝘢𝘣𝘤, etc.)
3. Hashtags: lowercase, no spaces or hyphens (e.g. "movementeducation" not "movement-education")
4. Use \\n for line breaks within fields
5. Always output content in English
6. Detect content_type automatically from the input

Return this exact JSON schema:
{
  "content_type": "event" | "workshop" | "personal" | "lecture",
  "hook": "strong title or hook question",
  "sections": [
    {
      "name": "section name or null",
      "dates": "dates/times or null",
      "tags": "topics and level, different groups on different lines with \\n, or empty string",
      "body": "descriptive text without dates or bio",
      "schedule": "schedule with \\n between days, or null"
    }
  ],
  "about_label": "e.g. About MAMM or null",
  "about_name": "teacher/speaker names or null",
  "about_bio": "bio with \\n — first line is tagline, rest are credentials, or null",
  "early_bird": "Early Bird info with \\n or null",
  "cta": "short call to action",
  "hashtags_telegram": ["3 to 5 relevant hashtags"],
  "hashtags_instagram": ["exactly 5 most powerful hashtags for Instagram discovery"],
  "hashtags_youtube": ["5 to 8 hashtags"],
  "youtube": {
    "description": "2-4 sentence description of the content",
    "ideal_for": ["audience type 1", "audience type 2"],
    "timecodes": "00:00 Introduction\\n03:20 Chapter 1 or null",
    "speaker_name": "full name or null",
    "speaker_bio": "1-2 line bio or null",
    "speaker_website": "URL or null",
    "speaker_instagram": "@handle or null",
    "produced_by": "SREDA",
    "collaborators": [{"name": "PARTNER NAME", "instagram": "@handle"}],
    "filmed_by": "names or null",
    "edited_by": "name or null",
    "music": ["Artist - Track Name"]
  }
}

Reply ONLY with valid JSON, no explanations."""


_PARSE_EVENT_PROMPT = """Extract event details from the user's message and return JSON.
Today's date context: use it to resolve relative dates like "завтра", "в пятницу", "6 апреля".
Return ONLY this JSON:
{
  "title": "event title",
  "date": "YYYY-MM-DD",
  "start_time": "HH:MM",
  "end_time": "HH:MM"
}
If any field cannot be determined, set it to null.
Reply ONLY with valid JSON, no explanations."""


async def parse_event_nlp(text: str, today: str) -> dict:
    """Parse natural language event description into structured data."""
    completion = await client.chat.completions.create(
        model="openai/gpt-4o-mini",
        messages=[
            {"role": "system", "content": _PARSE_EVENT_PROMPT},
            {"role": "user", "content": f"Today is {today}. Event: {text}"},
        ],
    )
    response_text = completion.choices[0].message.content.strip()
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
    return json.loads(response_text)


async def reformat_text(raw_text: str) -> dict:
    completion = await client.chat.completions.create(
        model="openai/gpt-4o-mini",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
    )
    response_text = completion.choices[0].message.content.strip()
    # Strip markdown code blocks if present
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
    return json.loads(response_text)
