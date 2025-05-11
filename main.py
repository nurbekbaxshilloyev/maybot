import os
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 6459086003  # faqat bitta admin

bot = telebot.TeleBot(BOT_TOKEN)
user_messages = {}

# /start komandasi
@bot.message_handler(commands=['start'])
def start_handler(message):
    bot.send_message(message.chat.id, "Assalomu alaykum! Savolingizni yuboring.")

# Foydalanuvchi savolini qabul qilish
@bot.message_handler(func=lambda message: True)
def user_message_handler(message):
    if message.chat.id != ADMIN_ID:
        user_messages[message.message_id] = message.chat.id
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("Javob berish", callback_data=f"answer:{message.message_id}"))
        bot.send_message(ADMIN_ID, f"Yangi xabar:\n\n{message.text}", reply_markup=markup)

# Admin tugmani bosganda
@bot.callback_query_handler(func=lambda call: call.data.startswith("answer:"))
def answer_callback(call):
    message_id = int(call.data.split(":")[1])
    msg = bot.send_message(call.message.chat.id, "Javobni yozing:")
    bot.register_next_step_handler(msg, process_admin_reply, message_id)

# Admin javob yozganda
def process_admin_reply(message, message_id):
    user_id = user_messages.get(message_id)
    if user_id:
        bot.send_message(user_id, f"Admin javobi:\n{message.text}")
        bot.send_message(ADMIN_ID, "Javob yuborildi.")
    else:
        bot.send_message(ADMIN_ID, "Xatolik: foydalanuvchi topilmadi.")

# Adminga broadcast komanda
@bot.message_handler(commands=['broadcast'])
def broadcast_handler(message):
    if message.chat.id == ADMIN_ID:
        msg = bot.send_message(message.chat.id, "Broadcast xabarni yozing:")
        bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    sent_count = 0
    for user_id in set(user_messages.values()):
        try:
            bot.send_message(user_id, f"📢 {message.text}")
            sent_count += 1
        except:
            pass
    bot.send_message(ADMIN_ID, f"Broadcast yuborildi. {sent_count} foydalanuvchiga.")

# Botni ishga tushirish
print("✅ Bot ishga tushdi.")
bot.polling(none_stop=True)
