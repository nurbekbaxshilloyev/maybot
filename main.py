import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters,
)
from aiohttp import web
from dotenv import load_dotenv
import sqlite3
from typing import List, Dict

# Logging sozlamalari
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment variables yuklash
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(id) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip().isdigit()]

# Ma'lumotlar bazasini sozlash
def init_db():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        chat_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS questions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER,
        question TEXT,
        answer TEXT,
        answered_by INTEGER,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
    )''')
    conn.commit()
    conn.close()

# Foydalanuvchini ro'yxatdan o'tkazish
def register_user(chat_id: int, username: str, first_name: str):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO users (chat_id, username, first_name) VALUES (?, ?, ?)',
              (chat_id, username or 'Unknown', first_name or 'Unknown'))
    conn.commit()
    conn.close()

# Savolni saqlash
def save_question(chat_id: int, question: str):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('INSERT INTO questions (chat_id, question) VALUES (?, ?)', (chat_id, question))
    conn.commit()
    question_id = c.lastrowid
    conn.close()
    return question_id

# Javobni saqlash
def save_answer(question_id: int, answer: str, answered_by: int):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('UPDATE questions SET answer = ?, answered_by = ? WHERE id = ?', 
              (answer, answered_by, question_id))
    conn.commit()
    conn.close()

# Barcha foydalanuvchilarni olish
def get_all_users() -> List[Dict]:
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT chat_id, username, first_name FROM users')
    users = [{'chat_id': row[0], 'username': row[1], 'first_name': row[2]} for row in c.fetchall()]
    conn.close()
    return users

# Savol ma'lumotlarini olish
def get_question(question_id: int) -> Dict:
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''SELECT q.id, q.chat_id, q.question, q.answer, q.answered_by, u.username, u.first_name
                 FROM questions q JOIN users u ON q.chat_id = u.chat_id WHERE q.id = ?''', (question_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            'id': row[0], 'chat_id': row[1], 'question': row[2], 'answer': row[3],
            'answered_by': row[4], 'username': row[5], 'first_name': row[6]
        }
    return {}

# /start komandasi
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    register_user(user.id, user.username, user.first_name)
    await update.message.reply_text(
        'Welcome to LawSupportBot! Send your legal questions, and our admins will respond soon.'
    )

# Savol qabul qilish
async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id in ADMIN_IDS:
        return  # Adminlarning xabarlari savol sifatida qabul qilinmaydi
    
    question = update.message.text
    register_user(user.id, user.username, user.first_name)
    question_id = save_question(user.id, question)
    
    # Adminlarga savolni yuborish
    for admin_id in ADMIN_IDS:
        keyboard = [[InlineKeyboardButton("Answer", callback_data=f"answer_{question_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"New question from @{user.username} ({user.first_name}):\n\n{question}",
            reply_markup=reply_markup
        )
    
    await update.message.reply_text('Your question has been sent to the admins. You will receive a response soon.')

# Tugma bosilishi
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    await query.answer()
    
    if user.id not in ADMIN_IDS:
        await query.message.reply_text('This action is for admins only.')
        return
    
    data = query.data
    if data.startswith('answer_'):
        question_id = int(data.split('_')[1])
        context.user_data['answering_question_id'] = question_id
        await query.message.reply_text('Please type your answer to the question.')
    
    elif data == 'broadcast':
        await query.message.reply_text('Please type the message to broadcast to all users.')
        context.user_data['broadcast_mode'] = True

# Admin javobini qabul qilish
async def handle_admin_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        return
    
    if context.user_data.get('broadcast_mode'):
        message = update.message.text
        users = get_all_users()
        for user in users:
            try:
                await context.bot.send_message(chat_id=user['chat_id'], text=message)
            except Exception as e:
                logger.error(f"Failed to send broadcast to {user['chat_id']}: {e}")
        await update.message.reply_text(f'Broadcast sent to {len(users)} users.')
        context.user_data.pop('broadcast_mode', None)
        return
    
    question_id = context.user_data.get('answering_question_id')
    if not question_id:
        return
    
    answer = update.message.text
    question = get_question(question_id)
    if not question:
        await update.message.reply_text('Question not found.')
        return
    
    save_answer(question_id, answer, user.id)
    
    # Foydalanuvchiga javob yuborish
    await context.bot.send_message(
        chat_id=question['chat_id'],
        text=f"Answer from admin:\n\n{answer}"
    )
    
    # Boshqa adminga xabar berish
    other_admin_id = [aid for aid in ADMIN_IDS if aid != user.id]
    if other_admin_id:
        await context.bot.send_message(
            chat_id=other_admin_id[0],
            text=f"Question from @{question['username']} ({question['first_name']}) answered by @{user.username}:\n\n"
                 f"Question: {question['question']}\nAnswer: {answer}"
        )
    
    await update.message.reply_text('Answer sent to the user.')
    context.user_data.pop('answering_question_id', None)

# /broadcast komandasi (faqat adminlar uchun)
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text('This command is for admins only.')
        return
    
    keyboard = [[InlineKeyboardButton("Start Broadcast", callback_data="broadcast")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        'Click the button to start broadcasting a message to all users.',
        reply_markup=reply_markup
    )

# Veb-server (Railway.app uchun)
async def web_server():
    async def health_check(request):
        return web.Response(text="LawSupportBot is running")
    
    app = web.Application()
    app.add_routes([web.get('/', health_check)])
    return app

def main() -> None:
    # Ma'lumotlar bazasini ishga tushirish
    init_db()
    
    # Telegram botni sozlash
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Handlerlarni qo'shish
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('broadcast', broadcast))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_response))
    
    # Botni polling rejimida ishga tushirish
    application.run_polling()

if __name__ == '__main__':
    port = int(os.getenv('PORT', 8000))
    web.run_app(web_server(), port=port)
    main()