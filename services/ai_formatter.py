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

_SYSTEM_PROMPT = """Ты — редактор контента для социальных сетей в сфере movement education / contemporary dance.

Переструктурируй текст по схеме:
- hook: цепляющий заголовок (1-2 предложения, выразительно и кратко)
- tags: ключевые слова / теги / уровень / стиль (через запятую или /)
- body: основной описательный текст (подробно, атмосферно)
- cta: призыв к действию (1 предложение, с энергией)
- hashtags: список из 5-8 хэштегов на английском по теме текста (movement education, partnering, dance и т.д.)

Отвечай ТОЛЬКО валидным JSON без пояснений:
{"hook": "...", "tags": "...", "body": "...", "cta": "...", "hashtags": ["tag1", "tag2"]}"""


async def reformat_text(raw_text: str) -> dict:
    completion = await client.chat.completions.create(
        model="openai/gpt-4o-mini",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
    )
    response_text = completion.choices[0].message.content.strip()
    return json.loads(response_text)
