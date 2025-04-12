import os
import json
import re
import asyncio
import difflib
import gspread
import threading
from datetime import datetime
from flask import Flask
from oauth2client.service_account import ServiceAccountCredentials
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# --- Flask сервер для Railway ---
app_flask = Flask(__name__)

@app_flask.route('/')
def index():
    return '✅ Бот работает и не спит!'

# --- Google Sheets ---
scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']
creds_dict = json.loads(os.environ['GOOGLE_CREDENTIALS'])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

def get_data():
    sheet = client.open("Передовик вакансии БОТ").sheet1
    return sheet.get_all_records()

def save_application_to_sheet(name, phone, vacancy, username):
    sheet = client.open_by_key("10TcAZPunK079FBN1gNQIU4XmInMEQ8Qz4CWeA6oDGvI")
    worksheet = sheet.worksheet("bot otkliki")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    worksheet.append_row([now, name, phone, vacancy, f"@{username}" if username else "без username"],
                         value_input_option="USER_ENTERED")

# --- Telegram логика ---
STATE_WAITING_FOR_FIO = 1
STATE_WAITING_FOR_PHONE = 2

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("АКТУАЛЬНЫЕ ВАКАНСИИ", callback_data="find_jobs")]]
    await update.message.reply_text(
        "Я помогу вам подобрать вакансию. Напишите название профессии или посмотрите список открытых вакансий",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_data()
    lines = [f"• {line.strip()}"
             for row in data if row.get('СТАТУС', '').strip().upper() == 'НАБИРАЕМ'
             for line in row['Вакансия'].splitlines()]
    text = "\n".join(lines)

    if update.message:
        await update.message.reply_text("Список актуальных вакансий:\n\n" + text)
        await asyncio.sleep(1)
        await update.message.reply_text("Какая вакансия интересует?")
    elif update.callback_query:
        await update.callback_query.message.reply_text("Список актуальных вакансий:\n\n" + text)
        await asyncio.sleep(1)
        await update.callback_query.message.reply_text("Какая вакансия интересует?")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    if update.callback_query.data == "find_jobs":
        await jobs(update, context)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    data = get_data()
    matches = []

    for row in data:
        for line in row['Вакансия'].splitlines():
            if text in line.lower() or difflib.get_close_matches(text, [line.lower()], cutoff=0.6):
                matches.append(row)
                break

    if matches:
        context.user_data['vacancy_matches'] = matches
        for i, row in enumerate(matches):
            description = row.get('Описание', '').strip()
            description_text = f"\n\n📃 Описание вакансии:\n\n{description}" if description else ""
            response = f"""
🔧 *{row['Вакансия']}*

📈 Часовая ставка: {row['Часовая ставка']}
🕐 Вахта 30/30 по 12ч: {row['Вахта по 12 часов (30/30)']}
🕑 Вахта 60/30 по 11ч: {row['Вахта по 11 ч (60/30)']}
📌 Статус: {row.get('СТАТУС', 'не указан')}{description_text}
"""
            keyboard = [
                [InlineKeyboardButton("ОТКЛИКНУТЬСЯ", callback_data=f"apply_{i}"),
                 InlineKeyboardButton("НАЗАД", callback_data="back")]
            ]
            await update.message.reply_markdown(response, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text("Не нашёл вакансию. Попробуйте написать её точнее.")

async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    keyboard = [[InlineKeyboardButton("АКТУАЛЬНЫЕ ВАКАНСИИ", callback_data="find_jobs")]]
    await update.callback_query.message.reply_text(
        "Напишите название профессии или посмотрите список вакансий",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    index = int(update.callback_query.data.split("_")[1])
    data = context.user_data.get('vacancy_matches')
    if not data or index >= len(data):
        await update.callback_query.answer("Ошибка, попробуйте ещё раз.")
        return
    row = data[index]
    context.user_data['vacancy'] = row['Вакансия']
    context.user_data['state'] = STATE_WAITING_FOR_FIO
    await update.callback_query.answer()
    await update.callback_query.message.edit_text(f"Вы выбрали: {row['Вакансия']}\nВведите ваше ФИО:")

async def handle_fio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fio = update.message.text.strip()
    if not re.match(r"^[А-Яа-яЁё\s-]+$", fio):
        await update.message.reply_text("ФИО должно содержать только буквы, пробелы и дефисы.")
        return
    context.user_data['fio'] = fio
    context.user_data['state'] = STATE_WAITING_FOR_PHONE
    await update.message.reply_text("Введите ваш номер телефона:")

async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    if not re.match(r"^[\d+\(\)\- ]+$", phone):
        await update.message.reply_text("Номер может содержать только цифры, +, -, пробелы и ().")
        return
    context.user_data['phone'] = phone
    save_application_to_sheet(
        context.user_data['fio'],
        context.user_data['phone'],
        context.user_data['vacancy'],
        update.message.from_user.username
    )
    await update.message.reply_text("Спасибо! Ваш отклик принят.")
    context.user_data.clear()

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state')
    if state == STATE_WAITING_FOR_FIO:
        await handle_fio(update, context)
    elif state == STATE_WAITING_FOR_PHONE:
        await handle_phone(update, context)
    else:
        await handle_message(update, context)

# --- Запуск Telegram бота в отдельном потоке ---
def run_bot():
    application = ApplicationBuilder().token(os.environ["BOT_TOKEN"]).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("jobs", jobs))
    application.add_handler(CallbackQueryHandler(handle_callback, pattern="find_jobs"))
    application.add_handler(CallbackQueryHandler(handle_apply, pattern=r"apply_\d+"))
    application.add_handler(CallbackQueryHandler(back, pattern="back"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    application.run_polling()

if __name__ == "__main__":
    threading.Thread(target=run_bot).start()
    port = int(os.environ.get("PORT", 5000))
    app_flask.run(host="0.0.0.0", port=port)
