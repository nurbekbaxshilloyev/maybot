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
ADMIN_IDS = [int(i) for i in os.environ.get("ADMIN_IDS", "").split(",") if i.strip().isdigit()]

# Global holat saqlovchilar
pending_answers = {}  # admin_id -> user_id
is_broadcast = {}     # admin_id -> True/False

# /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Assalomu alaykum! Savollaringiz bo‘lsa, yozing.\n/help - yordam")

# /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🆘 Yordam:\nSavol yuboring va adminlardan javob oling.\n/info - ma'lumot\n/contact - bog‘lanish")

# /info
async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("ℹ️ Bu bot orqali siz savollarga tezkor javob olasiz.")

# /contact
async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📞 Bog‘lanish: @nurbekbaxshilloyev")

# Savolni qabul qilish
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    message = update.message.text

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✉️ Javob yozish", callback_data=f"answer:{user.id}")]
    ])

    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"📩 Yangi savol:\n\n{message}\n\n👤 @{user.username or user.full_name}",
                reply_markup=keyboard
            )
        except Exception as e:
            print(f"Admin {admin_id} ga yuborishda xato: {e}")

    await update.message.reply_text("✅ Savolingiz adminga yuborildi.")

# Callback tugma ishlovchisi
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    admin_id = query.from_user.id

    if data.startswith("answer:"):
        user_id = int(data.split(":")[1])
        pending_answers[admin_id] = user_id
        await query.message.reply_text("✍️ Javobingizni yozing:")

    elif data == "broadcast":
        is_broadcast[admin_id] = True
        await query.message.reply_text("📢 Xabar matnini kiriting:")

# Admin xabari uchun ishlovchi
async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_id = update.message.from_user.id
    text = update.message.text

    # Broadcast
    if is_broadcast.get(admin_id):
        del is_broadcast[admin_id]
        user_ids = set(pending_answers.values())
        for uid in user_ids:
            try:
                await context.bot.send_message(chat_id=uid, text=f"📢 {text}")
            except Exception as e:
                print(f"❌ Broadcast foydalanuvchiga yuborilmadi ({uid}): {e}")
        await update.message.reply_text("✅ Broadcast yuborildi.")
        return

    # Javob
    user_id = pending_answers.get(admin_id)
    if user_id:
        try:
            await context.bot.send_message(chat_id=user_id, text=f"📨 Admin javobi:\n\n{text}")
            await update.message.reply_text("✅ Javob yuborildi.")
        except Exception as e:
            await update.message.reply_text(f"❌ Xatolik: {e}")
        del pending_answers[admin_id]
    else:
        await update.message.reply_text("⚠️ Javob yuborish uchun foydalanuvchi tanlanmagan.")

# /broadcast komandasi
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMIN_IDS:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Broadcast yuborish", callback_data="broadcast")]
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

    # Avval adminning javoblari uchun
    app.add_handler(MessageHandler(filters.TEXT & filters.User(user_id=ADMIN_IDS), handle_admin_reply))
    # Foydalanuvchilarning xabarlari uchun
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Bot ishga tushdi.")
    app.run_polling()

if __name__ == "__main__":
    main()
