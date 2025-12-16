from aiogram import Router, F, types
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)
from aiogram.enums import ParseMode
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

import sys
import os
import random
import asyncio
import logging
import re

CURRENT_DIR = os.path.dirname(__file__)
PROMPT_PATH = os.path.join(CURRENT_DIR, "prompt.txt")
START_SCENE_PATH = os.path.join(CURRENT_DIR, "start_scene.txt")

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from generate import ai_generate, BASE_PROMPT

router = Router()

logger = logging.getLogger(__name__)

class CreateChar(StatesGroup):
    race = State()
    name = State()
    char_class = State()
    background = State()
    stats = State()
    apply_bonuses = State()
    personality = State()
    appearance = State()
    finish = State()

class Gen(StatesGroup):
    wait = State()
    history = State()
    custom = State()

RACES = {1:"Человек",2:"Эльф",3:"Дроу",4:"Гном",5:"Дварф",6:"Драконорожденный",7:"Тифлинг",8:"Полуэльф",9:"Полурослик",10:"Орк",11:"Полуорк",12:"Кобольд",13:"Шейфтер",14:"Людоящер"}
CLASSES = {1:"Воин",2:"Паладин",3:"Плут",4:"Волшебник",5:"Жрец",6:"Бард",7:"Варвар",8:"Друид",9:"Монах",10:"Следопыт",11:"Чародей",12:"Изобретатель"}
BACKGROUNDS = {1:"Народный герой",2:"Благородный",3:"Отшельник",4:"Бродяга",5:"Артист",6:"Аферист",7:"Солдат",8:"Торговец",9:"Писарь",10:"Следопыт",11:"Ремесленник"}
RACE_BONUSES = {
    "Человек": {"Сила": 1, "Ловкость": 1, "Телосложение": 1, "Интеллект": 1, "Мудрость": 1, "Харизма": 1},
    "Эльф": {"Ловкость": 2, "Интеллект": 1},
    "Дроу": {"Ловкость": 2, "Харизма": 1},
    "Гном": {"Интеллект": 2, "Телосложение": 1},
    "Дварф": {"Телосложение": 2, "Мудрость": 1},
    "Драконорожденный": {"Сила": 2, "Харизма": 1},
    "Тифлинг": {"Харизма": 2, "Интеллект": 1},
    "Полуэльф": {"Харизма": 2, "Ловкость": 1, "Интеллект": 1},
    "Полурослик": {"Ловкость": 2, "Харизма": 1},
    "Орк": {"Сила": 2, "Телосложение": 1},
    "Полуорк": {"Сила": 2, "Телосложение": 1},
    "Кобольд": {"Ловкость": 2, "Интеллект": 1},
    "Шейфтер": {"Ловкость": 2, "Харизма": 1},
    "Людоящер": {"Телосложение": 2, "Мудрость": 1},
}

def roll_4d6_drop_lowest():
    rolls = [random.randint(1,6) for _ in range(4)]
    rolls_sorted = sorted(rolls)
    return sum(rolls_sorted[1:]), rolls, rolls_sorted[0]

def generate_stats_auto():
    labels = ["Сила","Ловкость","Телосложение","Интеллект","Мудрость","Харизма"]
    stats = {}
    report_lines = []
    for lab in labels:
        total, rolls, dropped = roll_4d6_drop_lowest()
        stats[lab] = total
        report_lines.append(f"{lab}: {total}")
    return stats, "\n".join(report_lines)

def apply_race_bonuses(stats: dict, race: str):
    """Применяет бонусы расы к характеристикам, возвращает обновленные статы и отчёт."""
    bonus = RACE_BONUSES.get(race, {})
    if not bonus:
        return stats, "Бонусы расы: нет данных."

    updated = stats.copy()
    applied = []
    for stat_name, inc in bonus.items():
        if stat_name in updated:
            updated[stat_name] += inc
            applied.append(f"{stat_name} {inc:+d} ⇒ {updated[stat_name]}")

    report = "Бонусы расы:\n" + "\n".join(applied) if applied else "Бонусы расы: нет изменений."
    return updated, report

def trim_history(history, max_pairs=8):
    limit = max_pairs*2 + 1
    return history[-limit:] if len(history) > limit else history


async def process_user_turn(message: Message, state: FSMContext, user_content: str):
    """Добавляет ход игрока, запрашивает ответ ИИ и отдаёт его с кнопками выбора."""
    data = await state.get_data()
    history = data.get("history", [])

    history.append({"role": "user", "content": user_content})
    history = trim_history(history, max_pairs=10)
    await state.update_data(history=history)
    await state.set_state(Gen.wait)

    thinking_messages = [
        "🔮 <i>Магический шар показывает варианты...</i>",
        "📖 <i>Листаю древние манускрипты...</i>",
        "🎲 <i>Бросок костей судьбы...</i>",
        "⚡ <i>Наполняюсь магической энергией...</i>",
        "🌌 <i>Советуюсь со звездами...</i>",
        "🐉 <i>Слушаю мудрость драконов...</i>",
        "🌀 <i>Проникаю в пустоту разума...</i>",
        "✨ <i>Собираю магические частицы...</i>",
        "🔍 <i>Ищу ответ в хрониках веков...</i>",
        "💭 <i>Погружаюсь в глубокие размышления...</i>",
        "🌟 <i>Призываю силу древних артефактов...</i>",
    ]

    await message.answer(random.choice(thinking_messages), parse_mode=ParseMode.HTML)

    raw = await safe_ai_generate(history, state, Gen.history)
    response = raw if raw else "⚠️ Пустой ответ от сервера."

    # Сохраняем оригинальный ответ (Markdown) в историю
    history.append({"role": "assistant", "content": response})
    history = trim_history(history, max_pairs=10)
    await state.update_data(history=history)
    await state.set_state(Gen.history)

    # Отправляем HTML-версию с кнопками выбора
    response_html = markdown_to_html(response)
    await message.answer(response_html, parse_mode=ParseMode.HTML, reply_markup=make_choice_keyboard())

def make_game_keyboard():
    """Создаёт красивую игровую клавиатуру с эмодзи"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📊 Статус"),
                KeyboardButton(text="🎒 Инвентарь")
            ],
            [
                KeyboardButton(text="✨ Заклинания"),
                KeyboardButton(text="💰 Торговля")
            ],
            [
                KeyboardButton(text="🛌 Отдых")
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите действие или напишите свой вариант..."
    )


def make_choice_keyboard():
    """Клавиатура выбора действия в сцене"""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="1"), KeyboardButton(text="2"), KeyboardButton(text="3")],
            [KeyboardButton(text="Свой вариант")],
            [
                KeyboardButton(text="📊 Статус"),
                KeyboardButton(text="🎒 Инвентарь")
            ],
            [
                KeyboardButton(text="✨ Заклинания"),
                KeyboardButton(text="💰 Торговля")
            ],
            [
                KeyboardButton(text="🛌 Отдых")
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите 1/2/3 или нажмите «Свой вариант»"
    )

def markdown_to_html(text: str) -> str:
    """
    Конвертирует Markdown форматирование в HTML для Telegram.
    Обрабатывает: **жирный**, *курсив*, списки с -, кавычки
    """
    if not text:
        return text
    
    # Сначала защищаем уже существующие HTML теги
    # Временно заменяем их на плейсхолдеры
    html_tags = []
    tag_pattern = r'<[^>]+>'
    
    def replace_tag(match):
        html_tags.append(match.group(0))
        return f"__HTML_TAG_{len(html_tags)-1}__"
    
    text = re.sub(tag_pattern, replace_tag, text)
    
    # Экранируем специальные символы HTML
    text = text.replace("&", "&amp;")
    
    # Конвертируем **жирный текст** в <b>жирный текст</b>
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    
    # Конвертируем *курсив* в <i>курсив</i> (но не **)
    # Используем негативный lookbehind и lookahead, чтобы не трогать уже обработанные **
    text = re.sub(r'(?<!\*)\*([^*\n]+?)\*(?!\*)', r'<i>\1</i>', text)
    
    # Обрабатываем списки с дефисом в начале строки
    # Заменяем "- пункт" на "• пункт"
    lines = text.split('\n')
    result_lines = []
    for line in lines:
        # Проверяем, начинается ли строка с "- " (список)
        if re.match(r'^\s*-\s+', line):
            # Убираем "- " и добавляем маркер списка
            line = re.sub(r'^\s*-\s+', '• ', line)
        result_lines.append(line)
    text = '\n'.join(result_lines)
    
    # Восстанавливаем HTML теги
    for i, tag in enumerate(html_tags):
        text = text.replace(f"__HTML_TAG_{i}__", tag)
    
    return text

def validate_text_input(text, min_length=3, max_length=500):
    """
    Валидирует и очищает пользовательский ввод.
    Возвращает (is_valid, cleaned_text, error_msg)
    """
    if not text or not isinstance(text, str):
        return False, "", "❌ <b>Ошибка ввода</b>\n\nПожалуйста, введите текст."
    
    # Очищаем текст от лишних пробелов
    cleaned_text = text.strip()
    
    # Проверка на пустую строку после очистки
    if not cleaned_text:
        return False, "", f"❌ <b>Пустой ввод</b>\n\nПожалуйста, введите текст (минимум {min_length} символов)."
    
    # Проверка минимальной длины
    if len(cleaned_text) < min_length:
        return False, cleaned_text, f"❌ <b>Слишком короткий текст</b>\n\nМинимум {min_length} символов. Вы ввели {len(cleaned_text)}. Попробуйте ещё раз!"
    
    # Проверка максимальной длины
    if len(cleaned_text) > max_length:
        return False, cleaned_text, f"❌ <b>Слишком длинный текст</b>\n\nМаксимум {max_length} символов. Вы ввели {len(cleaned_text)}. Сократите описание."
    
    # Проверка на HTML теги (защита от XSS)
    if re.search(r'<[^>]+>', cleaned_text):
        return False, cleaned_text, "❌ <b>Недопустимые символы</b>\n\nТекст содержит HTML теги (< >), которые не разрешены. Исправьте и попробуйте снова."
    
    # Проверка на потенциально опасные символы (но разрешаем скобки для описаний)
    # Запрещаем только угловые скобки и фигурные скобки, которые могут сломать форматирование
    if re.search(r'[<>{}]', cleaned_text):
        return False, cleaned_text, "❌ <b>Недопустимые символы</b>\n\nТекст содержит символы < > {{ }}, которые не разрешены. Исправьте и попробуйте снова."
    
    # Проверка на слишком длинные "слова" без пробелов (возможная ошибка ввода)
    words = cleaned_text.split()
    if words:
        max_word_length = max(len(word) for word in words)
        if max_word_length > 100:
            return False, cleaned_text, "❌ <b>Подозрительный ввод</b>\n\nОбнаружено слишком длинное слово без пробелов. Проверьте правильность ввода."
    
    return True, cleaned_text, ""

async def safe_ai_generate(history, state: FSMContext, fallback_state, timeout_sec:int=60):
    try:
        raw = await asyncio.wait_for(ai_generate(history), timeout=timeout_sec)
        if raw is None: raise RuntimeError("ai_generate вернул None")
        return raw
    except asyncio.TimeoutError:
        logger.exception("ai_generate timeout")
        await state.set_state(fallback_state)
        return "⚠️ Сервис генерации не отвечает (таймаут)."
    except Exception as e:
        logger.exception("Ошибка при вызове ai_generate: %s", e)
        await state.set_state(fallback_state)
        return f"⚠️ Произошла ошибка при генерации: {str(e)}"

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🎲 Начать приключение", callback_data="start_game")]]
    )

    await message.answer(
        "⚔️ <b>Добро пожаловать в мир Dungeons & Dragons!</b> ⚔️\n\n"
        "🌌 Здесь начинаются легенды...\n"
        "🐉 Здесь решаются судьбы...\n"
        "✨ Здесь рождаются герои...\n\n"
        "<i>Осмелишься ли ты сделать первый шаг в это эпическое приключение?</i>",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML,
    )

@router.callback_query(F.data == "start_game")
async def start_game_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()

    text = "🛡️ <b>Создание персонажа — Шаг 1 из 7</b>\n\n"
    text += "🌍 <b>Выберите расу вашего героя:</b>\n\n"
    for num, race in RACES.items():
        text += f"  <b>{num}.</b> {race}\n"
    text += "\n✨ <i>Введите номер выбранной расы (1-14):</i>"

    await callback.message.edit_text(text, parse_mode=ParseMode.HTML)
    await state.set_state(CreateChar.race)

@router.message(CreateChar.race)
async def set_race(message: Message, state: FSMContext):
    try:
        num = int(message.text.strip())
        race = RACES[num]
    except Exception:
        return await message.answer(
            "❌ <b>Ошибка выбора</b>\n\n"
            "Пожалуйста, введите <b>только номер</b> расы из списка (от 1 до 14)."
        )

    await state.update_data(race=race)
    await state.set_state(CreateChar.name)
    await message.answer(
        f"✅ <b>Раса выбрана:</b> {race}\n\n"
        "✏️ <b>Создание персонажа — Шаг 2 из 7</b>\n\n"
        "📝 <b>Введите имя вашего персонажа:</b>\n\n"
        "<i>Имя должно быть от 2 до 50 символов. Это имя будет известно по всему миру!</i>",
        parse_mode=ParseMode.HTML
    )

@router.message(CreateChar.name)
async def set_name(message: Message, state: FSMContext):
    is_valid, cleaned_name, error_msg = validate_text_input(message.text, min_length=2, max_length=50)
    if not is_valid:
        return await message.answer(error_msg, parse_mode=ParseMode.HTML)
    
    await state.update_data(name=cleaned_name)
    text = f"✅ <b>Имя выбрано:</b> {cleaned_name}\n\n"
    text += "⚔️ <b>Создание персонажа — Шаг 3 из 7</b>\n\n"
    text += "🎭 <b>Выберите класс вашего героя:</b>\n\n"
    for num, cl in CLASSES.items():
        text += f"  <b>{num}.</b> {cl}\n"
    text += "\n✨ <i>Введите номер выбранного класса (1-12):</i>"
    await message.answer(text, parse_mode=ParseMode.HTML)
    await state.set_state(CreateChar.char_class)

@router.message(CreateChar.char_class)
async def set_class(message: Message, state: FSMContext):
    try:
        cl = CLASSES[int(message.text.strip())]
    except Exception:
        return await message.answer(
            "❌ <b>Ошибка выбора</b>\n\n"
            "Пожалуйста, введите <b>только номер</b> класса из списка (от 1 до 12)."
        )

    await state.update_data(char_class=cl)
    text = f"✅ <b>Класс выбран:</b> {cl}\n\n"
    text += "📖 <b>Создание персонажа — Шаг 4 из 7</b>\n\n"
    text += "📚 <b>Выберите предысторию вашего героя:</b>\n\n"
    for num, bg in BACKGROUNDS.items():
        text += f"  <b>{num}.</b> {bg}\n"
    text += "\n✨ <i>Введите номер выбранной предыстории (1-11):</i>"
    await message.answer(text, parse_mode=ParseMode.HTML)
    await state.set_state(CreateChar.background)

@router.message(CreateChar.background)
async def set_background(message: Message, state: FSMContext):
    try:
        bg = BACKGROUNDS[int(message.text.strip())]
    except Exception:
        return await message.answer(
            "❌ <b>Ошибка выбора</b>\n\n"
            "Пожалуйста, введите <b>только номер</b> предыстории из списка (от 1 до 11)."
        )

    await state.update_data(background=bg)
    stats_dict, stats_report = generate_stats_auto()
    await state.update_data(stats=stats_dict)
    await state.update_data(stats_report=stats_report)

    stats_emoji_map = {
        "Сила": "💪",
        "Ловкость": "🏹",
        "Телосложение": "🛡️",
        "Интеллект": "📚",
        "Мудрость": "🔮",
        "Харизма": "🎭"
    }
    
    stats_display = []
    for line in stats_report.split("\n"):
        stat_name = line.split(":")[0]
        emoji = stats_emoji_map.get(stat_name, "•")
        stats_display.append(f"{emoji} {line}")
    
    await message.answer(
        f"✅ <b>Предыстория выбрана:</b> {bg}\n\n"
        "🎲 <b>Создание персонажа — Шаг 5 из 7</b>\n\n"
        "⚡ <b>Характеристики персонажа:</b>\n\n" +
        "\n".join(stats_display) +
        "\n\n🌟 <b>Применить бонусы расы автоматически?</b>\n"
        "<i>Введите <b>да</b> или <b>нет</b></i>",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(CreateChar.apply_bonuses)

@router.message(CreateChar.apply_bonuses)
async def set_bonuses(message: Message, state: FSMContext):
    answer = message.text.strip().lower()
    if answer not in ("да", "нет"):
        return await message.answer(
            "❌ <b>Некорректный ответ</b>\n\n"
            "Пожалуйста, введите <b>да</b> или <b>нет</b>."
        )

    await state.update_data(apply_bonuses=answer)

    if answer == "да":
        data = await state.get_data()
        current_stats = data.get("stats", {})
        race = data.get("race", "")
        updated_stats, bonus_report = apply_race_bonuses(current_stats, race)

        # Обновляем характеристики и отчет
        await state.update_data(stats=updated_stats)
        stats_lines = [f"{k}: {v}" for k, v in updated_stats.items()]
        stats_report = "\n".join(stats_lines)
        await state.update_data(stats_report=stats_report)

        stats_emoji_map = {
            "Сила": "💪",
            "Ловкость": "🏹",
            "Телосложение": "🛡️",
            "Интеллект": "📚",
            "Мудрость": "🔮",
            "Харизма": "🎭"
        }
        
        stats_display = []
        for line in stats_report.split("\n"):
            stat_name = line.split(":")[0]
            emoji = stats_emoji_map.get(stat_name, "•")
            stats_display.append(f"{emoji} {line}")
        
        await message.answer(
            "✨ <b>Бонусы расы успешно применены!</b>\n\n"
            f"{bonus_report}\n\n"
            "⚡ <b>Обновлённые характеристики:</b>\n\n" +
            "\n".join(stats_display),
            parse_mode=ParseMode.HTML
        )

    await message.answer(
        "🧠 <b>Создание персонажа — Шаг 6 из 7</b>\n\n"
        "💭 <b>Опишите характер вашего героя:</b>\n\n"
        "<i>Расскажите о его основных чертах, мотивациях, страхах, принципах и особенностях личности.\n"
        "Это поможет создать уникального и живого персонажа!</i>\n\n"
        "📝 <i>Минимум 10 символов, максимум 1000.</i>",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(CreateChar.personality)

@router.message(CreateChar.personality)
async def set_personality(message: Message, state: FSMContext):
    is_valid, cleaned_personality, error_msg = validate_text_input(message.text, min_length=10, max_length=1000)
    if not is_valid:
        return await message.answer(error_msg, parse_mode=ParseMode.HTML)
    
    await state.update_data(personality=cleaned_personality)
    await message.answer(
        f"✅ <b>Характер описан!</b>\n\n"
        "🎨 <b>Создание персонажа — Шаг 7 из 7</b>\n\n"
        "👁️ <b>Опишите внешность вашего героя:</b>\n\n"
        "<i>Расскажите о его внешних чертах, одежде, отличительных особенностях, росте, телосложении.\n"
        "Создайте яркий визуальный образ, который запомнится!</i>\n\n"
        "📝 <i>Минимум 10 символов, максимум 1000.</i>",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(CreateChar.appearance)

@router.message(CreateChar.appearance)
async def set_appearance(message: Message, state: FSMContext):
    is_valid, cleaned_appearance, error_msg = validate_text_input(message.text, min_length=10, max_length=1000)
    if not is_valid:
        return await message.answer(error_msg, parse_mode=ParseMode.HTML)

    await state.update_data(appearance=cleaned_appearance)
    
    await finish_creation(message, state)

async def finish_creation(message: Message, state: FSMContext):
    data = await state.get_data()

    # ---------- 0. Бросок стартовых монет (1d6+1) ----------
    if "coins" not in data or data.get("coins") == "1d6+1":
        coins_roll = random.randint(1, 6) + 1
        await state.update_data(coins=coins_roll)
        data["coins"] = coins_roll  # Обновляем локальную переменную

    # ---------- 1. Характеристики ----------
    stats = data.get("stats", {})
    stats_lines = [f"{k}: {v}" for k, v in stats.items()]
    stats_str = "\n".join(stats_lines)
    
    # Получаем актуальные данные после обновления монет
    final_data = await state.get_data()
    coins_amount = final_data.get("coins", random.randint(1, 6) + 1)

    # ---------- 2. CHARACTER блок ----------
    character_block = (
        "[CHARACTER]\n"
        f"Имя: {data.get('name','')}\n"
        f"Раса: {data.get('race','')}\n"
        f"Класс: {data.get('char_class','')}\n"
        f"Предыстория: {data.get('background','')}\n"
        f"Характеристики:\n{stats_str}\n"
        f"Бонусы_расы: {data.get('apply_bonuses','')}\n"
        f"Характер: {data.get('personality','')}\n"
        f"Внешность: {data.get('appearance','')}\n"
        f"День_старта: {data.get('day_counter', 1)}\n"
        f"Снаряжение: {data.get('equipment','Базовая экипировка')}\n"
        f"Монеты: {coins_amount}\n"
        f"Сумка: {data.get('bag','Пустая сумка')}\n"
        "[/CHARACTER]\n"
    )

    # ---------- 3. Запись prompt.txt ----------
    try:
        with open(PROMPT_PATH, "w", encoding="utf-8") as f:
            # В файл кладём текущего персонажа + неизменяемый базовый промпт.
            f.write(character_block + "\n" + BASE_PROMPT)
    except Exception as e:
        logger.exception("Ошибка записи prompt.txt: %s", e)
        await message.answer("⚠️ Не удалось сохранить персонажа.", parse_mode=ParseMode.HTML)
        return

    # ---------- 4. Подготовка данных для сцены ----------
    scene_data = {
        "name": data.get("name", ""),
        "race": data.get("race", ""),
        "class": data.get("char_class", ""),
        "background": data.get("background", ""),
        "personality": data.get("personality", ""),
        "appearance": data.get("appearance", ""),
        "str": stats.get("Сила", 0),
        "dex": stats.get("Ловкость", 0),
        "con": stats.get("Телосложение", 0),
        "int": stats.get("Интеллект", 0),
        "wis": stats.get("Мудрость", 0),
        "cha": stats.get("Харизма", 0),
        "armor": data.get("equipment", "Базовая экипировка"),
        "weapon": "Основное оружие",
        "coins": coins_amount,
    }

    # ---------- 5. Загрузка start_scene.txt ----------
    try:
        with open(START_SCENE_PATH, "r", encoding="utf-8") as f:
            template = f.read()
    except Exception:
        template = "{name} начинает своё приключение..."

    # ---------- 6. Формирование стартовой сцены ----------
    start_scene = template.format(**scene_data)

    # ---------- 7. Формирование информации о персонаже для вывода ----------
    stats_emoji = {
        "Сила": "💪",
        "Ловкость": "🏹",
        "Телосложение": "🛡️",
        "Интеллект": "📚",
        "Мудрость": "🔮",
        "Харизма": "🎭"
    }
    
    character_info = (
        f"🧙♂️ <b>Персонаж создан успешно!</b>\n\n"
        f"{data.get('name', '')} — {data.get('race', '')}, {data.get('char_class', '')} ({data.get('background', '')})\n\n"
        f"⚔️ <b>Характер:</b> {data.get('personality', '')}\n\n"
        f"👁️ <b>Внешность:</b> {data.get('appearance', '')}\n\n"
        f"<b>Характеристики:</b>\n\n"
    )
    
    for stat_name, stat_value in stats.items():
        emoji = stats_emoji.get(stat_name, "•")
        character_info += f"{emoji} {stat_name}: {stat_value}\n"
    
    character_info += (
        f"\n<b>Снаряжение:</b>\n\n"
        f"🎒 {data.get('equipment', 'Базовая экипировка')}\n\n"
        f"💰 Монеты: {coins_amount} золотых\n\n"
        f"<b>Счётчик дней:</b>\n\n"
        f"📅 День {data.get('day_counter', 1)}\n\n"
        f"⚠️ Напоминание: используйте /статус для проверки состояния персонажа\n\n"
        f"---\n\n"
    )
    
    # ---------- 8. Отправка информации о персонаже ----------
    await message.answer(
        character_info,
        parse_mode=ParseMode.HTML,
        reply_markup=make_choice_keyboard()
    )
    
    # ---------- 9. Инициализация истории и генерация первого ответа от ИИ ----------
    # Формируем запрос для ИИ, чтобы он сгенерировал стартовую сцену по шаблону
    # ВАЖНО: Информация о персонаже уже выведена отдельным сообщением, 
    # ИИ должен генерировать ТОЛЬКО стартовую сцену с вариантами действий
    initial_prompt = (
        f"Используй КАРКАС_ПЕРВОГО_ОТВЕТА из шаблона. "
        f"Информация о персонаже уже показана игроку отдельно. "
        f"Твоя задача - описать стартовую сцену для {data.get('name', '')} "
        f"({data.get('race', '')}, {data.get('char_class', '')}, {data.get('background', '')}). "
        f"Начни приключение в классической локации (дорога, таверна, лагерь). "
        f"Опиши локацию, время суток, атмосферу (2-4 абзаца). "
        f"Затем предложи ровно 3 варианта действий + возможность написать свой. "
        f"НЕ дублируй информацию о персонаже - она уже выведена."
    )
    
    history = [
        {"role": "user", "content": initial_prompt}
    ]
    await state.update_data(history=history)
    await state.set_state(Gen.wait)
    
    # Генерируем первый ответ от ИИ
    thinking_msg = await message.answer(
        "🔮 <i>Мастер готовит начало приключения...</i>",
        parse_mode=ParseMode.HTML
    )
    
    raw = await safe_ai_generate(history, state, Gen.history)
    response = raw if raw else "⚠️ Пустой ответ от сервера."

    # Сохраняем оригинальный ответ в историю (Markdown)
    history.append({"role": "assistant", "content": response})
    history = trim_history(history, max_pairs=10)
    await state.update_data(history=history)
    await state.set_state(Gen.history)

    # Конвертируем Markdown форматирование в HTML для отображения
    response_html = markdown_to_html(response)

    await message.answer(response_html, parse_mode=ParseMode.HTML, reply_markup=make_choice_keyboard())

@router.message(Gen.history)
async def continue_dialog(message: Message, state: FSMContext):
    user_text = (message.text or "").strip()

    # Разрешаем системные команды /... обрабатываться отдельными хендлерами
    if user_text.startswith("/"):
        return

    # Разрешаем прямой вызов кнопок-команд
    if user_text in {"📊 Статус", "🎒 Инвентарь", "✨ Заклинания", "💰 Торговля", "🛌 Отдых"}:
        return

    # Обработка вариантов выбора 1/2/3
    if user_text in {"1", "2", "3"}:
        user_content = f"Выбираю вариант {user_text}."
        return await process_user_turn(message, state, user_content)

    # Свой вариант — переключаемся в режим ввода собственного действия
    if user_text.lower() in {"свой вариант", "0"}:
        await state.set_state(Gen.custom)
        return await message.answer(
            "✏️ <b>Опиши свой вариант действия</b>\n\n"
            "Напиши, что делает герой. После отправки я продолжу сюжет.",
            parse_mode=ParseMode.HTML,
            reply_markup=ReplyKeyboardRemove(),
        )

    # Любой другой ввод — просим использовать кнопки
    await message.answer(
        "ℹ️ <b>Выбери действие кнопкой</b>\n\n"
        "Нажми <b>1</b>, <b>2</b> или <b>3</b>. "
        "Если нужен другой вариант — нажми «Свой вариант».",
        parse_mode=ParseMode.HTML,
        reply_markup=make_choice_keyboard(),
    )
    return


@router.message(Gen.custom)
async def custom_action(message: Message, state: FSMContext):
    user_text = (message.text or "").strip()
    if not user_text:
        return await message.answer(
            "❌ <b>Пустой ввод</b>\n\nОпиши действие героя текстом.",
            parse_mode=ParseMode.HTML,
        )

    # Возвращаемся к основному циклу диалога
    await process_user_turn(message, state, user_text)

@router.message(F.text.in_(["📊 Статус", "/статус"]) | Command("статус"))
async def cmd_status(message: Message, state: FSMContext):
    """Обработчик команды /статус"""
    data = await state.get_data()
    coins_amount = data.get("coins", 0)
    
    await message.answer(
        "📊 <b>Статус персонажа</b>\n\n"
        f"💰 Монеты: {coins_amount} золотых\n"
        f"📅 День: {data.get('day_counter', 1)}\n\n"
        "<i>Полная информация о персонаже будет доступна в будущих обновлениях.</i>",
        parse_mode=ParseMode.HTML
    )

@router.message(F.text.in_(["🎒 Инвентарь", "/инвентарь"]) | Command("инвентарь"))
async def cmd_inventory(message: Message, state: FSMContext):
    """Обработчик команды /инвентарь"""
    data = await state.get_data()
    bag = data.get("bag", "Пустая сумка")
    equipment = data.get("equipment", "Базовая экипировка")
    
    await message.answer(
        "🎒 <b>Инвентарь</b>\n\n"
        f"🎒 Сумка: {bag}\n"
        f"⚔️ Снаряжение: {equipment}\n\n"
        "<i>Детальный инвентарь будет доступен в будущих обновлениях.</i>",
        parse_mode=ParseMode.HTML
    )

@router.message(F.text.in_(["✨ Заклинания", "/заклинания"]) | Command("заклинания"))
async def cmd_spells(message: Message, state: FSMContext):
    """Обработчик команды /заклинания"""
    await message.answer(
        "✨ <b>Заклинания</b>\n\n"
        "<i>Список заклинаний будет доступен в будущих обновлениях.</i>",
        parse_mode=ParseMode.HTML
    )

@router.message(F.text.in_(["💰 Торговля", "/торговля"]) | Command("торговля"))
async def cmd_trade(message: Message, state: FSMContext):
    """Обработчик команды /торговля"""
    await message.answer(
        "💰 <b>Торговля</b>\n\n"
        "<i>Система торговли будет доступна в будущих обновлениях.</i>",
        parse_mode=ParseMode.HTML
    )

@router.message(F.text.in_(["🛌 Отдых", "/отдых"]) | Command("отдых"))
async def cmd_rest(message: Message, state: FSMContext):
    """Обработчик команды /отдых"""
    await message.answer(
        "🛌 <b>Отдых</b>\n\n"
        "<i>Система отдыха будет доступна в будущих обновлениях.</i>",
        parse_mode=ParseMode.HTML
    )

@router.message(Gen.wait)
async def stop_flood(message: Message):
    waiting_messages = [
        "⚙️ <i>Подожди, идёт обработка запроса...</i>",
        "⏳ <i>Магия еще не готова, подожди немного...</i>",
        "🔮 <i>Кристалл все еще показывает видения...</i>",
        "📜 <i>Древние свитки разворачиваются...</i>",
        "🌀 <i>Портал между мирами стабилизируется...</i>",
        "⚔️ <i>Совет мудрецов обдумывает твой вопрос...</i>",
        "🌠 <i>Звезды еще не сошлись для ответа...</i>",
        "🐲 <i>Дракон размышляет над твоими словами...</i>",
        "✨ <i>Магическая энергия накапливается...</i>",
        "🔍 <i>Поиск ответа в летописях продолжается...</i>",
        "💫 <i>Силы магии все еще работают...</i>",
        "🛡️ <i>Хранители знаний проверяют информацию...</i>",
    ]

    await message.answer(random.choice(waiting_messages), parse_mode=ParseMode.HTML)