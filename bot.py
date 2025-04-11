from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          CallbackQueryHandler, ContextTypes, ConversationHandler, filters)
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import asyncio
import difflib
import re

# Этапы ConversationHandler
ASK_NAME, ASK_PHONE = range(2)

# Подключение к Google Sheets
scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']
creds_dict = json.loads(os.environ['GOOGLE_CREDENTIALS'])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("Передовик вакансии БОТ").sheet1

def get_data():
    return sheet.get_all_records()

user_data_temp = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("АКТУАЛЬНЫЕ ВАКАНСИИ", callback_data="find_jobs")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Я помогу вам подобрать вакансию. Напишите название профессии или посмотрите список открытых вакансий",
        reply_markup=reply_markup)

async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_data()
    lines = [f"\u2022 {line.strip()}" for row in data if row.get('СТАТУС', '').strip().upper() == 'НАБИРАЕМ'
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
    query = update.callback_query
    await query.answer()
    if query.data == "find_jobs":
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
        for i, row in enumerate(matches):
            description = row.get('Описание', '').strip()
            description_text = f"\n\n\ud83d\udcc3 Описание вакансии:\n\n{description}" if description else ""

            response = f"""
\ud83d\udd27 *{row['Вакансия']}*

\ud83d\udcc8 Часовая ставка:
{row['Часовая ставка']}

\ud83d\udd50 Вахта 30/30 по 12ч:
{row['Вахта по 12 часов (30/30)']}

\ud83d\udd51 Вахта 60/30 по 11ч:
{row['Вахта по 11 ч (60/30)']}

\ud83d\udccc Статус: {row.get('СТАТУС', 'не указан')}{description_text}
"""
            keyboard = [[InlineKeyboardButton("ОТКЛИКНУТЬСЯ", callback_data=f"apply_{i}"),
                         InlineKeyboardButton("НАЗАД", callback_data="back")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_markdown(response, reply_markup=reply_markup)
    else:
        await update.message.reply_text("Не нашёл вакансию по вашему запросу. Попробуйте написать её полнее.")

async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    keyboard = [[InlineKeyboardButton("АКТУАЛЬНЫЕ ВАКАНСИИ", callback_data="find_jobs")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text(
        "Я помогу вам подобрать вакансию. Напишите название профессии или посмотрите список открытых вакансий",
        reply_markup=reply_markup)

async def handle_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    index = int(query.data.split("_", 1)[1])
    context.user_data['vacancy_index'] = index
    await query.answer()
    await query.message.edit_text("Пожалуйста, введите ваше ФИО:")
    return ASK_NAME

async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not re.fullmatch(r"[A-Za-zА-Яа-яЁё\-\s]+", name):
        await update.message.reply_text("Пожалуйста, введите корректное ФИО (только буквы и дефис).")
        return ASK_NAME
    context.user_data['full_name'] = name
    await update.message.reply_text("Теперь укажите ваш контактный номер телефона:")
    return ASK_PHONE

async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    if not re.fullmatch(r"[+\d()\s-]+", phone):
        await update.message.reply_text("Пожалуйста, введите корректный номер телефона (только цифры, +, (), -).")
        return ASK_PHONE

    context.user_data['phone'] = phone
    username = update.message.from_user.username or "Без username"

    vacancy_index = context.user_data.get('vacancy_index')
    data = get_data()
    if vacancy_index >= len(data):
        await update.message.reply_text("Ошибка: вакансия не найдена.")
        return ConversationHandler.END

    vacancy = data[vacancy_index]['Вакансия']
    full_name = context.user_data['full_name']

    await update.message.reply_text(f"Спасибо! Вы откликнулись на вакансию: {vacancy}\n\n"
                                    f"ФИО: {full_name}\n"
                                    f"Телефон: {phone}\n"
                                    f"Username: @{username}")
    return ConversationHandler.END

# Запуск
app = ApplicationBuilder().token(os.environ["BOT_TOKEN"]).build()

conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(handle_apply, pattern=r"apply_\\d+")],
    states={
        ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
        ASK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_phone)],
    },
    fallbacks=[]
)

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("jobs", jobs))
app.add_handler(conv_handler)
app.add_handler(CallbackQueryHandler(handle_callback, pattern="find_jobs"))
app.add_handler(CallbackQueryHandler(back, pattern="back"))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app.run_polling()
