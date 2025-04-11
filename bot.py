from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import asyncio  # Для использования асинхронной задержки

# Подключение к Google Sheets
scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']

creds_dict = json.loads(os.environ['GOOGLE_CREDENTIALS'])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

client = gspread.authorize(creds)
sheet = client.open("Передовик вакансии БОТ").sheet1  # замени на точное название таблицы

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

# Команда /jobs
async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_data()
    
    lines = []
    for row in data:
        if row.get('СТАТУС', '').strip().upper() == 'НАБИРАЕМ':
            for line in row['Вакансия'].splitlines():
                lines.append(f"• {line.strip()}")
    text = "\n".join(lines)

    await update.message.reply_text("Список актуальных вакансий:\n\n" + text)
    await asyncio.sleep(1)
    await update.message.reply_text("Какая вакансия интересует?")

# Гибкий поиск по сообщению
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    data = get_data()

    for row in data:
        вакансии = row['Вакансия'].lower().splitlines()
        for вак in вакансии:
            if text in вак:
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

# Обработка кнопки
async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "find_jobs":
        await jobs(update, context)

# Запуск бота
app = ApplicationBuilder().token("YOUR_BOT_TOKEN_HERE").build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("jobs", jobs))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.add_handler(MessageHandler(filters.COMMAND, handle_message))  # на всякий случай
app.add_handler(CommandHandler("callback_query", callback_query_handler))
app.add_handler(MessageHandler(filters.ALL, handle_message))
app.add_handler(MessageHandler(filters.StatusUpdate, handle_message))
app.add_handler(MessageHandler(filters.UpdateType, handle_message))
app.add_handler(MessageHandler(filters.Update, handle_message))
app.add_handler(MessageHandler(filters.VOICE, handle_message))
app.add_handler(MessageHandler(filters.Sticker, handle_message))
app.add_handler(MessageHandler(filters.LOCATION, handle_message))
app.add_handler(MessageHandler(filters.Document.ALL, handle_message))
app.add_handler(MessageHandler(filters.Document.PDF, handle_message))
app.add_handler(MessageHandler(filters.Document.WORD, handle_message))
app.add_handler(MessageHandler(filters.Document.PRESENTATION, handle_message))
app.add_handler(MessageHandler(filters.PhotoSize, handle_message))
app.add_handler(MessageHandler(filters.PHOTO, handle_message))
app.add_handler(MessageHandler(filters.VIDEO, handle_message))
app.add_handler(MessageHandler(filters.VIDEO_NOTE, handle_message))
app.add_handler(MessageHandler(filters.CONTACT, handle_message))
app.add_handler(MessageHandler(filters.AUDIO, handle_message))
app.add_handler(MessageHandler(filters.ANIMATION, handle_message))
app.add_handler(MessageHandler(filters.VOICE, handle_message))
app.add_handler(MessageHandler(filters.Sticker, handle_message))
app.add_handler(MessageHandler(filters.DICE, handle_message))
app.add_handler(MessageHandler(filters.POLL, handle_message))
app.add_handler(MessageHandler(filters.GAME, handle_message))
app.add_handler(MessageHandler(filters.PAYMENT, handle_message))
app.add_handler(MessageHandler(filters.INVOICE, handle_message))
app.add_handler(MessageHandler(filters.SUCCESSFUL_PAYMENT, handle_message))
app.add_handler(MessageHandler(filters.SHIPPING_QUERY, handle_message))
app.add_handler(MessageHandler(filters.PRE_CHECKOUT_QUERY, handle_message))
app.add_handler(MessageHandler(filters.CALLBACK_QUERY, handle_message))
app.add_handler(MessageHandler(filters.CHAT_MEMBER, handle_message))

app.add_handler(MessageHandler(filters.ALL, handle_message))
app.add_handler(MessageHandler(filters.TEXT, handle_message))
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_message))
app.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, handle_message))
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_TITLE, handle_message))
app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_PHOTO, handle_message))
app.add_handler(MessageHandler(filters.StatusUpdate.DELETE_CHAT_PHOTO, handle_message))
app.add_handler(MessageHandler(filters.StatusUpdate.GROUP_CHAT_CREATED, handle_message))

app.add_handler(MessageHandler(filters.ALL, handle_message))

app.run_polling()
