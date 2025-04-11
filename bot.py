from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes, ConversationHandler
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

# Степы для ConversationHandler
GET_NAME, GET_PHONE = range(2)

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

    # Определим, откуда пришёл запрос (команда или кнопка)
    if update.message:
        await update.message.reply_text("Список актуальных вакансий:\n\n" + text)
        await asyncio.sleep(1)
        await update.message.reply_text("Какая вакансия интересует?")
    elif update.callback_query:
        await update.callback_query.message.reply_text("Список актуальных вакансий:\n\n" + text)
        await asyncio.sleep(1)
        await update.callback_query.message.reply_text("Какая вакансия интересует?")

# Обработка кнопки
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "find_jobs":
        await jobs(update, context)

# Ответ на текст
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    data = get_data()

    all_titles = [row['Вакансия'] for row in data]
    matches = []

    for row in data:
        for line in row['Вакансия'].splitlines():
            if text in line.lower():
                matches.append(row)
                break
            elif difflib.get_close_matches(text, [line.lower()], cutoff=0.6):
                matches.append(row)
                break

    if matches:
        for row in matches:
            # Получаем описание из столбца F, который называется "Описание"
            description = row.get('Описание', '').strip()

            # Логируем описание для отладки
            print(f"Описание вакансии для '{row['Вакансия']}': {description}")

            # Если описание не пустое, добавляем его к ответу
            description_text = f"\n📃 Описание вакансии:\n\n{description}" if description else ""

            # Формируем ответ с кнопками
            response = f"""
🔧 *{row['Вакансия']}*

📈 Часовая ставка:
{row['Часовая ставка']}

🕐 Вахта 30/30 по 12ч:
{row['Вахта по 12 часов (30/30)']}

🕑 Вахта 60/30 по 11ч:
{row['Вахта по 11 ч (60/30)']}

📌 Статус: {row.get('СТАТУС', 'не указан')}

{description_text}
"""

            # Кнопки для отклика и назад
            keyboard = [
                [InlineKeyboardButton("ОТКЛИКНУТЬСЯ", callback_data=f"apply_{row['Вакансия']}"),
                 InlineKeyboardButton("НАЗАД", callback_data="back_to_jobs")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(response, reply_markup=reply_markup)

    else:
        await update.message.reply_text("Не нашёл вакансию по вашему запросу. Попробуйте написать её полнее.")

# Обработка отклика на вакансию
async def handle_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    vacancy_name = query.data.split('_')[1]
    await query.answer()

    # Сохраняем вакансию для дальнейшего использования
    context.user_data['vacancy_name'] = vacancy_name
    # Переходим к сбору имени
    return GET_NAME

# Получение имени и фамилии
async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text
    context.user_data['name'] = name

    # Переходим к сбору номера телефона
    await update.message.reply_text("Теперь напишите ваш контактный номер телефона.")
    return GET_PHONE

# Получение номера телефона
async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text
    # Проверяем, что номер телефона валиден
    if not all(c.isdigit() or c in "+() " for c in phone):
        await update.message.reply_text("Похоже, вы ввели некорректный номер телефона. Давайте попробуем еще раз.")
        return GET_PHONE

    # Сохраняем номер телефона
    context.user_data['phone'] = phone

    # Получаем username пользователя
    username = update.message.from_user.username

    # Записываем данные в Google таблицу
    sheet = client.open("Передовик вакансии БОТ").worksheet("bot otkliki")
    sheet.append_row([
        context.user_data['vacancy_name'],
        context.user_data['name'],
        context.user_data['phone'],
        username
    ])

    await update.message.reply_text("Ваш отклик был успешно отправлен. Спасибо!")

    # Возвращаемся к выбору вакансий
    await jobs(update, context)

    return ConversationHandler.END

# Обработка кнопки назад
async def handle_back_to_jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await jobs(update, context)

# Создание ConversationHandler для шагов отклика
conversation_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(handle_apply, pattern=r"apply_.*")],
    states={
        GET_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)],
        GET_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
    },
    fallbacks=[],
)

# Запуск бота
app = ApplicationBuilder().token("7868075757:AAER7ENuM0L6WT_W5ZB0iRrVRUw8WeijbOo").build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("jobs", jobs))
app.add_handler(CallbackQueryHandler(handle_callback))
app.add_handler(CallbackQueryHandler(handle_back_to_jobs, pattern="back_to_jobs"))
app.add_handler(conversation_handler)  # Добавляем ConversationHandler
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app.run_polling()
