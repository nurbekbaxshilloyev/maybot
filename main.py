import os
import logging
import asyncio
import sqlite3
from typing import List, Dict
from dotenv import load_dotenv
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ContextTypes,
    filters
)

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
ADMIN_IDS = [int(id) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip().isdigit()]
logger.info(f"Loaded ADMIN_IDS: {ADMIN_IDS}")

# SQLite DB setup
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

def register_user(chat_id: int, username: str, first_name: str):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO users (chat_id, username, first_name) VALUES (?, ?, ?)',
              (chat_id, username or 'Unknown', first_name or 'Unknown'))
    conn.commit()
    conn.close()

def save_question(chat_id: int, question: str):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('INSERT INTO questions (chat_id, question) VALUES (?, ?)', (chat_id, question))
    conn.commit()
    question_id = c.lastrowid
    conn.close()
    return question_id

def save_answer(question_id: int, answer: str, answered_by: int):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('UPDATE questions SET answer = ?, answered_by = ? WHERE id = ?', (answer, answered_by, question_id))
    conn.commit()
    conn.close()

def get_all_users() -> List[Dict]:
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT chat_id, username, first_name FROM users')
    users = [{'chat_id': row[0], 'username': row[1], 'first_name': row[2]} for row in c.fetchall()]
    conn.close()
    return users

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

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    register_user(user.id, user.username, user.first_name)
    keyboard = [
        [KeyboardButton("Info"), KeyboardButton("Help")],
        [KeyboardButton("Contact")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text('Welcome to LawSupportBot! Send your legal questions.', reply_markup=reply_markup)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('Send your legal question and an admin will reply as soon as possible.')

async def info_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('LawSupportBot connects you with legal experts quickly and efficiently.')

async def contact_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text('You can contact us at example@example.com or call +998 90 000 00 00.')

async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id in ADMIN_IDS:
        return
    question = update.message.text
    register_user(user.id, user.username, user.first_name)
    question_id = save_question(user.id, question)
    for admin_id in ADMIN_IDS:
        keyboard = [[InlineKeyboardButton("Answer", callback_data=f"answer_{question_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"New question from @{user.username or 'NoUsername'} ({user.first_name}):\n\n{question}",
            reply_markup=reply_markup
        )
    await update.message.reply_text('Your question has been sent to the admins.')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await query.message.reply_text('Admins only.')
        return
    data = query.data
    if data.startswith('answer_'):
        question_id = int(data.split('_')[1])
        context.user_data['answering_question_id'] = question_id
        await query.message.reply_text('Please type your answer.')
    elif data == 'broadcast':
        context.user_data['broadcast_mode'] = True
        await query.message.reply_text('Type the message to broadcast:')

async def handle_admin_response(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        return
    if context.user_data.get('broadcast_mode'):
        message = update.message.text
        users = get_all_users()
        for u in users:
            try:
                await context.bot.send_message(chat_id=u['chat_id'], text=message)
            except Exception as e:
                logger.error(f"Failed to send broadcast to {u['chat_id']}: {e}")
        await update.message.reply_text(f'Message broadcast to {len(users)} users.')
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
    await context.bot.send_message(chat_id=question['chat_id'], text=f"Answer from admin:\n\n{answer}")
    for admin_id in [aid for aid in ADMIN_IDS if aid != user.id]:
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"Question from @{question['username']} ({question['first_name']}) answered by @{user.username}:\n\nQuestion: {question['question']}\nAnswer: {answer}"
        )
    await update.message.reply_text('Answer sent.')
    context.user_data.pop('answering_question_id', None)

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text('Only for admins.')
        return
    keyboard = [[InlineKeyboardButton("Start Broadcast", callback_data="broadcast")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Click to start broadcast.', reply_markup=reply_markup)

async def web_server(application):
    async def handle_webhook(request):
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return web.Response(text="OK")

    async def health_check(request):
        return web.Response(text="Bot is running.")

    app = web.Application()
    app.add_routes([web.post('/webhook', handle_webhook), web.get('/', health_check)])
    return app

async def send_admin_test(bot):
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text="Bot is running and you are registered as admin.")
        except Exception as e:
            logger.error(f"Admin test message failed: {e}")

# Run app
if __name__ == '__main__':
    init_db()
    port = int(os.getenv('PORT', 8000))

    async def main():
        application = Application.builder().token(BOT_TOKEN).build()

        application.add_handler(CommandHandler('start', start))
        application.add_handler(CommandHandler('help', help_command))
        application.add_handler(CommandHandler('info', info_command))
        application.add_handler(CommandHandler('contact', contact_command))
        application.add_handler(CommandHandler('broadcast', broadcast))
        application.add_handler(CallbackQueryHandler(button_callback))
        application.add_handler(MessageHandler(filters.TEXT & filters.User(ADMIN_IDS), handle_admin_response))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.User(ADMIN_IDS), handle_question))

        await application.initialize()
        await application.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
        await send_admin_test(application.bot)
        app = await web_server(application)
        await application.start()
        await web._run_app(app, port=port)

    asyncio.run(main())
