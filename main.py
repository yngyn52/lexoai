import os
import json
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardRemove
from dotenv import load_dotenv
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
import io
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загружаем базу знаний
try:
    with open("data/qa_base.json", "r", encoding="utf-8") as f:
        qa_base = json.load(f)
    logger.info(f"Загружено {len(qa_base)} вопросов в базу знаний")
except Exception as e:
    logger.error(f"Ошибка при загрузке базы знаний: {e}")
    qa_base = []

# Определение состояний для FSM
class DocumentForm(StatesGroup):
    choosing_document_type = State()
    entering_complaint_info = State()
    entering_lawsuit_info = State()
    entering_lease_agreement_info = State()
    confirming_document = State()

# Шаблоны документов
DOCUMENT_TEMPLATES = {
    "Претензия на возврат товара": {
        "prompt": "Создай претензию на возврат товара по ст. 18 ЗоЗПП РФ. "
                  "Включи реквизиты: ФИО потребителя, адрес, дата покупки, "
                  "наименование товара, описание проблемы, требование о возврате средств.",
        "required_fields": ["ФИО", "адрес", "дата покупки", "наименование товара", "описание проблемы"]
    },
    "Исковое заявление об увольнении": {
        "prompt": "Создай исковое заявление об восстановлении на работе по ст. 81 ТК РФ. "
                  "Включи реквизиты: ФИО истца, адрес, наименование ответчика, "
                  "дата увольнения, обстоятельства, доказательства, требование о восстановлении.",
        "required_fields": ["ФИО", "адрес", "наименование работодателя", "дата увольнения", "обстоятельства"]
    },
    "Договор аренды квартиры": {
        "prompt": "Создай договор аренды квартиры по ст. 671 ГК РФ. "
                  "Включи реквизиты: ФИО арендодателя, ФИО арендатора, адрес квартиры, "
                  "срок аренды, размер арендной платы, порядок оплаты, права и обязанности сторон.",
        "required_fields": ["ФИО арендодателя", "ФИО арендатора", "адрес квартиры", "срок аренды", "размер арендной платы"]
    }
}

load_dotenv()
bot = Bot(token=os.getenv("BOT_TOKEN"))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

def preprocess_text(text):
    """Предобработка текста для сравнения"""
    return text.lower().strip().replace("?", "").replace(".", "").replace("!", "")

def calculate_similarity(a, b):
    """Вычисляет степень схожести двух строк"""
    from difflib import SequenceMatcher
    return SequenceMatcher(None, a, b).ratio()

def generate_legal_document(doc_type, context):
    """
    Заглушка для генерации юридического документа через YaLM API.
    В реальной реализации здесь будет вызов API.
    """
    logger.info(f"Генерация документа: {doc_type} с контекстом: {context}")
    
    # Пример сгенерированного документа для демонстрации
    templates = {
        "Претензия на возврат товара": f"""
ПРЕТЕНЗИЯ
о возврате денежных средств за некачественный товар

г. Москва
{context.get('дата', 'Дата')}

В магазин "{context.get('магазин', 'Название магазина')}"

Я, {context.get('ФИО', 'ФИО потребителя')}, проживающий(ая) по адресу: {context.get('адрес', 'Адрес')},
2 {context.get('дата покупки', 'дата')} приобрел(а) в Вашем магазине товар: "{context.get('наименование товара', 'Наименование товара')}".

В процессе эксплуатации обнаружил(а) следующие недостатки: {context.get('описание проблемы', 'Описание проблемы')}.

На основании ст. 18 Закона РФ "О защите прав потребителей" требую:
1. Возврата уплаченной за товар денежной суммы в размере {context.get('сумма', 'Сумма')} рублей.
2. Выплаты неустойки в размере 1% от стоимости товара за каждый день просрочки.

В случае отказа или игнорирования настоящей претензии буду вынужден(а) обратиться в суд 
с требованием о взыскании денежных средств, неустойки, компенсации морального вреда и штрафа.

Приложение:
1. Копия чека/товарного чека
2. Копия гарантийного талона (при наличии)

С уважением,
{context.get('ФИО', 'ФИО потребителя')}
{context.get('контактный телефон', 'Контактный телефон')}
        """,
        "Исковое заявление об увольнении": f"""
В {context.get('суд', 'Наименование суда')}

Истец: {context.get('ФИО', 'ФИО истца')}
Адрес: {context.get('адрес', 'Адрес истца')}
Телефон: {context.get('телефон', 'Телефон истца')}

Ответчик: {context.get('наименование работодателя', 'Наименование работодателя')}
Адрес: {context.get('адрес работодателя', 'Адрес работодателя')}

ИСКОВОЕ ЗАЯВЛЕНИЕ
о восстановлении на работе и взыскании заработной платы

{context.get('дата увольнения', 'Дата')} меня, {context.get('ФИО', 'ФИО истца')}, был уволен(а) {context.get('должность', 'Должность')} {context.get('наименование работодателя', 'Наименование работодателя')} по п. {context.get('основание увольнения', 'Основание')} ст. 81 ТК РФ.

Увольнение произведено незаконно, так как: {context.get('обстоятельства', 'Обстоятельства')}

На основании изложенного, руководствуясь ст. 81 ТК РФ, ст. 392 ТК РФ, ст. 237 ТК РФ,
прошу суд:
1. Признать увольнение незаконным и восстановить меня на работе.
2. Взыскать с ответчика заработную плату за время вынужденного прогула в размере {context.get('сумма', 'Сумма')} рублей.
3. Взыскать компенсацию морального вреда в размере {context.get('сумма морального вреда', 'Сумма')} рублей.

Приложения:
1. Копия трудовой книжки
2. Копия приказа об увольнении
3. Расчет среднего заработка
4. Другие доказательства

Дата: {context.get('дата', 'Дата')}
Подпись: _________________
        """,
        "Договор аренды квартиры": f"""
ДОГОВОР АРЕНДЫ КВАРТИРЫ
№ {context.get('номер договора', 'Номер')} от {context.get('дата', 'Дата')}

г. {context.get('город', 'Город')}

Арендодатель: {context.get('ФИО арендодателя', 'ФИО арендодателя')}, паспорт: {context.get('паспорт арендодателя', 'Паспортные данные')}, 
адрес регистрации: {context.get('адрес регистрации арендодателя', 'Адрес регистрации')}

Арендатор: {context.get('ФИО арендатора', 'ФИО арендатора')}, паспорт: {context.get('паспорт арендатора', 'Паспортные данные')}, 
адрес регистрации: {context.get('адрес регистрации арендатора', 'Адрес регистрации')}

1. Предмет договора
Арендодатель предоставляет Арендатору во временное пользование квартиру, расположенную по адресу: 
{context.get('адрес квартиры', 'Адрес квартиры')}

2. Срок аренды
Настоящий договор заключен на срок {context.get('срок аренды', 'Срок аренды')} с {context.get('дата начала', 'Дата начала')} по {context.get('дата окончания', 'Дата окончания')}.

3. Размер и порядок оплаты
Размер арендной платы составляет {context.get('размер арендной платы', 'Размер')} рублей в месяц.
Оплата вносится не позднее {context.get('срок оплаты', 'Срок оплаты')} числа каждого месяца.

4. Права и обязанности сторон
[Подробные условия договора]

5. Заключительные положения
[Заключительные положения]

Договор составлен в двух экземплярах, имеющих одинаковую юридическую силу.

Арендодатель: _________________
Арендатор: _________________
        """
    }
    
    return templates.get(doc_type, "Документ не найден")

def create_pdf(document_text, doc_type):
    """Создает PDF файл из текста документа"""
    try:
        buffer = io.BytesIO()
        
        # Создаем PDF документ
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=40,
            leftMargin=40,
            topMargin=40,
            bottomMargin=40
        )
        
        # Стили для документа
        styles = getSampleStyleSheet()
        title_style = styles["Heading1"]
        title_style.fontSize = 16
        title_style.alignment = 1  # Центрирование
        
        normal_style = styles["BodyText"]
        normal_style.fontSize = 12
        normal_style.leading = 15
        
        # Разделяем текст на строки и создаем элементы
        elements = []
        
        # Добавляем название документа
        title = Paragraph(f"{doc_type}", title_style)
        elements.append(title)
        elements.append(Spacer(1, 20))
        
        # Добавляем содержимое документа
        lines = document_text.strip().split('\n')
        for line in lines:
            if line.strip():
                # Если строка содержит двоеточие и выглядит как реквизит, делаем ее жирной
                if any(keyword in line.lower() for keyword in ['г.', 'требую', 'прошу', 'адрес', 'ф.и.о', 'паспорт', 'дата']):
                    p_style = styles["Heading3"]
                    p_style.fontSize = 12
                else:
                    p_style = normal_style
                elements.append(Paragraph(line, p_style))
                elements.append(Spacer(1, 5))
        
        # Добавляем подпись
        elements.append(Spacer(1, 30))
        signature = Paragraph("С уважением,<br/>_________________<br/>Дата: _________________", normal_style)
        elements.append(signature)
        
        # Собираем документ
        doc.build(elements)
        
        # Перематываем буфер к началу
        buffer.seek(0)
        return buffer
    
    except Exception as e:
        logger.error(f"Ошибка при создании PDF: {e}")
        return None

@dp.message(Command("start"))
async def start(message: types.Message, state: FSMContext):
    await state.clear()
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

@dp.message(Command("document"))
async def document_start(message: types.Message, state: FSMContext):
    # Сбрасываем состояние
    await state.clear()
    
    # Показываем клавиатуру с типами документов
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Претензия на возврат товара")],
            [types.KeyboardButton(text="Исковое заявление об увольнении")],
            [types.KeyboardButton(text="Договор аренды квартиры")]
        ],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    
    await message.answer(
        "Выберите тип документа, который хотите создать:",
        reply_markup=keyboard
    )
    await state.set_state(DocumentForm.choosing_document_type)

@dp.message(DocumentForm.choosing_document_type)
async def process_document_type(message: types.Message, state: FSMContext):
    doc_type = message.text
    
    # Проверяем, поддерживается ли выбранный тип документа
    if doc_type not in DOCUMENT_TEMPLATES:
        await message.answer(
            "К сожалению, я не поддерживаю создание этого типа документа.\n"
            "Пожалуйста, выберите один из предложенных вариантов.",
            reply_markup=types.ReplyKeyboardRemove()
        )
        return
    
    # Сохраняем тип документа
    await state.update_data(document_type=doc_type)
    
    # Получаем обязательные поля
    required_fields = DOCUMENT_TEMPLATES[doc_type]["required_fields"]
    
    # Сохраняем информацию о текущем поле
    await state.update_data(current_field_index=0)
    await state.update_data(required_fields=required_fields)
    
    # Запрашиваем первое поле
    await message.answer(
        f"Отлично! Будем создавать: {doc_type}\n\n"
        f"Пожалуйста, укажите {required_fields[0]}:",
        reply_markup=types.ReplyKeyboardRemove()
    )
    
    await state.set_state(DocumentForm.entering_complaint_info)

@dp.message(DocumentForm.entering_complaint_info)
@dp.message(DocumentForm.entering_lawsuit_info)
@dp.message(DocumentForm.entering_lease_agreement_info)
async def process_document_info(message: types.Message, state: FSMContext):
    # Получаем текущее состояние
    user_data = await state.get_data()
    doc_type = user_data["document_type"]
    required_fields = user_data["required_fields"]
    current_index = user_data.get("current_field_index", 0)
    
    # Сохраняем введенное значение
    field_name = required_fields[current_index]
    await state.update_data({field_name: message.text})
    
    # Переходим к следующему полю
    current_index += 1
    
    # Проверяем, есть ли еще поля для заполнения
    if current_index < len(required_fields):
        await state.update_data(current_field_index=current_index)
        await message.answer(f"Теперь укажите {required_fields[current_index]}:")
    else:
        # Все поля заполнены, показываем подтверждение
        user_data = await state.get_data()
        
        # Формируем текст подтверждения
        confirmation_text = f"Проверьте введенные данные для {doc_type}:\n\n"
        for field in required_fields:
            confirmation_text += f"{field}: {user_data.get(field, 'Не указано')}\n"
        
        # Добавляем дополнительные поля, если они есть
        if "дата" not in required_fields:
            user_data["дата"] = message.date.strftime("%d.%m.%Y")
        
        # Сохраняем обновленные данные
        await state.update_data(user_data)
        
        # Клавиатура подтверждения
        keyboard = types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="Да, все верно")],
                [types.KeyboardButton(text="Нет, ввести заново")]
            ],
            resize_keyboard=True,
            one_time_keyboard=True
        )
        
        await message.answer(
            confirmation_text + "\n\nВсе верно?",
            reply_markup=keyboard
        )
        await state.set_state(DocumentForm.confirming_document)

@dp.message(DocumentForm.confirming_document, F.text == "Да, все верно")
async def confirm_document(message: types.Message, state: FSMContext):
    # Получаем данные
    user_data = await state.get_data()
    doc_type = user_data["document_type"]
    
    # Генерируем документ
    document_text = generate_legal_document(doc_type, user_data)
    
    # Создаем PDF
    pdf_buffer = create_pdf(document_text, doc_type)
    
    if pdf_buffer:
        # Отправляем PDF
        pdf_file = types.BufferedInputFile(
            pdf_buffer.getvalue(),
            filename=f"{doc_type.replace(' ', '_')}.pdf"
        )
        
        await message.answer_document(
            pdf_file,
            caption="Ваш юридический документ готов!\n\n"
                    "Вы можете скачать его и использовать по назначению."
        )
        
        # Отправляем текст документа
        await message.answer(
            "Текст документа:\n\n" + document_text[:3000] + "..."
            if len(document_text) > 3000 else document_text
        )
    else:
        await message.answer(
            "Произошла ошибка при создании PDF. Отправляю текст документа:\n\n" + document_text
        )
    
    # Сбрасываем состояние
    await state.clear()
    
    # Предлагаем создать еще документ
    keyboard = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="Создать еще документ")],
            [types.KeyboardButton(text="Задать юридический вопрос")]
        ],
        resize_keyboard=True
    )
    
    await message.answer(
        "Документ успешно сгенерирован!\n\n"
        "Что вы хотите сделать дальше?",
        reply_markup=keyboard
    )

@dp.message(DocumentForm.confirming_document, F.text == "Нет, ввести заново")
async def restart_document(message: types.Message, state: FSMContext):
    # Сбрасываем состояние и начинаем заново
    user_data = await state.get_data()
    doc_type = user_data["document_type"]
    
    # Получаем обязательные поля
    required_fields = DOCUMENT_TEMPLATES[doc_type]["required_fields"]
    
    # Обновляем состояние
    await state.update_data(current_field_index=0)
    await state.update_data(required_fields=required_fields)
    
    await message.answer(
        f"Хорошо, начнем заново.\n\n"
        f"Пожалуйста, укажите {required_fields[0]}:",
        reply_markup=types.ReplyKeyboardRemove()
    )
    await state.set_state(DocumentForm.entering_complaint_info)

@dp.message()
async def handle_question(message: types.Message):
    # Предобработка текста
    user_question = preprocess_text(message.text)
    
    # Поиск наиболее похожего вопроса
    best_match = None
    best_ratio = 0.4  # снижаем порог схожести для лучшего поиска
    
    # Поиск по основным вопросам и синонимам
    for item in qa_base:
        # Проверяем основной вопрос
        base_question = preprocess_text(item["question"])
        ratio = calculate_similarity(user_question, base_question)
        
        # Проверяем синонимы, если они есть
        if "synonyms" in item:
            for synonym in item["synonyms"]:
                synonym_processed = preprocess_text(synonym)
                synonym_ratio = calculate_similarity(user_question, synonym_processed)
                if synonym_ratio > ratio:
                    ratio = synonym_ratio
        
        # Если нашли более подходящий вопрос
        if ratio > best_ratio:
            best_ratio = ratio
            best_match = item
    
    # Дополнительная проверка по ключевым словам
    if not best_match:
        keywords = {
            "уволили": [q for q in qa_base if "уволили" in preprocess_text(q["question"])],
            "вернуть деньги": [q for q in qa_base if "вернуть деньги" in preprocess_text(q["question"]) or "возврат" in preprocess_text(q["question"])],
            "дтп": [q for q in qa_base if "дтп" in preprocess_text(q["question"])],
            "гидд": [q for q in qa_base if "гидд" in preprocess_text(q["question"])]
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
                response += f"\n{i}. {link.strip()}"
        
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
    logger.info("Запуск бота...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
