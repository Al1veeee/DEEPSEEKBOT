import os
import sys
from openai import AsyncOpenAI, OpenAIError
from config import AI_TOKEN

sys.stdout.reconfigure(encoding="utf-8")

os.environ["OPENAI_API_KEY"] = AI_TOKEN

client = AsyncOpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENAI_API_KEY"),
)

# Загружаем промпт из файла
try:
    with open("prompt.txt", "r", encoding="utf-8") as file:
        prompt_content = file.read().strip()
except FileNotFoundError:
    print("❌ Ошибка: файл prompt.txt не найден")
    sys.exit(1)
except Exception as e:
    print(f"❌ Ошибка при чтении prompt.txt: {e}")
    sys.exit(1)


async def ai_generate(messages: list):
    """Асинхронный запрос к DeepSeek API"""
    try:
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