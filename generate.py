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
        error_message = str(e)
        print(f"⚠️ Ошибка OpenAI API: {e}")
        
        # Обработка специфичных ошибок
        if "402" in error_message or "Insufficient credits" in error_message or "never purchased credits" in error_message:
            return (
                "⚠️ <b>Недостаточно кредитов на аккаунте</b>\n\n"
                "🔴 На вашем аккаунте OpenRouter закончились кредиты или они никогда не были приобретены.\n\n"
                "💡 <b>Решение:</b>\n"
                "1. Проверьте баланс на https://openrouter.ai/settings/credits\n"
                "2. Убедитесь, что используете правильный API ключ\n"
                "3. При необходимости пополните баланс\n\n"
                "<i>Обратитесь к администратору бота для решения проблемы.</i>"
            )
        elif "401" in error_message or "Invalid API key" in error_message or "authentication" in error_message.lower():
            return (
                "⚠️ <b>Ошибка аутентификации</b>\n\n"
                "🔴 Неверный или недействительный API ключ.\n\n"
                "💡 <b>Решение:</b>\n"
                "Проверьте правильность API ключа в настройках бота.\n\n"
                "<i>Обратитесь к администратору бота.</i>"
            )
        elif "429" in error_message or "rate limit" in error_message.lower():
            return (
                "⚠️ <b>Превышен лимит запросов</b>\n\n"
                "🔴 Слишком много запросов к API. Попробуйте через несколько секунд.\n\n"
                "<i>Пожалуйста, подождите немного и попробуйте снова.</i>"
            )
        elif "500" in error_message or "503" in error_message:
            return (
                "⚠️ <b>Сервис временно недоступен</b>\n\n"
                "🔴 Сервер API временно не отвечает.\n\n"
                "<i>Попробуйте снова через несколько минут.</i>"
            )
        else:
            # Общая ошибка для остальных случаев
            return (
                "⚠️ <b>Ошибка при обращении к ИИ</b>\n\n"
                f"Детали: {error_message}\n\n"
                "<i>Попробуйте снова чуть позже. Если проблема сохраняется, обратитесь к администратору.</i>"
            )

    except Exception as e:
        print(f"⚠️ Неизвестная ошибка: {e}")
        return (
            "⚠️ <b>Внутренняя ошибка</b>\n\n"
            "Произошла непредвиденная ошибка при обработке запроса.\n\n"
            "<i>Попробуйте снова. Если проблема сохраняется, обратитесь к администратору.</i>"
        )