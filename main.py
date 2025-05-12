import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 6459086003  # O'zgartiring

user_questions = {}  # user_id -> xabar

network_buttons = [
    [InlineKeyboardButton("Item 1", callback_data="item1")],
    [InlineKeyboardButton("Item 2", callback_data="item2")],
    [InlineKeyboardButton("Item 3", callback_data="item3")],
]


# /start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["stage"] = "register"
    await update.message.reply_text("Boshlash uchun tugmani bosing:",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("-->", callback_data="register")]])
    )


# Bosqichlar orasida yurish
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()
    stage = context.user_data.get("stage")

    if data == "register":
        context.user_data["stage"] = "network"
        await query.message.reply_text("Tarmoqni tanlang:",
            reply_markup=InlineKeyboardMarkup(network_buttons))

    elif data.startswith("item") and stage == "network":
        context.user_data["stage"] = "contract"
        context.user_data["selected_item"] = data
        await query.message.reply_text("Iltimos, matnni yuboring:")

    elif data.startswith("answer:"):
        target_id = int(data.split(":")[1])
        context.user_data["reply_to_user"] = target_id
        await query.message.reply_text("✍️ Foydalanuvchiga yuboriladigan javobni yozing.")

    elif data == "broadcast":
        context.user_data["broadcast_mode"] = True
        await query.message.reply_text("📢 Broadcast matnini yozing.")


# Foydalanuvchi yoki admin xabari
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    text = update.message.text

    # Admin xabari — javob yoki broadcast
    if user_id == ADMIN_ID:
        reply_id = context.user_data.get("reply_to_user")
        is_broadcast = context.user_data.get("broadcast_mode", False)

        if is_broadcast:
            for uid in user_questions.keys():
                try:
                    await context.bot.send_message(chat_id=uid, text=f"📢 {text}")
                except:
                    pass
            await update.message.reply_text("✅ Broadcast yuborildi.")
            context.user_data["broadcast_mode"] = False
            return

        if reply_id:
            try:
                await context.bot.send_message(chat_id=reply_id, text=f"📨 Admindan:\n\n{text}")
                await update.message.reply_text("✅ Javob yuborildi.")
            except Exception as e:
                await update.message.reply_text(f"❌ Xatolik: {e}")
            context.user_data["reply_to_user"] = None
            return

        await update.message.reply_text("⚠️ Javob yuborish uchun foydalanuvchi tanlanmagan.")
        return

    # Oddiy foydalanuvchi — bosqichli forma
    stage = context.user_data.get("stage")
    if stage == "contract":
        selected = context.user_data.get("selected_item", "Noma'lum")
        msg = f"🆕 Yangi so'rov:\nTanlov: {selected}\nMatn: {text}\n\n👤 {update.message.from_user.full_name} ({user_id})"

        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✉️ Javob yozish", callback_data=f"answer:{user_id}")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]
        ])

        await context.bot.send_message(chat_id=ADMIN_ID, text=msg, reply_markup=keyboard)
        await update.message.reply_text("✅ Javobingiz adminga yuborildi.")
        user_questions[user_id] = msg
        context.user_data.clear()
    else:
        await update.message.reply_text("Iltimos, /start bosib boshlang.")


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.TEXT, handle_message))
    print("✅ Bot ishga tushdi.")
    app.run_polling()


if __name__ == "__main__":
    main()
