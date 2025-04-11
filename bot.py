from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import asyncio
import difflib
import re
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

# Состояния для пользователя
STATE_WAITING_FOR_FIO = 1
STATE_WAITING_FOR_PHONE = 2
STATE_IDLE = 0

# Этапы для ConversationHandler
FIO, PHONE = range(1, 3)

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
    context.user_data['vacancy'] = vacancy  # Сохраняем вакансию на которую откликнулись

    await query.answer()
    await query.message.edit_text(f"Вы откликнулись на вакансию: {vacancy}\n\nПожалуйста, введите ваше ФИО:")

    # Меняем состояние пользователя на ожидающий ФИО
    return FIO

# Обработка ввода ФИО
async def handle_fio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fio = update.message.text.strip()

    if not re.match(r"^[А-Яа-яЁё\s-]+$", fio):
        await update.message.reply_text("Неверное ФИО. Пожалуйста, введите ФИО только с буквами, пробелами и дефисами.")
        return FIO

    context.user_data['fio'] = fio
    await update.message.reply_text("Теперь, пожалуйста, введите ваш номер телефона:")

    # Переходим к следующему шагу
    return PHONE

# Обработка ввода номера телефона
async def handle_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()

    if not re.match(r"^[\d+\(\)\- ]+$", phone):
        await update.message.reply_text("Неверный номер телефона. Пожалуйста, введите номер с цифрами, знаками +, -, (), пробелами.")
        return PHONE

    context.user_data['phone'] = phone
    username = update.message.from_user.username

    # Сохранение данных в Google Sheets
    save_application_to_sheet(context.user_data['fio'], context.user_data['phone'], context.user_data['vacancy'], username)
    
    await update.message.reply_text(f"Ваш отклик на вакансию {context.user_data['vacancy']} принят!\n"
                                    f"ФИО: {context.user_data['fio']}\n"
                                    f"Телефон: {context.user_data['phone']}\n\n"
                                    "Спасибо за отклик!")

    # Завершаем процесс
    return ConversationHandler.END

# Запуск бота с использованием ConversationHandler
conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(handle_apply, pattern=r"apply_\d+")],
    states={
        FIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_fio)],
        PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_phone)],
    },
    fallbacks=[]
)

# Запуск бота
app = ApplicationBuilder().token(os.environ["BOT_TOKEN"]).build()

# Хендлеры
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("jobs", jobs))
app.add_handler(CallbackQueryHandler(handle_callback, pattern="find_jobs"))
app.add_handler(conversation_handler)

app.run_polling()
