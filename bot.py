from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import asyncio

# Подключение к Google Sheets
scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']
creds_dict = json.loads(os.environ['GOOGLE_CREDENTIALS'])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

client = gspread.authorize(creds)
sheet = client.open("Передовик вакансии БОТ").sheet1

def get_data():
    return sheet.get_all_records()

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("АКТУАЛЬНЫЕ ВАКАНСИИ", callback_data="find_jobs")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Я помогу вам подобрать вакансию. Напишите название профессии или посмотрите список открытых вакансий",
        reply_markup=reply_markup
    )

# Вывод вакансий (используется и в /jobs, и в кнопке)
async def show_jobs(update_or_query, context: ContextTypes.DEFAULT_TYPE):
    data = get_data()

    lines = []
    for row in data:
        if row.get('СТАТУС', '').strip().upper() == 'НАБИРАЕМ':
            for line in row['Вакансия'].splitlines():
                lines.append(f"• {line.strip()}")
    text = "\n".join(lines)

    await update_or_query.message.reply_text("Список актуальных вакансий:\n\n" + text)
    await asyncio.sleep(1)
    await update_or_query.message.reply_text("Какая вакансия интересует?")

# Обработка /jobs
async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_jobs(update, context)

# Обработка нажатия кнопки
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await show_jobs(query, context)

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
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.run_polling()
