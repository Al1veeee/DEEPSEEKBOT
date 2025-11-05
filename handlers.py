from aiogram import Router, F, types
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from aiogram.enums import ParseMode
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import sys
import os
import random

sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from generate import ai_generate, prompt_content

router = Router()


class Gen(StatesGroup):
    wait = State()
    history = State()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    """Приветствие и inline-кнопка запуска"""
    await state.clear()

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎲 Начать приключение", callback_data="start_game")]
        ]
    )

    await message.answer(
        "⚔️ <b>Добро пожаловать в Таинственные Земли!</b> ⚔️\n\n"
        "🛡️ <i>Храбрец, ты стоишь на пороге великих свершений...</i>\n"
        "📜 <i>Древние свитки предсказывают твое прибытие</i>\n"
        "🔮 <i>Магия витает в воздухе, готовясь к твоим деяниям</i>\n\n"
        "Осмелься ли ты сделать первый шаг?",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )


@router.callback_query(F.data == "start_game")
async def start_game_callback(callback: types.CallbackQuery, state: FSMContext):
    """Первый запуск — обращение к AI с prompt.txt"""
    await state.set_state(Gen.history)
    
    loading_messages = [
        "🔮 <i>Магический кристалл наполняется сиянием...</i>",
        "🌌 <i>Звезды сходятся в благоприятном положении...</i>",
        "📜 <i>Свитки древних пророчеств раскрываются</i>",
        "⚡ <i>Энергия магии наполняет пространство...</i>",
        "🐉 <i>Мудрый дракон пробуждается от векового сна...</i>",
        "🔍 <i>Карта судьбы проявляет новые пути</i>",
        "✨ <i>Чары начинают действовать...</i>",
        "🏰 <i>Врата в забытые королевства открываются...</i>",
        "🗝️ <i>Ключи от тайн обретают силу</i>",
        "🌠 <i>Млечный путь указывает направление...</i>",
        "🌙 <i>Луна наполняется магической силой...</i>",
        "🔥 <i>Огонь знаний разгорается ярче</i>",
        "💧 <i>Воды ясновидения очищаются...</i>"
    ]
    
    await callback.message.edit_text(
        random.choice(loading_messages),
        parse_mode=ParseMode.HTML
    )

    history = [{"role": "user", "content": prompt_content}]
    response = await ai_generate(history)
    response = response.replace("\n", "\n\n")

    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/начать")],
            [KeyboardButton(text="/статус"), KeyboardButton(text="/инвентарь")],
            [KeyboardButton(text="/заклинания"), KeyboardButton(text="/торговля")],
            [KeyboardButton(text="/отдых"), KeyboardButton(text="/форматирование")]
        ],
        resize_keyboard=True
    )

    await callback.message.answer(response, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    history.append({"role": "assistant", "content": response})
    await state.update_data(history=history)
    await callback.answer()

@router.message(F.text == "/форматирование")
async def format_reminder(message: Message, state: FSMContext):
    """Отправляем напоминание о форматировании в историю диалога с AI"""
    data = await state.get_data()
    history = data.get("history", [])
    
    format_instruction = (
        "НАПОМИНАНИЕ О ФОРМАТИРОВАНИИ: "
        "Используй правильное форматирование для Telegram: "
        "между абзацами только одна пустая строка, "
        "не добавляй лишние переносы, "
        "используй HTML-теги (<b>жирный</b>, <i>курсив</i>), "
        "добавляй эмодзи для визуальных акцентов. "
        "Текст должен быть готов к отправке с parse_mode=HTML."
    )
    
    history.append({"role": "user", "content": format_instruction})
    
    await message.answer(
        "📝 <i>Напоминание о форматировании отправлено Мастеру...</i>",
        parse_mode=ParseMode.HTML
    )
    
    response = await ai_generate(history)
    response = response.replace("\n", "\n\n")
    
    await message.answer(response, parse_mode=ParseMode.HTML)
    
    history.append({"role": "assistant", "content": response})
    await state.update_data(history=history)

@router.message(Gen.history)
async def continue_dialog(message: Message, state: FSMContext):
    """Диалог с сохранением контекста"""
    data = await state.get_data()
    history = data.get("history", [])

    history.append({"role": "user", "content": message.text})
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
        "🌟 <i>Призываю силу древних артефактов...</i>"
    ]
    
    await message.answer(
        random.choice(thinking_messages),
        parse_mode=ParseMode.HTML
    )

    response = await ai_generate(history)
    response = response.replace("\n", "\n\n")

    await message.answer(response, parse_mode=ParseMode.HTML)

    history.append({"role": "assistant", "content": response})
    await state.update_data(history=history)
    await state.set_state(Gen.history)


@router.message(Gen.wait)
async def stop_flood(message: Message):
    """Если пользователь пишет во время генерации"""
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
        "🛡️ <i>Хранители знаний проверяют информацию...</i>"
    ]
    
    await message.answer(
        random.choice(waiting_messages),
        parse_mode=ParseMode.HTML
    )