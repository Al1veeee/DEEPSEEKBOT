import os
import sys
from openai import AsyncOpenAI, OpenAIError
from config import AI_TOKEN

sys.stdout.reconfigure(encoding="utf-8")

os.environ["OPENAI_API_KEY"] = AI_TOKEN

# Базовая директория проекта (где лежит generate.py и prompt.txt)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPT_PATH = os.path.join(BASE_DIR, "prompt.txt")

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENAI_API_KEY"),
)

try:
    with open(PROMPT_PATH, "r", encoding="utf-8") as file:
        BASE_PROMPT = file.read().strip()
except FileNotFoundError:
    print(f"❌ Ошибка: файл prompt.txt не найден по пути: {PROMPT_PATH}")
    sys.exit(1)
except Exception as e:
    print(f"❌ Ошибка при чтении prompt.txt ({PROMPT_PATH}): {e}")
    sys.exit(1)


async def ai_generate(history: list):
    """Асинхронный запрос к DeepSeek API"""
    try:
        # На каждый вызов читаем актуальный prompt.txt,
        # чтобы там уже был [CHARACTER] + базовый промпт.
        try:
            with open(PROMPT_PATH, "r", encoding="utf-8") as f:
                full_prompt = f.read().strip()
        except Exception:
            # Фоллбек — используем базовый промпт из момента запуска
            full_prompt = BASE_PROMPT

        messages = [
            {"role": "system", "content": full_prompt},
            *history,
        ]

        response = await client.chat.completions.create(
            model="deepseek/deepseek-chat",
            messages=messages,
        )
        return response.choices[0].message.content

    except OpenAIError as e:
        print(f"⚠️ Ошибка OpenAI API: {e}")
        return "⚠️ <b>Ошибка при обращении к ИИ.</b>\nПопробуй снова чуть позже."

    except Exception as e:
        print(f"⚠️ Неизвестная ошибка: {e}")
        return "⚠️ <b>Внутренняя ошибка.</b>\nПопробуй снова."