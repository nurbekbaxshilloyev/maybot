import os
import json
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

USERS_FILE = "users.json"
user_questions = {}  # foydalanuvchi ID -> savol matni

# --- USER ID saqlash funksiyalari ---
def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_users(user_ids):
    with open(USERS_FILE, "w") as f:
        json.dump(list(user_ids), f)

user_ids = load_users()

# --- START komandasi ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Assalomu alaykum! Savolingizni yozing.")

# --- HELP komandasi ---
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Savolingizni yozing. Admin sizga tez orada javob beradi.")

# --- Foydalanuvchi xabari ---
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    text = update.message.text
    user_id = user.id
    user_questions[user_id] = text

    if user_id not in user_ids:
        user_ids.add(user_id)
        save_users(user_ids)

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

# --- CALLBACK tugmalari ---
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

# --- Admin javobi yoki broadcast ---
async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = context.user_data.get("reply_to_user")
    is_broadcast = context.user_data.get("broadcast_mode", False)

    if is_broadcast:
        message = update.message.text
        context.user_data["broadcast_mode"] = False
        success, fail = 0, 0
        for uid in user_ids:
            try:
                await context.bot.send_message(chat_id=uid, text=f"📢 Broadcast:\n\n{message}")
                success += 1
            except Exception:
                fail += 1
        await update.message.reply_text(f"✅ Broadcast yuborildi.\n📬 Yuborildi: {success}\n❌ Xatolik: {fail}")
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

# --- MAIN ---
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
