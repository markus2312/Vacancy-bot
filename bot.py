from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import asyncio
import difflib
import re

# Подключение к Google Sheets
scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']
creds_dict = json.loads(os.environ['GOOGLE_CREDENTIALS'])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("Передовик вакансии БОТ").sheet1
otkliki_sheet = client.open("Передовик вакансии БОТ").worksheet("bot otkliki")

def get_data():
    return sheet.get_all_records()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("АКТУАЛЬНЫЕ ВАКАНСИИ", callback_data="find_jobs")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Я помогу вам подобрать вакансию. Напишите название профессии или посмотрите список открытых вакансий",
        reply_markup=reply_markup
    )

async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = get_data()
    lines = []
    for row in data:
        if row.get('СТАТУС', '').strip().upper() == 'НАБИРАЕМ':
            for line in row['Вакансия'].splitlines():
                lines.append(f"• {line.strip()}")
    text = "\n".join(lines)

    # Добавление кнопок
    keyboard = [
        [InlineKeyboardButton("ОТКЛИКНУТЬСЯ", callback_data="apply_for_job"),
         InlineKeyboardButton("НАЗАД", callback_data="go_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Определим, откуда пришёл запрос (команда или кнопка)
    if update.message:
        await update.message.reply_text("Список актуальных вакансий:\n\n" + text, reply_markup=reply_markup)
        await asyncio.sleep(1)
        await update.message.reply_text("Какая вакансия интересует?")
    elif update.callback_query:
        await update.callback_query.message.reply_text("Список актуальных вакансий:\n\n" + text, reply_markup=reply_markup)
        await asyncio.sleep(1)
        await update.callback_query.message.reply_text("Какая вакансия интересует?")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "find_jobs":
        await jobs(update, context)
    elif query.data == "apply_for_job":
        # Начинаем процесс отклика
        await query.message.reply_text("Введите свою Фамилию и Имя.")
        context.user_data['state'] = 'waiting_for_name'
    elif query.data == "go_back":
        # Возвращаемся на стартовую страницу
        await start(update, context)

# Обработка текстовых сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_state = context.user_data.get('state', None)

    if user_state == 'waiting_for_name':
        # Сохраняем фамилию и имя
        name = update.message.text.strip()
        context.user_data['name'] = name
        await update.message.reply_text("Теперь введите ваш контактный номер телефона.")
        context.user_data['state'] = 'waiting_for_phone'

    elif user_state == 'waiting_for_phone':
        phone = update.message.text.strip()
        # Проверка корректности номера телефона
        if re.match(r"^\+?\(?\d{1,3}\)?[-\s]?\d{1,4}[-\s]?\d{1,4}[-\s]?\d{1,9}$", phone):
            context.user_data['phone'] = phone
            name = context.user_data.get('name')
            job = context.user_data.get('job')
            username = update.message.from_user.username

            # Запись в таблицу
            otkliki_sheet.append_row([job, name, phone, username])
            await update.message.reply_text(f"Ваша заявка на вакансию '{job}' успешно отправлена! Спасибо за отклик.")
            context.user_data.clear()  # Сброс состояния
        else:
            await update.message.reply_text("Похоже, вы ввели не корректный номер телефона, давайте попробуем еще раз.")

    else:
        await update.message.reply_text("Пожалуйста, используйте кнопки для взаимодействия.")

# Запуск бота
app = ApplicationBuilder().token("YOUR_BOT_API_KEY").build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handle_callback))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
app.run_polling()
