import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv()

# Bot tokenini olish
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi. .env faylida BOT_TOKEN ni sozlang.")

# Admin ID va foydalanuvchilar ro'yxati
ADMIN_ID = 6459086003
user_ids = set()

# /start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_ids.add(user_id)
    await update.message.reply_text("Assalomu alaykum! Savollaringiz bo‘lsa, yozing.")
    print(f"Foydalanuvchi {user_id} /start komandasini ishlatdi.")

# /help komandasi
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🆘 Yordam:\nSavol yuboring va adminlardan javob oling.")

# /broadcast komandasi (faqat admin uchun)
async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Sizda ruxsat yo‘q.")
        return

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("📢 Broadcast yuborish", callback_data="broadcast")]]
    )
    await update.message.reply_text("Broadcast yubormoqchimisiz?", reply_markup=keyboard)

# Oddiy foydalanuvchi xabari
async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_ids.add(user.id)

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("✉️ Javob yozish", callback_data=f"answer:{user.id}")]]
    )

    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"📩 Yangi xabar:\n\n{update.message.text}\n\n👤 @{user.username or 'Nomaʼlum'} (ID: {user.id})",
            reply_markup=keyboard,
        )
        await update.message.reply_text("✅ Savolingiz adminga yuborildi. Tez orada javob olasiz.")
    except Exception as e:
        print(f"Foydalanuvchi xabarini yuborishda xato: {e}")
        await update.message.reply_text("❌ Xatolik yuz berdi. Iltimos, qayta urinib ko‘ring.")

# Callback query handler
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()  # Callback query'ga javob berish
    data = query.data

    print(f"Callback qabul qilindi: {data}")  # Debug uchun log

    try:
        if data.startswith("answer:"):
            user_id = int(data.split(":")[1])
            context.user_data["answer_user_id"] = user_id
            await query.message.reply_text("✍️ Iltimos, foydalanuvchiga yuboriladigan javobni yozing:")
        elif data == "broadcast":
            context.user_data["is_broadcast"] = True
            await query.message.reply_text("📨 Broadcast xabarini kiriting:")
        else:
            await query.message.reply_text("⚠️ Noma'lum callback.")
    except Exception as e:
        print(f"Callback ishlov berishda xato: {e}")
        await query.message.reply_text("❌ Xatolik yuz berdi.")

# Admin javobi
async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    user_id = context.user_data.get("answer_user_id")
    is_broadcast = context.user_data.get("is_broadcast", False)
    text = update.message.text

    try:
        if is_broadcast:
            success_count = 0
            for uid in user_ids:
                try:
                    await context.bot.send_message(chat_id=uid, text=f"📢 {text}")
                    success_count += 1
                except Exception as e:
                    print(f"Broadcast xatosi (ID: {uid}): {e}")
            await update.message.reply_text(f"✅ Broadcast {success_count} foydalanuvchiga yuborildi.")
            context.user_data["is_broadcast"] = False
        elif user_id:
            await context.bot.send_message(chat_id=user_id, text=f"📨 Admin javobi:\n\n{text}")
            await update.message.reply_text("✅ Javob foydalanuvchiga yuborildi.")
            context.user_data["answer_user_id"] = None
        else:
            await update.message.reply_text("⚠️ Javob yuboriladigan foydalanuvchi aniqlanmadi.")
    except Exception as e:
        print(f"Admin javobida xato: {e}")
        await update.message.reply_text(f"❌ Xatolik: {e}")

# Main funksiya
def main():
    try:
        app = ApplicationBuilder().token(BOT_TOKEN).build()

        # Handler'larni qo'shish
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("help", help_command))
        app.add_handler(CommandHandler("broadcast", broadcast_command))
        app.add_handler(CallbackQueryHandler(handle_callback))
        app.add_handler(MessageHandler(filters.TEXT & filters.User(user_id=ADMIN_ID), handle_admin_reply))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message))

        print("✅ Bot ishga tushdi.")
        app.run_polling(allowed_updates=Update.ALL_TYPES)  # Barcha yangilanishlarni qabul qilish
    except Exception as e:
        print(f"Botni ishga tushirishda xato: {e}")

if __name__ == "__main__":
    main()
