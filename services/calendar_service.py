import os
from datetime import datetime, timedelta, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

TIMEZONE = "Asia/Makassar"
CALENDAR_ID = "primary"


def _get_service():
    creds = Credentials(
        token=None,
        refresh_token=os.getenv("GOOGLE_REFRESH_TOKEN"),
        client_id=os.getenv("GOOGLE_CLIENT_ID"),
        client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
        token_uri="https://oauth2.googleapis.com/token",
    )
    return build("calendar", "v3", credentials=creds)


def _bali_now() -> datetime:
    bali_offset = timezone(timedelta(hours=8))
    return datetime.now(bali_offset)


def _format_event(event: dict) -> str:
    summary = event.get("summary", "(без названия)")
    start = event.get("start", {})
    if "dateTime" in start:
        dt = datetime.fromisoformat(start["dateTime"])
        time_str = dt.strftime("%H:%M")
        end_dt = datetime.fromisoformat(event["end"]["dateTime"])
        return f"🕐 {time_str}–{end_dt.strftime('%H:%M')} {summary}"
    else:
        return f"📅 весь день — {summary}"


def get_today_events() -> str:
    now = _bali_now()
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    day_end = now.replace(hour=23, minute=59, second=59, microsecond=0)

    service = _get_service()
    result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=day_start.isoformat(),
        timeMax=day_end.isoformat(),
        singleEvents=True,
        orderBy="startTime",
        timeZone=TIMEZONE,
    ).execute()

    events = result.get("items", [])
    if not events:
        return "📭 Сегодня событий нет"

    DAYS_RU = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]
    MONTHS_RU = ["", "января", "февраля", "марта", "апреля", "мая", "июня",
                 "июля", "августа", "сентября", "октября", "ноября", "декабря"]
    date_str = f"{DAYS_RU[now.weekday()]}, {now.day} {MONTHS_RU[now.month]}"
    lines = [f"📆 *{date_str}*\n"]
    for e in events:
        lines.append(_format_event(e))
    return "\n".join(lines)


def get_week_events() -> str:
    now = _bali_now()
    week_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_end = week_start + timedelta(days=7)

    service = _get_service()
    result = service.events().list(
        calendarId=CALENDAR_ID,
        timeMin=week_start.isoformat(),
        timeMax=week_end.isoformat(),
        singleEvents=True,
        orderBy="startTime",
        timeZone=TIMEZONE,
    ).execute()

    events = result.get("items", [])
    if not events:
        return "📭 На этой неделе событий нет"

    DAY_NAMES = {
        0: "Пн", 1: "Вт", 2: "Ср", 3: "Чт", 4: "Пт", 5: "Сб", 6: "Вс"
    }

    by_day: dict[str, list] = {}
    for e in events:
        start = e.get("start", {})
        date_key = (start.get("date") or start.get("dateTime", "")[:10])
        by_day.setdefault(date_key, []).append(e)

    lines = ["📅 *Неделя*\n"]
    for date_key in sorted(by_day.keys()):
        dt = datetime.fromisoformat(date_key)
        day_label = f"{DAY_NAMES[dt.weekday()]} {dt.strftime('%d.%m')}"
        lines.append(f"\n*{day_label}*")
        for e in by_day[date_key]:
            lines.append(_format_event(e))
    return "\n".join(lines)


def add_event(summary: str, date_str: str, start_time: str, end_time: str) -> str:
    """date_str: YYYY-MM-DD, start_time/end_time: HH:MM"""
    service = _get_service()
    event = {
        "summary": summary,
        "start": {
            "dateTime": f"{date_str}T{start_time}:00",
            "timeZone": TIMEZONE,
        },
        "end": {
            "dateTime": f"{date_str}T{end_time}:00",
            "timeZone": TIMEZONE,
        },
    }
    created = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    return created.get("summary", summary)
