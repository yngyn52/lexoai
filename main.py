import os
import json
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv
import asyncio
from difflib import SequenceMatcher

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

def calculate_similarity(a, b):
    """Вычисляет степень схожести двух строк"""
    return SequenceMatcher(None, a, b).ratio()

def preprocess_text(text):
    """Предобработка текста для сравнения"""
    return text.lower().strip().replace("?", "").replace(".", "").replace("!", "")

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
    user_question = preprocess_text(message.text)
    
    # Поиск наиболее похожего вопроса
    best_match = None
    best_ratio = 0.4  # снижаем порог схожести для лучшего поиска
    
    # Дополнительная обработка для специфических случаев
    special_cases = {
        "как вернуть деньги за товар": [q for q in qa_base if "вернуть деньги" in q["question"].lower() or "возврат" in q["question"].lower()],
        "как оформить дтп без гибдд": [q for q in qa_base if "дтп" in q["question"].lower() and "гидд" in q["question"].lower()]
    }
    
    # Проверяем специальные случаи
    if user_question in special_cases:
        matches = special_cases[user_question]
        if matches:
            best_match = matches[0]
    
    # Если специальный случай не найден, ищем через алгоритм
    if not best_match:
        for item in qa_base:
            base_question = preprocess_text(item["question"])
            
            # Проверяем степень схожести
            ratio = calculate_similarity(user_question, base_question)
            
            # Если нашли более подходящий вопрос
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = item
    
    # Дополнительная проверка по ключевым словам
    if not best_match:
        keywords = {
            "уволили": [q for q in qa_base if "уволили" in q["question"].lower()],
            "вернуть деньги": [q for q in qa_base if "вернуть деньги" in q["question"].lower() or "возврат" in q["question"].lower()],
            "дтп": [q for q in qa_base if "дтп" in q["question"].lower()],
            "гидд": [q for q in qa_base if "гидд" in q["question"].lower()]
        }
        
        for keyword, matches in keywords.items():
            if keyword in user_question and matches:
                best_match = matches[0]
                break
    
    # Если нашли подходящий вопрос
    if best_match:
        # Формируем ответ
        response = f"⚖️ {best_match['answer']}\n\n"
            
        # Добавляем ссылки на законы, если они есть
        if best_match["law_links"] and len(best_match["law_links"]) > 0:
            response += "🔗 Источник: "
            for i, link in enumerate(best_match["law_links"], 1):
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
