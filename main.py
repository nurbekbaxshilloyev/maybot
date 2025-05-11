import logging
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ForceReply,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# Bot tokenini o'zingizning tokeningiz bilan almashtiring
BOT_TOKEN = 'YOUR_BOT_TOKEN_HERE'

# Adminlar ro'yxati (Telegram user IDlari)
ADMINS = [123456789, 987654321]

# Foydalanuvchilar ro'yxati
user_ids = set()

# Savollarni saqlash uchun lug'at
questions = {}

# Logging sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# /start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_ids.add(user.id)
    await update.message.reply_text(
        "Assalomu alaykum! Savolingizni yozing yoki quyidagi komandalarni tanlang:\n"
        "/help - Yordam\n"
        "/info - Ma'lumot\n"
        "/contact - Aloqa"
    )

# /help komandasi
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Yordam uchun bu yerga murojaat qiling.")

# /info komandasi
async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bu bot foydalanuvchilarning savollarini qabul qiladi va adminlarga yuboradi.")

# /contact komandasi
async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Biz bilan bog'lanish uchun: contact@example.com")

# Foydalanuvchi xabarini qabul qilish
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message.text
    question_id = update.message.message_id
    questions[question_id] = {
        'user_id': user.id,
        'username': user.username,
        'question': message,
    }

    # Adminlarga savolni yuborish
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Javob berish", callback_data=f"answer:{question_id}")]
    ])
    for admin_id in ADMINS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"Yangi savol:\n\n{message}\n\nFoydalanuvchi: @{user.username or 'Noma'lum'}",
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Adminga xabar yuborishda xatolik: {e}")

# Callback queryni qayta ishlash
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user

    if user.id not in ADMINS:
        await query.answer("Sizda bu amal uchun ruxsat yo'q.", show_alert=True)
        return

    data = query.data
    if data.startswith("answer:"):
        question_id = int(data.split(":")[1])
        question = questions.get(question_id)
        if question:
            context.user_data['answering'] = question_id
            await context.bot.send_message(
                chat_id=user.id,
                text=f"Foydalanuvchi @{question['username']} savoliga javob yozing:",
                reply_markup=ForceReply()
            )
        else:
            await query.answer("Savol topilmadi.", show_alert=True)

# Admin javobini qabul qilish
async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if 'answering' in context.user_data:
        question_id = context.user_data.pop('answering')
        question = questions.get(question_id)
        if question:
            try:
                await context.bot.send_message(
                    chat_id=question['user_id'],
                    text=f"Admin javobi:\n\n{update.message.text}"
                )
                await update.message.reply_text("Javob foydalanuvchiga yuborildi.")
            except Exception as e:
                logger.error(f"Javob yuborishda xatolik: {e}")
                await update.message.reply_text("Javob yuborishda xatolik yuz berdi.")
        else:
            await update.message.reply_text("Savol topilmadi.")
    else:
        await update.message.reply_text("Iltimos, avval savolni tanlang.")

# /broadcast komandasi
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMINS:
        await update.message.reply_text("Sizda bu amal uchun ruxsat yo'q.")
        return

    if context.args:
        message = ' '.join(context.args)
        for uid in user_ids:
            try:
                await context.bot.send_message(chat_id=uid, text=message)
            except Exception as e:
                logger.error(f"Broadcast yuborishda xatolik: {e}")
        await update.message.reply_text("Broadcast xabar yuborildi.")
    else:
        await update.message.reply_text("Iltimos, xabar matnini kiriting: /broadcast [xabar]")

# Botni ishga tushirish
def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("info", info_command))
    application.add_handler(CommandHandler("contact", contact_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & filters.REPLY, handle_reply))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    application.run_polling()

if __name__ == '__main__':
    main()
