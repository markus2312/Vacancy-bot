from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import asyncio  # Для использования асинхронной задержки

# Подключение к Google Sheets
scope = ["https://spreadsheets.google.com/feeds",'https://www.googleapis.com/auth/drive']

creds_dict = json.loads(os.environ['GOOGLE_CREDENTIALS'])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

client = gspread.authorize(creds)
sheet = client.open("Передовик вакансии БОТ").sheet1  # замени на точное название

def get_data():
    return sheet.get_all_records()

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Создаем кнопку
    keyboard = [
        [InlineKeyboardButton("Найти вакансии", callback_data="find_jobs")]  # Кнопка "Найти вакансии"
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Отправляем приветственное сообщение
    await update.message.reply_text(
        "Привет! Я — твой персональный помощник по подбору вакансий.\n\n"
        "Здесь ты сможешь быстро найти актуальные вакансии, узнать подробности и выбрать подходящее предложение.\n\n"
        "Нажми на кнопку 👇 и начни свой поиск!",
        reply_markup=reply_markup
    )

# Команда /jobs
async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_data()
    
    lines = []  # Здесь создаем пустой список для вакансий
    for row in data:
        if row.get('СТАТУС', '').strip().upper() == 'НАБИРАЕМ':  # Проверяем статус вакансии
            for line in row['Вакансия'].splitlines():  # Разбиваем по строкам
                lines.append(f"• {line.strip()}")  # Добавляем каждую строку с маркером
    text = "\n".join(lines)  # Объединяем все вакансии в одну строку

    # Отправляем список вакансий с отступом
    await update.message.reply_text("Список актуальных вакансий:\n\n" + text)
    
    # Задержка в 1 секунду перед следующим сообщением
    await asyncio.sleep(1)
    
    # Следующее сообщение
    await update.message.reply_text("Какая вакансия интересует?")

# Ответ на сообщения
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    data = get_data()

    for row in data:
        if row['Вакансия'].lower() in text:
            response = f"""
🔧 *{row['Вакансия']}*
📈 Часовая ставка: {row['Часовая ставка']}
🕐 Вахта 30/30: {row['Вахта по 12 часов (30/30)']}
🕑 Вахта 60/30: {row['Вахта по 11 ч (60/30)']}
📌 Статус: {row.get('СТАТУС', 'не указан')}
"""
            await update.message.reply_markdown(response)
            return

    await update.message.reply_text("Не нашёл вакансию по вашему запросу. Попробуйте написать её полнее.")

# Запуск бота
app = ApplicationBuilder().token("7868075757:AAER7ENuM0L6WT_W5ZB0iRrVRUw8WeijbOo").build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("jobs", jobs))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.run_polling()
