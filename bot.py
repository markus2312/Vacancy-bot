import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes
import re

# Получаем токен из переменных окружения Railway
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Этапы разговора
FIO, PHONE = range(2)

# Словарь для хранения данных пользователей
user_data = {}

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
    # Заглушка для вакансий
    text = "Список вакансий:\n1. Вакансия 1\n2. Вакансия 2"
    await update.message.reply_text(text)

# Обработка кнопки "ОТКЛИКНУТЬСЯ"
async def apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.edit_text("Введите ваше ФИО (только буквы и дефис):")
    return FIO

# Проверка ввода ФИО (только буквы и дефис)
def validate_fio(fio: str) -> bool:
    return bool(re.match("^[A-Za-zА-Яа-яЁё-]+$", fio))

# Ответ на ввод ФИО
async def get_fio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fio = update.message.text
    if not validate_fio(fio):
        await update.message.reply_text("ФИО должно содержать только буквы и дефис. Попробуйте еще раз.")
        return FIO

    user_data[update.message.from_user.id] = {"fio": fio}
    await update.message.reply_text("Укажите контактный номер телефона (только цифры и символы +, (, )):")
    return PHONE

# Проверка номера телефона (только цифры и символы +, (, ))
def validate_phone(phone: str) -> bool:
    return bool(re.match("^[0-9+()]*$", phone))

# Ответ на ввод телефона
async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text
    if not validate_phone(phone):
        await update.message.reply_text("Номер телефона должен содержать только цифры и символы +, (, ). Попробуйте еще раз.")
        return PHONE

    user_data[update.message.from_user.id]["phone"] = phone
    await update.message.reply_text(f"Вы откликнулись на вакансию!\nФИО: {user_data[update.message.from_user.id]['fio']}\nТелефон: {user_data[update.message.from_user.id]['phone']}")
    return ConversationHandler.END

# Начало диалога
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Отменено. Вы можете начать откликнуться снова, выбрав вакансию.")
    return ConversationHandler.END

# ConversationHandler
conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(apply, pattern="apply_")],
    states={
        FIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_fio)],
        PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)],
    },
    fallbacks=[CommandHandler('cancel', cancel)]
)

# Запуск бота
app = ApplicationBuilder().token(BOT_TOKEN).build()

# Добавляем обработчики
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("jobs", jobs))
app.add_handler(conv_handler)

# Запускаем бота
app.run_polling()
