import os
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 6459086003  # Faqat bitta admin
user_ids = set()  # Broadcast uchun foydalanuvchilar ro‘yxati

# /start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_ids.add(update.effective_user.id)
    await update.message.reply_text("Assalomu alaykum! Savollaringiz bo‘lsa, yozing.")

# /help komandasi
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🆘 Yordam:\nSavol yuboring va adminlardan javob oling.")

# /broadcast komandasi (faqat admin uchun)
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📢 Broadcast yuborish", callback_data="broadcast")]
        ])
        await update.message.reply_text("Broadcast yubormoqchimisiz?", reply_markup=keyboard)
    else:
        await update.message.reply_text("Sizda ruxsat yo‘q.")

# Oddiy foydalanuvchi xabari
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_ids.add(user.id)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✉️ Javob yozish", callback_data=f"answer:{user.id}")]
    ])

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"📩 Yangi xabar:\n\n{update.message.text}\n\n👤 @{user.username or 'Nomaʼlum'} (ID: {user.id})",
        reply_markup=keyboard
    )

    await update.message.reply_text("✅ Savolingiz adminga yuborildi. Tez orada javob olasiz.")

# Callback handler
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("answer:"):
        user_id = int(data.split(":")[1])
        context.user_data["answer_user_id"] = user_id
        await query.message.reply_text("✍️ Iltimos, foydalanuvchiga yuboriladigan javobni yozing:")
    elif data == "broadcast":
        context.user_data["is_broadcast"] = True
        await query.message.reply_text("📨 Broadcast xabarini kiriting:")

# Admin javobi
async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = context.user_data.get("answer_user_id")
    is_broadcast = context.user_data.get("is_broadcast", False)
    text = update.message.text

    if is_broadcast:
        for uid in user_ids:
            try:
                await context.bot.send_message(chat_id=uid, text=f"📢 {text}")
            except Exception as e:
                print(f"⚠️ Broadcast xato: {e}")
        await update.message.reply_text("✅ Broadcast yuborildi.")
        context.user_data["is_broadcast"] = False
        return

    if user_id:
        try:
            await context.bot.send_message(chat_id=user_id, text=f"📨 Admin javobi:\n\n{text}")
            await update.message.reply_text("✅ Javob foydalanuvchiga yuborildi.")
        except Exception as e:
            await update.message.reply_text(f"❌ Xatolik: {e}")
        context.user_data["answer_user_id"] = None
    else:
        await update.message.reply_text("⚠️ Javob yuboriladigan foydalanuvchi aniqlanmadi.")

# Main
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CallbackQueryHandler(handle_callback))

    app.add_handler(MessageHandler(filters.TEXT & filters.User(user_id=ADMIN_ID), handle_admin_reply))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message))

    print("✅ Bot ishga tushdi.")
    app.run_polling()

if __name__ == "__main__":
    main()
