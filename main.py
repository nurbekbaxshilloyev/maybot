import os
import telebot
from telebot import types

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = 6459086003

bot = telebot.TeleBot(BOT_TOKEN)
user_messages = {}

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.send_message(message.chat.id, "Assalomu alaykum! Savolingizni yuboring.")

@bot.message_handler(commands=['help', 'info', 'contact'])
def send_info(message):
    bot.send_message(message.chat.id, "Yordam kerakmi? Savolingizni yozing. Admin javob beradi.")

@bot.message_handler(func=lambda message: True, content_types=['text'])
def forward_to_admin(message):
    user_id = message.chat.id
    text = message.text
    user_messages[message.message_id] = user_id

    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton("Javob berish", callback_data=f"answer_{message.message_id}")
    markup.add(btn)

    bot.send_message(ADMIN_ID, f"📩 Yangi xabar:\n\n{text}\n\n🆔 User ID: {user_id}", reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data.startswith("answer_"))
def ask_reply(call):
    message_id = int(call.data.split("_")[1])
    bot.send_message(ADMIN_ID, f"Javobingizni yozing:", reply_markup=None)

    @bot.message_handler(func=lambda msg: msg.chat.id == ADMIN_ID)
    def get_admin_reply(msg):
        if message_id in user_messages:
            user_id = user_messages.pop(message_id)
            bot.send_message(user_id, f"📨 Admin javobi:\n\n{msg.text}")
            bot.send_message(ADMIN_ID, "✅ Javob yuborildi.")
        else:
            bot.send_message(ADMIN_ID, "❗ Xatolik: foydalanuvchi topilmadi.")

@bot.message_handler(commands=['broadcast'])
def handle_broadcast(message):
    if message.chat.id != ADMIN_ID:
        return
    bot.send_message(ADMIN_ID, "📢 Tarqatmoqchi bo‘lgan xabaringizni yozing:")

    @bot.message_handler(func=lambda m: m.chat.id == ADMIN_ID)
    def do_broadcast(msg):
        for user_id in list(user_messages.values()):
            try:
                bot.send_message(user_id, f"📢 E’lon:\n\n{msg.text}")
            except Exception:
                continue
        bot.send_message(ADMIN_ID, "✅ Xabar barcha foydalanuvchilarga yuborildi.")

bot.polling(none_stop=True)

