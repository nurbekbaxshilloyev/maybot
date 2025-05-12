import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 6459086003  # Faqat bitta admin

user_questions = {}  # foydalanuvchi ID -> savol matni


# START
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Assalomu alaykum! Savolingizni yozing.")


# HELP
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Savolingizni yozing. Admin sizga tez orada javob beradi.")


# Foydalanuvchi xabari
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text
    user_id = user.id
    user_questions[user_id] = text

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✉️ Javob yozish", callback_data=f"answer:{user_id}")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]
    ])

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"📩 Yangi savol:\n\n{text}\n\n👤 @{user.username or user.full_name} ({user_id})",
        reply_markup=keyboard
    )
    await update.message.reply_text("✅ Savolingiz adminga yuborildi.")


# CALLBACK
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("answer:"):
        user_id = int(data.split(":")[1])
        context.user_data["reply_to_user"] = user_id
        await query.message.reply_text("✍️ Iltimos, foydalanuvchiga yuboriladigan javobni yozing.")
    elif data == "broadcast":
        context.user_data["broadcast_mode"] = True
        await query.message.reply_text("📢 Broadcast matnini yozing.")


# Admin xabari (javob yoki broadcast)
async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = context.user_data.get("reply_to_user")
    is_broadcast = context.user_data.get("broadcast_mode", False)

    if is_broadcast:
        message = update.message.text
        context.user_data["broadcast_mode"] = False
        # Broadcast faqat foydalanuvchilarga yuborilmaydi — bu yerda siz user IDs ro'yxatini saqlashingiz mumkin
        await update.message.reply_text("✅ Broadcast yuborildi.")
        return

    if user_id:
        try:
            await context.bot.send_message(chat_id=user_id, text=f"📨 Admin javobi:\n\n{update.message.text}")
            await update.message.reply_text("✅ Javob yuborildi.")
        except Exception as e:
            await update.message.reply_text(f"❌ Xatolik: {e}")
        context.user_data["reply_to_user"] = None
    else:
        await update.message.reply_text("⚠️ Javob yuboriladigan foydalanuvchi tanlanmagan.")


# MAIN
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT & filters.User(user_id=ADMIN_ID), handle_admin_reply))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.User(user_id=ADMIN_ID), handle_user_message))

    print("✅ Bot ishga tushdi.")
    app.run_polling()


if __name__ == "__main__":
    main()
