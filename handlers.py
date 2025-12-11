from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.types import (
    Message,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
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
from generate import ai_generate, prompt_content

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

RACES = {1:"Человек",2:"Эльф",3:"Дроу",4:"Гном",5:"Дварф",6:"Драконорожденный",7:"Тифлинг",8:"Полуэльф",9:"Полурослик",10:"Орк",11:"Полуорк",12:"Кобольд",13:"Шейфтер",14:"Людоящер"}
CLASSES = {1:"Воин",2:"Паладин",3:"Плут",4:"Волшебник",5:"Жрец",6:"Бард",7:"Варвар",8:"Друид",9:"Монах",10:"Следопыт",11:"Чародей",12:"Изобретатель"}
BACKGROUNDS = {1:"Народный герой",2:"Благородный",3:"Отшельник",4:"Бродяга",5:"Артист",6:"Аферист",7:"Солдат",8:"Торговец",9:"Писарь",10:"Следопыт",11:"Ремесленник"}

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

def trim_history(history, max_pairs=8):
    limit = max_pairs*2 + 1
    return history[-limit:] if len(history) > limit else history

def make_game_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/статус"), KeyboardButton(text="/инвентарь")],
            [KeyboardButton(text="/заклинания"), KeyboardButton(text="/торговля")],
            [KeyboardButton(text="/отдых")],
        ],
        resize_keyboard=True,
    )

def validate_text_input(text, min_length=3, max_length=500):
    text = text.strip()
    if len(text) < min_length:
        return False,f"❌ Слишком короткий текст. Минимум {min_length} символов."
    if len(text) > max_length:
        return False,f"❌ Слишком длинный текст. Максимум {max_length} символов."
    if re.search(r'[<>{}[\]]', text):
        return False,"❌ Текст содержит недопустимые символы."
    return True,""

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

async def finish_creation(message: Message, state: FSMContext):
    data = await state.get_data()
    stats = data.get("stats",{})
    stats_lines = [f"{k}: {v}" for k,v in stats.items()] if isinstance(stats, dict) else [str(stats)]
    stats_str = "\n".join(stats_lines)

    # Формируем блок CHARACTER
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
        f"День_старта: {data.get('day_counter','1')}\n"
        f"Снаряжение: {data.get('equipment','Базовая экипировка')}\n"
        f"Монеты: {data.get('coins','1d6+1')}\n"
        f"Сумка: {data.get('bag','Пустая сумка')}\n"
        "[/CHARACTER]\n"
    )

    try:
        with open(PROMPT_PATH,"w",encoding="utf-8") as f:
            f.write(character_block + "\n" + prompt_content)
    except Exception as e:
        logger.exception("Не удалось записать prompt.txt: %s", e)
        await message.answer("⚠️ Ошибка при сохранении prompt.txt.", parse_mode=ParseMode.HTML)
        await state.set_state(Gen.history)
        return

    # Формируем словарь для сцены
    char_data_for_scene = {
        "name": data.get("name",""),
        "class": data.get("char_class",""),
        "race": data.get("race",""),
        "background": data.get("background",""),
        "str": stats.get("Сила",0),
        "dex": stats.get("Ловкость",0),
        "con": stats.get("Телосложение",0),
        "int": stats.get("Интеллект",0),
        "wis": stats.get("Мудрость",0),
        "cha": stats.get("Харизма",0),
        "armor": data.get("equipment","Базовая экипировка"),
        "weapon": "Основное оружие",
        "coins": data.get("coins","0")
    }

    # Загружаем шаблон начальной сцены
    try:
        with open(START_SCENE_PATH,"r",encoding="utf-8") as f:
            template = f.read()
    except Exception:
        # Если файла нет, используем дефолтный текст
        template = "{scene_text}"

    first_scene_text = "Вы стоите на пыльной дороге у трактира «Последний привал». В воздухе пахнет дымом и жареным кабаном. Из дверей доносится хриплый смех."

    # Формируем текст сцены
    start_scene = template.format(
        char_name=char_data_for_scene["name"],
        char_class=char_data_for_scene["class"],
        char_race=char_data_for_scene["race"],
        char_background=char_data_for_scene["background"],
        str=char_data_for_scene["str"],
        dex=char_data_for_scene["dex"],
        con=char_data_for_scene["con"],
        int=char_data_for_scene["int"],
        wis=char_data_for_scene["wis"],
        cha=char_data_for_scene["cha"],
        armor=char_data_for_scene["armor"],
        weapon=char_data_for_scene["weapon"],
        coins=char_data_for_scene["coins"],
        scene_text=first_scene_text
    )

    await message.answer("✨ Персонаж создан! Начало приключения:", parse_mode=ParseMode.HTML)
    await message.answer(start_scene, parse_mode=ParseMode.HTML, reply_markup=make_game_keyboard())

    history = [{"role":"assistant","content":start_scene}]
    await state.update_data(history=history)
    await state.set_state(Gen.history)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🎲 Начать приключение", callback_data="start_game")]]
    )

    await message.answer(
        "⚔️ <b>Добро пожаловать в игру Dungeons and dragons!</b> ⚔️\n\n"
        "Осмелишься ли ты сделать первый шаг?",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML,
    )

@router.callback_query(F.data == "start_game")
async def start_game_callback(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()

    text = "🛡️ <b>Создание персонажа — шаг 1</b>\n"
    text += "<i>Выберите расу:</i>\n\n"
    for num, race in RACES.items():
        text += f"  {num}. {race}\n"  # отступ для списка
    text += "\n<i>Введите номер выбранной расы:</i>"

    await callback.message.edit_text(text, parse_mode=ParseMode.HTML)
    await state.set_state(CreateChar.race)

@router.message(CreateChar.race)
async def set_race(message: Message, state: FSMContext):
    try:
        num = int(message.text.strip())
        race = RACES[num]
    except Exception:
        return await message.answer("❗ Пожалуйста, введите только номер расы присутствующий в списке.")

    await state.update_data(race=race)
    await state.set_state(CreateChar.name)
    await message.answer("✏️ <b>Создание персонажа — шаг 2:</b>\n<i>Введите имя персонажа:</i>\n\n", parse_mode=ParseMode.HTML)

@router.message(CreateChar.name)
async def set_name(message: Message, state: FSMContext):
    name = message.text.strip()
    
    is_valid, error_msg = validate_text_input(name, min_length=2, max_length=50)
    if not is_valid:
        return await message.answer(error_msg)
    
    await state.update_data(name=name)
    text = "⚔️ <b>Создание персонажа — шаг 3</b>\n"
    text += "<i>Выберите класс:</i>\n\n"
    for num, cl in CLASSES.items():
        text += f"  {num}. {cl}\n"
    text += "\n<i>Введите номер выбранного класса:</i>"
    await message.answer(text, parse_mode=ParseMode.HTML)
    await state.set_state(CreateChar.char_class)

@router.message(CreateChar.char_class)
async def set_class(message: Message, state: FSMContext):
    try:
        cl = CLASSES[int(message.text.strip())]
    except Exception:
        return await message.answer("❗ Введи номер класса (например: 1).")

    await state.update_data(char_class=cl)
    text = "📖 <b>Создание персонажа — шаг 4</b>\n"
    text += "<i>Выберите предысторию:</i>\n\n"
    for num, bg in BACKGROUNDS.items():
        text += f"  {num}. {bg}\n"
    text += "\n<i>Введите номер выбранной предыстории:</i>"
    await message.answer(text, parse_mode=ParseMode.HTML)
    await state.set_state(CreateChar.background)

@router.message(CreateChar.background)
async def set_background(message: Message, state: FSMContext):
    try:
        bg = BACKGROUNDS[int(message.text.strip())]
    except Exception:
        return await message.answer("❗ Введи номер предыстории.")

    await state.update_data(background=bg)
    stats_dict, stats_report = generate_stats_auto()
    await state.update_data(stats=stats_dict)
    await state.update_data(stats_report=stats_report)

    await message.answer(
        "🎲 <b>Создание персонажа — шаг 5</b>\n\n"
        "<b>Характеристики:</b>\n" +
        "\n".join([f"  {line}" for line in stats_report.split("\n")]) +
        "\n\n<i>Применить бонусы расы автоматически? (да/нет)</i>",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(CreateChar.apply_bonuses)

@router.message(CreateChar.apply_bonuses)
async def set_bonuses(message: Message, state: FSMContext):
    answer = message.text.strip().lower()
    if answer not in ("да", "нет"):
        return await message.answer("Ответь 'да' или 'нет'.")

    await state.update_data(apply_bonuses=answer)
    await message.answer(
        "🧠 <b>Шаг 6: Опишите характер персонажа</b>\n"
        "<i>Опишите основные черты характера, мотивации, страхи и т.д.</i>",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(CreateChar.personality)

@router.message(CreateChar.personality)
async def set_personality(message: Message, state: FSMContext):
    personality = message.text.strip()
    
    is_valid, error_msg = validate_text_input(personality, min_length=10, max_length=1000)
    if not is_valid:
        return await message.answer(error_msg)
    
    await state.update_data(personality=personality)
    await message.answer(
        "🎨 <b>Шаг 7: Опишите внешность персонажа</b>\n"
        "<i>Опишите внешние черты, одежду, отличительные особенности.</i>",
        parse_mode=ParseMode.HTML
    )
    await state.set_state(CreateChar.appearance)

@router.message(CreateChar.appearance)
async def set_appearance(message: Message, state: FSMContext):
    appearance = message.text.strip()
    
    is_valid, error_msg = validate_text_input(appearance, min_length=10, max_length=1000)
    if not is_valid:
        return await message.answer(error_msg)
    
    await state.update_data(appearance=appearance)
    
    await state.update_data(
        day_counter=1,
        equipment="Базовая экипировка по классу + 1 случайный предмет",
        coins="1d6+1",
        bag="Пустая сумка"
    )
    
    await finish_creation(message, state)

async def finish_creation(message: Message, state: FSMContext):
    data = await state.get_data()

    stats = data.get("stats", {})
    if isinstance(stats, dict):
        stats_lines = [f"{k}: {v}" for k, v in stats.items()]
        stats_str = "\n".join(stats_lines)
    else:
        stats_str = str(stats)

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
        f"День_старта: {data.get('day_counter','1')}\n"
        f"Снаряжение: {data.get('equipment','Базовая экипировка по классу + 1 случайный предмет')}\n"
        f"Монеты: {data.get('coins','1d6+1')}\n"
        f"Сумка: {data.get('bag','Пустая сумка')}\n"
        "[/CHARACTER]\n"
    )

    try:
        with open(PROMPT_PATH, "w", encoding="utf-8") as f:
            f.write(character_block + "\n" + prompt_content)
    except Exception as e:
        logger.exception("Не удалось записать prompt.txt: %s", e)
        await message.answer("⚠️ Ошибка при сохранении prompt.txt. Проверь права записи на папку.", parse_mode=ParseMode.HTML)
        await state.set_state(Gen.history)
        return

    await message.answer("✨ Персонаж создан и сохранён в prompt.txt. Формирую начало приключения...", parse_mode=ParseMode.HTML)

    history = [{"role": "user", "content": character_block + "\n" + prompt_content}]
    history = trim_history(history, max_pairs=8)

    raw = await safe_ai_generate(history, state, Gen.history)
    response_text = raw if raw else "⚠️ Пустой ответ от сервера."

    response_text = response_text.replace("\n", "\n\n")

    keyboard = make_game_keyboard()
    await message.answer(response_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    history.append({"role": "assistant", "content": response_text})
    await state.update_data(history=history)
    await state.set_state(Gen.history)

@router.message(Gen.history)
async def continue_dialog(message: Message, state: FSMContext):
    data = await state.get_data()
    history = data.get("history", [])

    history.append({"role": "user", "content": message.text})
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
    response = response.replace("\n", "\n\n")

    await message.answer(response, parse_mode=ParseMode.HTML)

    history.append({"role": "assistant", "content": response})
    history = trim_history(history, max_pairs=10)
    await state.update_data(history=history)
    await state.set_state(Gen.history)

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