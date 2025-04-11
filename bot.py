from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler,
                          CallbackQueryHandler, ConversationHandler, ContextTypes, filters)
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import asyncio
import difflib

# States for conversation
CHOOSING_VACANCY, ASK_NAME, ASK_PHONE = range(3)

# Google Sheets connection
scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']
creds_dict = json.loads(os.environ['GOOGLE_CREDENTIALS'])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("Передовик вакансии БОТ").sheet1

def get_data():
    return sheet.get_all_records()

# /start command
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("АКТУАЛЬНЫЕ ВАКАНСИИ", callback_data="find_jobs")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Я помогу вам подобрать вакансию. Напишите название профессии или посмотрите список открытых вакансий",
        reply_markup=reply_markup
    )
    return CHOOSING_VACANCY

# Jobs list
async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_data()
    lines = []
    for row in data:
        if row.get('СТАТУС', '').strip().upper() == 'НАБИРАЕМ':
            for line in row['Вакансия'].splitlines():
                lines.append(f"• {line.strip()}")
    text = "\n".join(lines)

    if update.message:
        await update.message.reply_text("Список актуальных вакансий:\n\n" + text)
    elif update.callback_query:
        await update.callback_query.message.reply_text("Список актуальных вакансий:\n\n" + text)
    await asyncio.sleep(1)
    await update.effective_message.reply_text("Какая вакансия интересует?")
    return CHOOSING_VACANCY

# Обработка текстового ввода с названием вакансии
async def handle_vacancy_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    data = get_data()
    matches = []

    for row in data:
        for line in row['Вакансия'].splitlines():
            if text in line.lower() or difflib.get_close_matches(text, [line.lower()], cutoff=0.6):
                matches.append(row)
                break

    if matches:
        context.user_data['vacancies'] = matches
        for i, row in enumerate(matches):
            description = row.get('Описание', '').strip()
            description_text = f"\n\n📃 Описание вакансии:\n\n{description}" if description else ""

            response = f"""
🔧 *{row['Вакансия']}*

📈 Часовая ставка:
{row['Часовая ставка']}

🕐 Вахта 30/30 по 12ч:
{row['Вахта по 12 часов (30/30)']}

🕑 Вахта 60/30 по 11ч:
{row['Вахта по 11 ч (60/30)']}

📌 Статус: {row.get('СТАТУС', 'не указан')}{description_text}
"""
            keyboard = [[
                InlineKeyboardButton("ОТКЛИКНУТЬСЯ", callback_data=f"apply_{i}"),
                InlineKeyboardButton("НАЗАД", callback_data="back")
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(response, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text("Не нашёл вакансию по вашему запросу. Попробуйте написать её полнее.")
    return CHOOSING_VACANCY

# Обработка кнопки "ОТКЛИКНУТЬСЯ"
async def handle_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    index = int(query.data.split("_")[1])
    vacancies = context.user_data.get('vacancies', [])

    if index >= len(vacancies):
        await query.answer("Не удалось найти вакансию. Попробуйте снова.")
        return CHOOSING_VACANCY

    vacancy = vacancies[index]
    context.user_data['selected_vacancy'] = vacancy.get("Вакансия", "Неизвестно")
    await query.answer()
    await query.message.reply_text("Вы откликнулись на вакансию. Пожалуйста, введите ваше ФИО:")
    return ASK_NAME

# Обработка ввода ФИО
async def ask_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['name'] = update.message.text
    await update.message.reply_text("Теперь введите ваш номер телефона:")
    return ASK_PHONE

# Обработка ввода телефона
async def ask_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['phone'] = update.message.text

    name = context.user_data.get('name')
    phone = context.user_data.get('phone')
    vacancy = context.user_data.get('selected_vacancy')

    await update.message.reply_text(f"Спасибо! Вы откликнулись на вакансию: {vacancy}\n\nФИО: {name}\nТелефон: {phone}")
    return ConversationHandler.END

# Обработка кнопки "НАЗАД"
async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    keyboard = [[InlineKeyboardButton("АКТУАЛЬНЫЕ ВАКАНСИИ", callback_data="find_jobs")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text(
        "Я помогу вам подобрать вакансию. Напишите название профессии или посмотрите список открытых вакансий",
        reply_markup=reply_markup
    )
    return CHOOSING_VACANCY

# Запуск бота
app = ApplicationBuilder().token(os.environ['TELEGRAM_BOT_TOKEN']).build()

conv_handler = ConversationHandler(
    entry_points=[CommandHandler("start", start)],
    states={
        CHOOSING_VACANCY: [
            CallbackQueryHandler(jobs, pattern="find_jobs"),
            CallbackQueryHandler(handle_apply, pattern=r"apply_\\d+"),
            CallbackQueryHandler(back, pattern="back"),
            MessageHandler(filters.TEXT & ~filters.COMMAND, handle_vacancy_query),
        ],
        ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_name)],
        ASK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_phone)]
    },
    fallbacks=[]
)

app.add_handler(conv_handler)
app.run_polling()
