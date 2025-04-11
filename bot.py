from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os

# Подключение к Google Sheets
scope = ["https://spreadsheets.google.com/feeds", 'https://www.googleapis.com/auth/drive']
creds_dict = json.loads(os.environ['GOOGLE_CREDENTIALS'])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
client = gspread.authorize(creds)
sheet = client.open("Передовик вакансии БОТ").worksheet("bot otkliki")

# Состояния для ConversationHandler
GET_NAME, GET_PHONE = range(2)

# Функция получения данных о вакансиях
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

# Функция вывода списка вакансий
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

# Обработка кнопки отклика
async def start_application(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Получаем название вакансии, на которую откликаются
    vacancy_name = context.user_data.get('vacancy_name', '')
    if vacancy_name:
        # Отправляем сообщение с данными о вакансии
        keyboard = [
            [InlineKeyboardButton("ОТКЛИКНУТЬСЯ", callback_data="start_application")],
            [InlineKeyboardButton("НАЗАД", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Получаем описание вакансии из таблицы
        data = get_data()
        vacancy_description = ""
        for row in data:
            if row['Вакансия'] == vacancy_name:
                vacancy_description = row.get('Описание', '')

        # Формируем текст с деталями вакансии
        vacancy_details = f"🔧 *{vacancy_name}*\n\n📃 Описание вакансии:\n\n{vacancy_description}"

        await query.edit_message_text(vacancy_details, reply_markup=reply_markup)
    else:
        await query.edit_message_text("Не удалось найти вакансию, попробуйте снова.")

    return GET_NAME  # Начинаем сбор данных

# Сбор ФИО
async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.text
    context.user_data['name'] = user_name  # Сохраняем имя в user_data

    # Запрашиваем номер телефона
    await update.message.reply_text("Теперь введите ваш номер телефона:")
    return GET_PHONE

# Сбор номера телефона
async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text
    # Проверка на корректность ввода номера
    if not all(c.isdigit() or c in "+()-" for c in phone):
        await update.message.reply_text("Похоже вы ввели некорректный номер телефона, давайте попробуем еще раз.")
        return GET_PHONE  # Повторно запрашиваем номер телефона

    context.user_data['phone'] = phone  # Сохраняем номер телефона в user_data

    # Записываем данные в Google Sheets
    sheet.append_row([
        context.user_data.get('vacancy', 'не указана'),  # Название вакансии
        context.user_data['name'],  # ФИО
        context.user_data['phone'],  # Номер телефона
        update.message.from_user.username  # Телеграм-имя пользователя
    ])

    # Подтверждение
    await update.message.reply_text("Ваш отклик отправлен! Благодарим за интерес.")
    return ConversationHandler.END  # Завершаем диалог

# Обработка кнопки НАЗАД
async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Возвращаем на стартовый экран с вакансиями
    keyboard = [
        [InlineKeyboardButton("АКТУАЛЬНЫЕ ВАКАНСИИ", callback_data="find_jobs")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        "Я помогу вам подобрать вакансию. Напишите название профессии или посмотрите список открытых вакансий",
        reply_markup=reply_markup
    )

    return ConversationHandler.END  # Завершаем текущую конверсацию

# Функция обработки конкретной вакансии
async def job_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    # Получаем вакансию, на которую откликается пользователь
    vacancy_name = "Пример вакансии"  # Например, эта вакансия, нужно получить её из данных
    context.user_data['vacancy_name'] = vacancy_name

    # Добавляем кнопки
    keyboard = [
        [InlineKeyboardButton("ОТКЛИКНУТЬСЯ", callback_data="start_application")],
        [InlineKeyboardButton("НАЗАД", callback_data="back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Формируем текст с вакансией
    vacancy_details = f"🔧 *{vacancy_name}*\n\nОписание вакансии: ..."

    await query.edit_message_text(vacancy_details, reply_markup=reply_markup)

# ConversationHandler
conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_application, pattern="^start_application$")],
    states={
        GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
        GET_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
    },
    fallbacks=[CallbackQueryHandler(back, pattern="^back$")]
)

# Запуск бота
app = ApplicationBuilder().token("7868075757:AAER7ENuM0L6WT_W5ZB0iRrVRUw8WeijbOo").build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("jobs", jobs))
app.add_handler(CallbackQueryHandler(job_details, pattern="^find_jobs$"))
app.add_handler(conversation_handler)

app.run_polling()
