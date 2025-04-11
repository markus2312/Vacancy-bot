import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
import asyncio
import difflib

# Настройка логирования
logging.basicConfig(level=logging.DEBUG)  # Логирование на уровне DEBUG
logger = logging.getLogger(__name__)

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
    try:
        logger.debug("Command /start received")  # Логируем команду /start
        keyboard = [
            [InlineKeyboardButton("АКТУАЛЬНЫЕ ВАКАНСИИ", callback_data="find_jobs")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Я помогу вам подобрать вакансию. Напишите название профессии или посмотрите список открытых вакансий",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error in start command: {e}")

# Команда /jobs и кнопка
async def jobs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.debug("Fetching jobs data")  # Логируем начало получения вакансий
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
    except Exception as e:
        logger.error(f"Error in jobs command: {e}")

# Обработка кнопки
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        logger.debug(f"Callback received with data: {query.data}")  # Логируем данные callback
        await query.answer()

        if query.data == "find_jobs":
            await jobs(update, context)
    except Exception as e:
        logger.error(f"Error in handle_callback: {e}")
        await update.callback_query.answer("Произошла ошибка при обработке запроса. Попробуйте снова позже.")

# Ответ на текст
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
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

                # Добавляем кнопки
                keyboard = [
                    [InlineKeyboardButton("ОТКЛИКНУТЬСЯ", callback_data=f"apply_{row['Вакансия']}"),
                     InlineKeyboardButton("НАЗАД", callback_data="back")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await update.message.reply_markdown(response, reply_markup=reply_markup)
        else:
            await update.message.reply_text("Не нашёл вакансию по вашему запросу. Попробуйте написать её полнее.")
    except Exception as e:
        logger.error(f"Error in handle_message: {e}")
        await update.message.reply_text("Произошла ошибка при обработке вашего запроса.")

# Обработка команды /back
async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        logger.debug("Back button clicked")  # Логируем, что кнопка "НАЗАД" была нажата
        keyboard = [
            [InlineKeyboardButton("АКТУАЛЬНЫЕ ВАКАНСИИ", callback_data="find_jobs")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Ответ на запрос callback_query, чтобы убрать индикатор загрузки
        await update.callback_query.answer()

        # Отправка нового сообщения или редактирование текущего
        await update.callback_query.message.edit_text(
            "Я помогу вам подобрать вакансию. Напишите название профессии или посмотрите список открытых вакансий",
            reply_markup=reply_markup
        )
    except Exception as e:
        logger.error(f"Error in back button handler: {e}")
        await update.callback_query.answer("Произошла ошибка при возвращении. Попробуйте снова позже.")

# Обработка кнопки отклика
async def handle_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        vacancy = query.data.split("_", 1)[1]  # Получаем название вакансии
        logger.debug(f"User applied for vacancy: {vacancy}")  # Логируем отклик на вакансию
        await query.answer()
        await query.message.edit_text(f"Вы откликнулись на вакансию: {vacancy}\nВведите ваше ФИО:")
    except Exception as e:
        logger.error(f"Error in handle_apply: {e}")
        await update.callback_query.answer("Произошла ошибка при отклике на вакансию. Попробуйте снова позже.")

# Запуск бота
app = ApplicationBuilder().token("7868075757:AAER7ENuM0L6WT_W5ZB0iRrVRUw8WeijbOo").build()
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("jobs", jobs))
app.add_handler(CommandHandler("back", back))
app.add_handler(CallbackQueryHandler(handle_callback))
app.add_handler(CallbackQueryHandler(handle_apply, pattern="apply_"))
app.add_handler(CallbackQueryHandler(back, pattern="back"))  # Обработка кнопки "НАЗАД"
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

app.run_polling()
