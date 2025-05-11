import telebot
from telebot import types

API_TOKEN = 'YOUR_TELEGRAM_BOT_TOKEN_HERE'  # BotFather’dan olingan tokenni yozing
ADMIN_ID = 6459086003

bot = telebot.TeleBot(API_TOKEN)
users = set()  # Foydalanuvchilar ID larini saqlash uchun

# /start komandasi
@bot.message_handler(commands=['start'])
def handle_start(message):
    users.add(message.chat.id)
    bot.send_message(message.chat.id,
                     "Assalomu alaykum! Savolingizni yozing, biz uni adminga jo'natamiz. "
                     "Yordam uchun /help buyrug'idan foydalaning.")

# /help komandasi
@bot.message_handler(commands=['help'])
def handle_help(message):
    bot.send_message(message.chat.id,
                     "/start - salomlashuv xabari\n"
                     "/info - bot haqida ma'lumot\n"
                     "/contact - admin bilan aloqa\n"
                     "/broadcast - (admin uchun) barcha foydalanuvchilarga xabar")

# /info komandasi
@bot.message_handler(commands=['info'])
def handle_info(message):
    bot.send_message(message.chat.id,
                     "Bu bot foydalanuvchilarning savollarini adminga yuborish va admin javobini qaytarish uchun mo'ljallangan.")

# /contact komandasi
@bot.message_handler(commands=['contact'])
def handle_contact(message):
    bot.send_message(message.chat.id,
                     "Admin Telegram ID: 6459086003")

# /broadcast komandasi (faqat admin uchun)
@bot.message_handler(commands=['broadcast'])
def handle_broadcast(message):
    if message.from_user.id != ADMIN_ID:
        return
    msg = bot.send_message(ADMIN_ID, "Jamoaviy xabar matnini kiriting:")
    bot.register_next_step_handler(msg, broadcast_send)

def broadcast_send(message):
    text = message.text
    for user_id in list(users):
        try:
            bot.send_message(user_id, text)
        except Exception:
            pass

# Foydalanuvchidan kelgan xabarlarni adminga yuborish
@bot.message_handler(func=lambda m: m.text is not None and m.from_user.id != ADMIN_ID)
def forward_to_admin(message):
    users.add(message.chat.id)
    # Inline tugma yaratish
    markup = types.InlineKeyboardMarkup()
    btn = types.InlineKeyboardButton("Javob berish", callback_data=f"answer_{message.chat.id}")
    markup.add(btn)
    # Adminga xabar yuborish
    bot.send_message(ADMIN_ID,
                     f"Foydalanuvchi {message.from_user.first_name} (ID: {message.chat.id}) savol berdi:\n{message.text}",
                     reply_markup=markup)

# Adminning "Javob berish" tugmasi bosilganda callback
@bot.callback_query_handler(func=lambda call: call.data and call.data.startswith("answer_"))
def callback_answer(call):
    user_id = int(call.data.split("_")[1])
    msg = bot.send_message(ADMIN_ID, "Javob matnini kiriting:")
    bot.register_next_step_handler(msg, send_answer_to_user, user_id)

def send_answer_to_user(message, user_id):
    bot.send_message(user_id, f"Admindan javob: {message.text}")
    bot.send_message(ADMIN_ID, "Javob foydalanuvchiga yuborildi.")

# Botni polling rejimida ishga tushirish (webhook o‘rnatilmaydi)
if __name__ == '__main__':
    bot.polling(none_stop=True)
