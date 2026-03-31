import asyncio
import os
import tempfile

from groq import Groq

_groq_client: Groq | None = None


def _get_groq_client() -> Groq:
    global _groq_client
    if _groq_client is None:
        _groq_client = Groq(api_key=os.getenv("GROQ_API_KEY", "placeholder"))
    return _groq_client


def _transcribe_sync(file_bytes: bytes) -> str:
    client = _get_groq_client()
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        with open(tmp_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=("voice.ogg", audio_file, "audio/ogg"),
                language="ru",
            )
        return transcript.text
    finally:
        os.unlink(tmp_path)


async def transcribe_audio(file_bytes: bytes) -> str:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _transcribe_sync, file_bytes)
