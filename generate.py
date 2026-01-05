import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

# Базовая директория проекта (где лежит generate.py и prompt.txt)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROMPT_PATH = os.path.join(BASE_DIR, "prompt.txt")

# Импортируем функцию генерации из yandex.py вместо OpenAI
from yandex import ai_generate, BASE_PROMPT

# Экспортируем для обратной совместимости
__all__ = ['ai_generate', 'BASE_PROMPT']