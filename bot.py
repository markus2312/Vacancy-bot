from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import asyncio
import difflib

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

# Обработка текстового ввода для поиска вакансий
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    data = get_data()
    matches = []

    # Ищем вакансии, соответствующие запросу пользователя
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

# Обработка отклика на вакансию
async def apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Получаем индекс вакансии
    vacancy_index = int(query.data.split('_')[1])
    data = get_data()
    vacancy = data[vacancy_index]['Вакансия']

    context.user_data['vacancy'] = vacancy  # Сохраняем вакансию для дальнейшей обработки

    # Запрашиваем ФИО пользователя
    await query.message.reply_text(f"Вы откликаетесь на вакансию: {vacancy}\nВведите ваше ФИО:")

# Обработка ввода ФИО
async def handle_fio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fio = update.message.text.strip()

    context.user_data['fio'] = fio  # Сохраняем ФИО

    # Запрашиваем номер телефона
    await update.message.reply_text("Теперь, пожалуйста, введите ваш номер телефона:")

    return "PHONE"

# Обработка ввода номера телефона
async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()

    context.user_data['phone'] = phone  # Сохраняем номер телефона

    # Сохраняем отклик в Google Sheets
    save_application_to_sheet(context.user_data['fio'], context.user_data['phone'], context.user_data['vacancy'], update.message.from_user.username)

    await update.message.reply_text(f"Ваш отклик на вакансию {context.user_data['vacancy']} принят!\n"
                                    f"ФИО: {context.user_data['fio']}\n"
                                    f"Телефон: {context.user_data['phone']}\n\n"
                                    "Спасибо за отклик!")

    return "END"

# Сохранение отклика в Google Sheets
def save_application_to_sheet(name, phone, vacancy, username):
    sheet = client.open_by_key("10TcAZPunK079FBN1gNQIU4XmInMEQ8Qz4CWeA6oDGvI")
    worksheet = sheet.worksheet("bot otkliki")

    new_row = [name, phone, vacancy, f"@{username}" if username else "без username"]
    worksheet.append_row(new_row, value_input_option="USER_ENTERED")

# Обработчик завершения диалога
async def end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Спасибо за использование бота! Если у вас есть еще вопросы, не стесняйтесь обращаться.")
    return "END"

# Запуск бота
app = ApplicationBuilder().token(os.environ["BOT_TOKEN"]).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handle_callback, pattern="find_jobs"))
app.add_handler(CallbackQueryHandler(apply, pattern=r"apply_\d+"))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app.run_polling()
