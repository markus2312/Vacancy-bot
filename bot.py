from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import asyncio
import difflib
from datetime import datetime

# Подключение к Google Sheets
scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']
creds_dict = json.loads(os.environ['GOOGLE_CREDENTIALS'])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)

# Получение данных из таблицы
def get_data():
    sheet = client.open("Передовик вакансии БОТ").sheet1
    return sheet.get_all_records()

def save_application_to_sheet(name, phone, vacancy, username):
    sheet = client.open_by_key("10TcAZPunK079FBN1gNQIU4XmInMEQ8Qz4CWeA6oDGvI")
    worksheet = sheet.worksheet("bot otkliki")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_row = [now, name, phone, vacancy, f"@{username}" if username else "без username"]
    worksheet.append_row(new_row, value_input_option="USER_ENTERED")

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

# Команда /jobs и кнопка
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
        await asyncio.sleep(1)
        await update.message.reply_text("Какая вакансия интересует?")
    elif update.callback_query:
        await update.callback_query.message.reply_text("Список актуальных вакансий:\n\n" + text)
        await asyncio.sleep(1)
        await update.callback_query.message.reply_text("Какая вакансия интересует?")

# Обработка кнопки "АКТУАЛЬНЫЕ ВАКАНСИИ"
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "find_jobs":
        await jobs(update, context)

# Обработка текстового ввода
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

            keyboard = [
                [InlineKeyboardButton("ОТКЛИКНУТЬСЯ", callback_data=f"apply_{i}"),
                 InlineKeyboardButton("НАЗАД", callback_data="back")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_markdown(response, reply_markup=reply_markup)
    else:
        await update.message.reply_text("Не нашёл вакансию по вашему запросу. Попробуйте написать её полнее.")

# Обработка кнопки "НАЗАД"
async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    keyboard = [
        [InlineKeyboardButton("АКТУАЛЬНЫЕ ВАКАНСИИ", callback_data="find_jobs")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text(
        "Я помогу вам подобрать вакансию. Напишите название профессии или посмотрите список открытых вакансий",
        reply_markup=reply_markup
    )

# Обработка кнопки "ОТКЛИКНУТЬСЯ"
async def handle_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    index = int(query.data.split("_", 1)[1])
    data = get_data()

    if index >= len(data):
        await query.answer("Не удалось найти вакансию. Попробуйте откликнуться заново.")
        return

    row = data[index]
    vacancy = row['Вакансия']
    await query.answer()

    # Сохраняем вакансию в контексте для дальнейшей обработки
    context.user_data['vacancy'] = vacancy

    await query.message.edit_text(f"Вы откликнулись на вакансию: {vacancy}\n\nПожалуйста, введите ваше ФИО:")

# Обработка текста с ФИО
async def handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name.replace(" ", "").replace("-", "").isalpha():
        await update.message.reply_text("Пожалуйста, введите корректное ФИО (только буквы, пробелы и дефисы).")
        return

    context.user_data['name'] = name
    await update.message.reply_text("Теперь, пожалуйста, введите ваш номер телефона:")

# Обработка текста с номером телефона
async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    if not all(char.isdigit() or char in "+() " for char in phone):
        await update.message.reply_text("Пожалуйста, введите корректный номер телефона (можно использовать только цифры, +, ( и )).")
        return

    context.user_data['phone'] = phone
    name = context.user_data.get('name')
    phone = context.user_data.get('phone')
    vacancy = context.user_data.get('vacancy')
    username = update.message.from_user.username or 'без username'

    save_application_to_sheet(name, phone, vacancy, username)

    await update.message.reply_text("Спасибо! Мы получили ваш отклик. Скоро с вами свяжутся.")

# Запуск бота
app = ApplicationBuilder().token(os.environ["BOT_TOKEN"]).build()

# Хендлеры
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("jobs", jobs))
app.add_handler(CallbackQueryHandler(handle_callback, pattern="find_jobs"))
app.add_handler(CallbackQueryHandler(handle_apply, pattern=r"apply_\d+"))
app.add_handler(CallbackQueryHandler(back, pattern="back"))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# Обработчики для сбора данных (ФИО и телефон)
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_name))  # Обрабатывает ФИО
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone))  # Обрабатывает телефон

app.run_polling()
