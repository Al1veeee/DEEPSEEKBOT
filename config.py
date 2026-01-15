import os
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

# OpenAI/OpenRouter токен (не используется, заменен на Yandex GPT)
AI_TOKEN = os.getenv('AI_TOKEN', '')

# Telegram Bot Token
TG_TOKEN = os.getenv('TG_TOKEN', '')

# Yandex GPT настройки
# ВАЖНО: Для работы API ключа необходимо:
# 1. Создать сервисный аккаунт в Yandex Cloud
# 2. Назначить роль: ai.languageModels.user
# 3. Создать API-ключ для этого аккаунта
# 4. Убедиться, что платежный аккаунт активен
# Подробнее: https://yandex.cloud/ru/docs/foundation-models/operations/get-api-key
YANDEX_API_KEY = os.getenv('YANDEX_API_KEY', '')
# Формат: gpt://<folder-id>/<model-name>
# folder-id - ID каталога в Yandex Cloud (можно найти в консоли)
# model-name: yandexgpt-lite, yandexgpt, yandexgpt-pro
YANDEX_MODEL_URI = os.getenv('YANDEX_MODEL_URI', 'gpt://b1gdoose5habmm2ishlb/qwen3-235b-a22b-fp8/latest')