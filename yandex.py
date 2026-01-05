import os
import sys
import json
import asyncio
import aiohttp
from config import YANDEX_API_KEY, YANDEX_MODEL_URI

sys.stdout.reconfigure(encoding="utf-8")

# Базовая директория проекта (где лежит yandex.py и prompt.txt)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPT_PATH = os.path.join(BASE_DIR, "prompt.txt")

# URL для Yandex GPT API
YANDEX_API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

# Загружаем базовый промпт при старте
try:
    with open(PROMPT_PATH, "r", encoding="utf-8") as file:
        BASE_PROMPT = file.read().strip()
except FileNotFoundError:
    print(f"❌ Ошибка: файл prompt.txt не найден по пути: {PROMPT_PATH}")
    BASE_PROMPT = ""
except Exception as e:
    print(f"❌ Ошибка при чтении prompt.txt ({PROMPT_PATH}): {e}")
    BASE_PROMPT = ""


def convert_history_to_yandex_format(history: list, system_prompt: str) -> list:
    """
    Конвертирует историю из формата OpenAI (role/content) в формат Yandex GPT (role/text).
    Добавляет системный промпт как первое сообщение.
    """
    yandex_messages = []
    
    # Добавляем системный промпт как первое сообщение
    if system_prompt:
        yandex_messages.append({
            "role": "system",
            "text": system_prompt
        })
    
    # Конвертируем остальные сообщения
    for msg in history:
        role = msg.get("role", "user")
        # Yandex GPT использует "text" вместо "content"
        content = msg.get("content", msg.get("text", ""))
        
        if role in ["user", "assistant", "system"]:
            yandex_messages.append({
                "role": role,
                "text": content
            })
    
    return yandex_messages


async def ai_generate(history: list):
    """
    Асинхронный запрос к Yandex GPT API.
    
    Args:
        history: Список сообщений в формате [{"role": "user"/"assistant", "content": "..."}]
    
    Returns:
        str: Сгенерированный текст ответа
    """
    try:
        # На каждый вызов читаем актуальный prompt.txt,
        # чтобы там уже был [CHARACTER] + базовый промпт.
        try:
            with open(PROMPT_PATH, "r", encoding="utf-8") as f:
                full_prompt = f.read().strip()
        except Exception:
            # Фоллбек — используем базовый промпт из момента запуска
            full_prompt = BASE_PROMPT
        
        # Конвертируем историю в формат Yandex GPT
        yandex_messages = convert_history_to_yandex_format(history, full_prompt)
        
        # Формируем запрос к Yandex GPT API
        request_data = {
            "modelUri": YANDEX_MODEL_URI,
            "completionOptions": {
                "stream": False,
                "temperature": 0.6,
                "maxTokens": "2000"
            },
            "messages": yandex_messages
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Api-Key {YANDEX_API_KEY}"
        }
        
        # Выполняем асинхронный запрос
        async with aiohttp.ClientSession() as session:
            async with session.post(
                YANDEX_API_URL,
                headers=headers,
                json=request_data,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status == 200:
                    try:
                        result = await response.json()
                        # Извлекаем текст ответа из структуры Yandex GPT
                        if "result" in result and "alternatives" in result["result"]:
                            if len(result["result"]["alternatives"]) > 0:
                                return result["result"]["alternatives"][0]["message"]["text"]
                        return "⚠️ Пустой ответ от Yandex GPT API."
                    except json.JSONDecodeError as e:
                        error_text = await response.text()
                        print(f"⚠️ Ошибка парсинга JSON от Yandex GPT: {e}, ответ: {error_text}")
                        return (
                            "⚠️ <b>Ошибка формата ответа</b>\n\n"
                            "🔴 Сервер Yandex GPT вернул некорректный ответ.\n\n"
                            "<i>Попробуйте снова через несколько секунд.</i>"
                        )
                else:
                    error_text = await response.text()
                    error_message = f"HTTP {response.status}: {error_text}"
                    # Детальное логирование для отладки
                    print(f"⚠️ Ошибка Yandex GPT API:")
                    print(f"   Статус: {response.status}")
                    print(f"   Ответ: {error_text}")
                    print(f"   ModelUri: {YANDEX_MODEL_URI}")
                    print(f"   API Key (первые 10 символов): {YANDEX_API_KEY[:10]}...")
                    return handle_yandex_error(response.status, error_message)
    
    except aiohttp.ClientError as e:
        error_message = str(e)
        print(f"⚠️ Ошибка сети при запросе к Yandex GPT: {e}")
        return (
            "⚠️ <b>Ошибка сети</b>\n\n"
            "🔴 Не удалось подключиться к серверу Yandex GPT.\n\n"
            "<i>Проверьте подключение к интернету и попробуйте снова.</i>"
        )
    except asyncio.TimeoutError:
        print("⚠️ Таймаут при запросе к Yandex GPT")
        return (
            "⚠️ <b>Превышено время ожидания</b>\n\n"
            "🔴 Сервер Yandex GPT не ответил в течение 60 секунд.\n\n"
            "<i>Попробуйте снова через несколько секунд.</i>"
        )
    except Exception as e:
        print(f"⚠️ Неизвестная ошибка при запросе к Yandex GPT: {e}")
        return (
            "⚠️ <b>Внутренняя ошибка</b>\n\n"
            f"Произошла непредвиденная ошибка: {str(e)}\n\n"
            "<i>Попробуйте снова. Если проблема сохраняется, обратитесь к администратору.</i>"
        )


def handle_yandex_error(status_code: int, error_message: str) -> str:
    """Обрабатывает ошибки Yandex GPT API и возвращает понятное сообщение пользователю."""
    if status_code == 401:
        return (
            "⚠️ <b>Ошибка аутентификации</b>\n\n"
            "🔴 Неверный или недействительный API ключ Yandex GPT.\n\n"
            "💡 <b>Решение:</b>\n"
            "Проверьте правильность API ключа в файле config.py.\n\n"
            "<i>Обратитесь к администратору бота.</i>"
        )
    elif status_code == 403:
        return (
            "⚠️ <b>Доступ запрещен</b>\n\n"
            "🔴 У вашего API ключа нет доступа к Yandex GPT.\n\n"
            "💡 <b>Инструкция по исправлению:</b>\n\n"
            "1. Перейдите в консоль Yandex Cloud: https://console.cloud.yandex.ru/\n"
            "2. Выберите каталог с вашим проектом\n"
            "3. Перейдите в раздел «Сервисные аккаунты»\n"
            "4. Создайте сервисный аккаунт (если его нет)\n"
            "5. Назначьте роль: <b>ai.languageModels.user</b>\n"
            "6. Создайте новый API-ключ для этого аккаунта\n"
            "7. Обновите YANDEX_API_KEY в config.py\n\n"
            "📝 <i>Также убедитесь, что платежный аккаунт активен.</i>"
        )
    elif status_code == 429:
        return (
            "⚠️ <b>Превышен лимит запросов</b>\n\n"
            "🔴 Слишком много запросов к Yandex GPT API. Попробуйте через несколько секунд.\n\n"
            "<i>Пожалуйста, подождите немного и попробуйте снова.</i>"
        )
    elif status_code in [500, 502, 503]:
        return (
            "⚠️ <b>Сервис временно недоступен</b>\n\n"
            "🔴 Сервер Yandex GPT временно не отвечает.\n\n"
            "<i>Попробуйте снова через несколько минут.</i>"
        )
    else:
        return (
            "⚠️ <b>Ошибка при обращении к Yandex GPT</b>\n\n"
            f"Код ошибки: {status_code}\n"
            f"Детали: {error_message}\n\n"
            "<i>Попробуйте снова чуть позже. Если проблема сохраняется, обратитесь к администратору.</i>"
        )
