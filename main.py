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

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load .env
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
ADMIN_IDS = [int(id) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip().isdigit()]

# DB Init
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

def register_user(chat_id, username, first_name):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO users (chat_id, username, first_name) VALUES (?, ?, ?)',
              (chat_id, username or 'Unknown', first_name or 'Unknown'))
    conn.commit()
    conn.close()

def save_question(chat_id, question):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('INSERT INTO questions (chat_id, question) VALUES (?, ?)', (chat_id, question))
    conn.commit()
    qid = c.lastrowid
    conn.close()
    return qid

def save_answer(question_id, answer, answered_by):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('UPDATE questions SET answer = ?, answered_by = ? WHERE id = ?',
              (answer, answered_by, question_id))
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

# Telegram Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id, user.username, user.first_name)
    await update.message.reply_text(
        'Welcome to LawSupportBot! Send your legal questions, and our admins will respond soon.'
    )

async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id in ADMIN_IDS:
        return
    question = update.message.text
    register_user(user.id, user.username, user.first_name)
    question_id = save_question(user.id, question)

    for admin_id in ADMIN_IDS:
        keyboard = [[InlineKeyboardButton("Answer", callback_data=f"answer_{question_id}")]]
        markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"New question from @{user.username}:\n\n{question}",
            reply_markup=markup
        )
    await update.message.reply_text('Your question has been sent to admins.')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    await query.answer()

    if user.id not in ADMIN_IDS:
        await query.message.reply_text('Admins only.')
        return

    if query.data.startswith("answer_"):
        question_id = int(query.data.split("_")[1])
        context.user_data['answering_question_id'] = question_id
        await query.message.reply_text('Please type your answer.')

    elif query.data == 'broadcast':
        context.user_data['broadcast_mode'] = True
        await query.message.reply_text('Send the message to broadcast.')

async def handle_admin_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        return

    if context.user_data.get('broadcast_mode'):
        msg = update.message.text
        users = get_all_users()
        for u in users:
            try:
                await context.bot.send_message(chat_id=u['chat_id'], text=msg)
            except Exception as e:
                logger.error(f"Failed to send to {u['chat_id']}: {e}")
        context.user_data.pop('broadcast_mode')
        await update.message.reply_text('Broadcast sent.')
        return

    qid = context.user_data.get('answering_question_id')
    if not qid:
        return
    answer = update.message.text
    question = get_question(qid)
    if not question:
        await update.message.reply_text('Question not found.')
        return

    save_answer(qid, answer, user.id)
    await context.bot.send_message(chat_id=question['chat_id'], text=f"Admin reply:\n{answer}")
    await update.message.reply_text('Answer sent.')
    context.user_data.pop('answering_question_id', None)

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return await update.message.reply_text('Admins only.')
    markup = InlineKeyboardMarkup([[InlineKeyboardButton("Start", callback_data="broadcast")]])
    await update.message.reply_text("Click to start broadcast:", reply_markup=markup)

# Webhook endpoint
async def telegram_webhook(request):
    try:
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
    return web.Response()

# Health check
async def health_check(request):
    return web.Response(text="LawSupportBot is alive")

# Web Server
async def web_server():
    app = web.Application()
    app.add_routes([
        web.get("/", health_check),
        web.post("/webhook", telegram_webhook),
    ])
    return app

# App init
async def init():
    global application
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('broadcast', broadcast))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_response))

    await application.bot.set_webhook(f"{WEBHOOK_URL}/webhook")
    runner = web.AppRunner(await web_server())
    await runner.setup()
    site = web.TCPSite(runner, port=int(os.environ.get('PORT', 8000)))
    await site.start()
    logger.info("Server started on Webhook mode.")

# Entry point
if __name__ == '__main__':
    import asyncio
    asyncio.run(init())
