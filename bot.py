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

# Обработка кнопки "НАЗАД"
async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("Back button clicked")

    keyboard = [
        [InlineKeyboardButton("АКТУАЛЬНЫЕ ВАКАНСИИ", callback_data="find_jobs")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.callback_query.answer()

    await update.callback_query.message.reply_text(
        "Я помогу вам подобрать вакансию. Напишите название профессии или посмотрите список открытых вакансий",
        reply_markup=reply_markup
    )

# Обработка кнопки "ОТКЛИКНУТЬСЯ"
async def handle_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    vacancy = query.data.split("_", 1)[1]  # Получаем название вакансии из callback_data
    await query.answer()

    # Запрос имени и фамилии у соискателя
    await query.message.edit_text(f"Вы откликнулись на вакансию: {vacancy}\nВведите ваше ФИО:")

    # Сохраняем вакансию для использования в дальнейшем (например, при записи данных в Google Sheets)
    context.user_data['vacancy'] = vacancy

# Обработка введенного имени и фамилии
async def handle_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_name = update.message.text.strip()

    # Проверка, что пользователь уже откликнулся на вакансию
    if 'vacancy' in context.user_data:
        vacancy = context.user_data['vacancy']
        await update.message.reply_text(f"Спасибо! Вы откликнулись на вакансию: {vacancy}. Ваши данные: {user_name}.")

        # Здесь можно обработать данные (например, сохранить в Google Sheets)
        # Например, сохраняем данные в контекст или базу данных
        # Если хотите, можете сохранить имя и вакансию в Google Sheets или другой источник.

        # Очистка данных после обработки
        del context.user_data['vacancy']
    else:
        await update.message.reply_text("Не удалось найти вакансию. Попробуйте откликнуться заново.")

# Запуск бота
app = ApplicationBuilder().token("7868075757:AAER7ENuM0L6WT_W5ZB0iRrVRUw8WeijbOo").build()

# Сначала добавляем обработчики для кнопки "АКТУАЛЬНЫЕ ВАКАНСИИ" (важно, чтобы он был первым)
app.add_handler(CallbackQueryHandler(jobs, pattern="find_jobs"))

# Затем добавляем обработчики для кнопки "ОТКЛИКНУТЬСЯ" и "НАЗАД"
app.add_handler(CallbackQueryHandler(handle_apply, pattern="apply_"))
app.add_handler(CallbackQueryHandler(back, pattern="back"))

# После этого добавляем обработчики для команд
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("jobs", jobs))

# Обработчик текстовых сообщений для получения ФИО
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_name))

# Запуск бота
app.run_polling()
