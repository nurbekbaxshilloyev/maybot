import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_IDS = [int(i) for i in os.environ.get("ADMIN_IDS", "").split(",") if i.strip().isdigit()]

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Assalomu alaykum! Savollaringiz bo‘lsa, yozing.\n/help - yordam"
    )

# /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🆘 Yordam:\nSavol yuboring va adminlardan javob oling.\n/info - ma'lumot\n/contact - bog‘lanish"
    )

# /info
async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ℹ️ Bu bot orqali siz savollarga tezkor javob olasiz.")

# /contact
async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📞 Biz bilan bog‘lanish: @nurbekbaxshilloyev")

# Savol qabul qilish
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    message = update.message.text

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✉️ Javob yozish", callback_data=f"answer:{user.id}:{update.message.message_id}")]
    ])

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"📩 Yangi savol:\n\n{message}\n\n👤 Foydalanuvchi: @{user.username or 'Nomalum'}",
                reply_markup=keyboard
            )
        except Exception as e:
            print(f"Xatolik adminga yuborishda: {e}")

    await update.message.reply_text("✅ Savolingiz adminga yuborildi. Tez orada javob olasiz.")

# Callback tugmalar
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("answer:"):
        parts = data.split(":")
        if len(parts) >= 2:
            context.user_data["answer_user_id"] = int(parts[1])
            await query.message.reply_text("✍️ Iltimos, javobingizni yozing:")

    elif data == "broadcast":
        context.user_data["is_broadcast"] = True
        await query.message.reply_text("📢 Yubormoqchi bo‘lgan umumiy xabaringizni yozing:")

# Javob yoki broadcast
async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = context.user_data.get("answer_user_id")
    is_broadcast = context.user_data.get("is_broadcast", False)
    text = update.message.text

    if is_broadcast:
        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=f"📢 Broadcast: {text}")
            except Exception as e:
                print(f"Broadcast yuborishda xatolik: {e}")
        context.user_data["is_broadcast"] = False
        await update.message.reply_text("📤 Broadcast yuborildi.")
        return

    if user_id:
        try:
            await context.bot.send_message(chat_id=user_id, text=f"📨 Sizning savolingizga javob:\n\n{text}")
            await update.message.reply_text("✅ Javob yuborildi.")
        except Exception as e:
            await update.message.reply_text(f"❌ Javob yuborilmadi: {e}")
        context.user_data["answer_user_id"] = None
    else:
        await update.message.reply_text("⚠️ Javob yuborish uchun savol tanlanmagan.")

# /broadcast
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMIN_IDS:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Yuborish", callback_data="broadcast")]
        ])
        await update.message.reply_text("📢 Broadcast yuborilsinmi?", reply_markup=keyboard)
    else:
        await update.message.reply_text("❌ Sizda ruxsat yo‘q.")

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
        filters.TEXT & ~filters.User(user_id=ADMIN_IDS), handle_message
    ))

    print("✅ Bot ishga tushdi.")
    app.run_polling()

if __name__ == "__main__":
    main()
