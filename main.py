import os
import json
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv
import asyncio

# Загружаем базу знаний
try:
    with open("data/qa_base.json", "r", encoding="utf-8") as f:
        qa_base = json.load(f)
    print(f"Загружено {len(qa_base)} вопросов в базу знаний")
except Exception as e:
    print(f"Ошибка при загрузке базы знаний: {e}")
    qa_base = []

load_dotenv()
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "⚖️ Привет! Я LexoAI — ваш юридический ассистент.\n"
        "Что вас интересует?\n"
        "1. /chat — Задать вопрос\n"
        "2. /document — Создать документ"
    )

@dp.message(Command("help"))
async def help(message: types.Message):
    await message.answer(
        "Как пользоваться:\n"
        "- Пишите вопросы естественным языком («Меня уволили без причины»)\n"
        "- Используйте /document для генерации претензий\n"
        "- Загружайте договоры через /analyze"
    )

@dp.message(Command("chat"))
async def handle_chat(message: types.Message):
    # Показываем клавиатуру с примерами вопросов
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Меня уволили без причины")],
            [types.KeyboardButton(text="Как вернуть деньги за товар")],
            [types.KeyboardButton(text="Как оформить ДТП без ГИБДД")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "Введите ваш юридический вопрос или выберите из примеров:",
        reply_markup=keyboard
    )

@dp.message()
async def handle_question(message: types.Message):
    # Предобработка текста
    user_question = message.text.lower().strip().replace("?", "").replace(".", "").replace("!", "")
    
    # Поиск по частичному совпадению
    for item in qa_base:
        # Убираем знаки препинания из вопроса из базы
        base_question = item["question"].lower().replace("?", "").replace(".", "").replace("!", "")
        
        # Проверяем, содержится ли текст пользователя в вопросе из базы
        if user_question in base_question or base_question in user_question:
            # Формируем ответ
            response = f"⚖️ {item['answer']}\n\n"
            
            # Добавляем ссылки на законы, если они есть
            if item["law_links"] and len(item["law_links"]) > 0:
                response += "🔗 Источник: "
                for i, link in enumerate(item["law_links"], 1):
                    response += f"\n{i}. {link}"
            
            await message.answer(
                response,
                reply_markup=types.ReplyKeyboardRemove()
            )
            return
    
    # Если вопрос не найден
    await message.answer(
        "К сожалению, я не нашел точного ответа в базе знаний.\n"
        "Попробуйте уточнить вопрос или задайте другой.\n\n"
        "Или воспользуйтесь /document для создания документа.",
        reply_markup=types.ReplyKeyboardRemove()
    )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
