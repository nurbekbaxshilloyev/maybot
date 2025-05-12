import os
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder, ContextTypes, CommandHandler,
    MessageHandler, CallbackQueryHandler, filters
)

# Token va admin ID
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 6459086003  # faqat 1 admin

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Assalomu alaykum!\nSavolingiz bo‘lsa, yozing.\n/help - yordam"
    )

# /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Yordam:\nSavol yuboring va javob kuting.\n/info - ma'lumot\n/contact - bog‘lanish"
    )

# /info
async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bu bot orqali siz savollarga tezkor javob olasiz.")

# /contact
async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Biz bilan bog‘lanish: @nurbekbaxshilloyev")

# /broadcast
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return await update.message.reply_text("Sizda ruxsat yo‘q.")
    context.user_data["awaiting_broadcast"] = True
    await update.message.reply_text("Broadcast xabarini yuboring:")

# Foydalanuvchi xabari
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    message = update.message.text

    # Callback tugma
    button = InlineKeyboardMarkup([
        [InlineKeyboardButton("✉️ Javob yozish", callback_data=f"answer:{user.id}")]
    ])

    # Adminga yuborish
    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"📩 Yangi savol:\n\n{message}\n\n👤 @{user.username or 'Nomalum'} (ID: {user.id})",
        reply_markup=button
    )

    await update.message.reply_text("Savolingiz adminga yuborildi.")

# Callback tugma bosilganda
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data.startswith("answer:"):
        target_user_id = int(data.split(":")[1])
        context.user_data["reply_to_user"] = target_user_id
        await query.message.reply_text("Javobingizni yozing:")

# Admin matnli javobi
async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = context.user_data.get("reply_to_user")
    broadcast_mode = context.user_data.get("awaiting_broadcast", False)

    if broadcast_mode:
        await context.bot.send_message(chat_id=ADMIN_ID, text="📢 Broadcast xabar:")
        await context.bot.send_message(chat_id=ADMIN_ID, text=update.message.text)
        context.user_data["awaiting_broadcast"] = False
        return await update.message.reply_text("✅ Broadcast yuborildi.")

    if user_id:
        await context.bot.send_message(chat_id=user_id, text=f"📨 Admin javobi:\n\n{update.message.text}")
        await update.message.reply_text("✅ Javob yuborildi.")
        context.user_data["reply_to_user"] = None
    else:
        await update.message.reply_text("⚠️ Javob yuborish uchun foydalanuvchi tanlanmagan.")

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
        filters.TEXT & filters.User(user_id=ADMIN_ID), handle_admin_message
    ))
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.User(user_id=ADMIN_ID), handle_user_message
    ))

    print("✅ Bot ishga tushdi.")
    app.run_polling()

if __name__ == "__main__":
    main()
