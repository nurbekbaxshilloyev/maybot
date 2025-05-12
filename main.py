import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_IDS = [6459086003]  # Faqat 1 ta admin

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Assalomu alaykum! Savollaringiz bo‘lsa, yozing.\n/help - yordam")

# /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🆘 Yordam:\nSavol yuboring va adminlardan javob oling.")

# /info
async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ℹ️ Bu bot orqali siz savollarga tezkor javob olasiz.")

# /contact
async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📞 Biz bilan bog‘lanish: @nurbekbaxshilloyev")

# Savol yuborish
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    user_id = user.id
    message = update.message.text

    # Adminga yuboriladigan tugma
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✉️ Javob yozish", callback_data=f"answer:{user_id}")]
    ])

    context.bot_data[f"question_from_{update.effective_user.id}"] = message

    try:
        await context.bot.send_message(
            chat_id=ADMIN_IDS[0],
            text=f"📩 Yangi savol:\n\n{message}\n\n👤 @{user.username or 'Nomalum'} (ID: {user_id})",
            reply_markup=keyboard
        )
        await update.message.reply_text("✅ Savolingiz yuborildi. Tez orada javob olasiz.")
    except Exception as e:
        await update.message.reply_text(f"Xatolik: {e}")

# Callback tugma
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data.startswith("answer:"):
        user_id = int(data.split(":")[1])
        context.bot_data["pending_answer_user"] = user_id
        await query.message.reply_text("✍️ Iltimos, javobingizni yozing:")
    elif data == "broadcast":
        context.bot_data["is_broadcast"] = True
        await query.message.reply_text("📢 Yubormoqchi bo‘lgan xabaringizni yozing:")

# Javob va broadcast
async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = context.bot_data.get("pending_answer_user")
    is_broadcast = context.bot_data.get("is_broadcast", False)
    text = update.message.text

    if is_broadcast:
        # Broadcast faqat adminlarga (hozir faqat 1 admin)
        for admin_id in ADMIN_IDS:
            await context.bot.send_message(chat_id=admin_id, text=f"📢 Broadcast:\n{text}")
        context.bot_data["is_broadcast"] = False
        await update.message.reply_text("✅ Broadcast yuborildi.")
        return

    if user_id:
        try:
            await context.bot.send_message(chat_id=user_id, text=f"📨 Savolingizga javob:\n\n{text}")
            await update.message.reply_text("✅ Javob yuborildi.")
        except Exception as e:
            await update.message.reply_text(f"❌ Xatolik: {e}")
        context.bot_data["pending_answer_user"] = None
    else:
        await update.message.reply_text("⚠️ Javob yuborish uchun foydalanuvchi tanlanmagan.")

# /broadcast
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMIN_IDS:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Broadcast Yuborish", callback_data="broadcast")]
        ])
        await update.message.reply_text("Broadcast xabar yuborilsinmi?", reply_markup=keyboard)
    else:
        await update.message.reply_text("❌ Siz admin emassiz.")

# Main
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("info", info_command))
    app.add_handler(CommandHandler("contact", contact_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))

    app.add_handler(CallbackQueryHandler(handle_callback))

    app.add_handler(MessageHandler(
        filters.TEXT & filters.User(user_id=ADMIN_IDS), handle_admin_reply
    ))

    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND, handle_user_message
    ))

    print("✅ Bot ishga tushdi.")
    app.run_polling()

if __name__ == "__main__":
    main()
