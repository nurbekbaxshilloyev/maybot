# importlar
import os
import logging
import asyncio
import sqlite3
from dotenv import load_dotenv
from aiohttp import web
from typing import List, Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)
BOT_TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(',') if id.strip().isdigit()]
logger.info(f"Loaded ADMIN_IDS: {ADMIN_IDS}")

# SQLite DB
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

# DB funksiyalar
def register_user(chat_id: int, username: str, first_name: str):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO users (chat_id, username, first_name) VALUES (?, ?, ?)',
              (chat_id, username or 'Unknown', first_name or 'Unknown'))
    conn.commit()
    conn.close()

def save_question(chat_id: int, question: str) -> int:
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

def get_question(question_id: int) -> Dict:
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''SELECT q.id, q.chat_id, q.question, u.username, u.first_name
                 FROM questions q JOIN users u ON q.chat_id = u.chat_id WHERE q.id = ?''', (question_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            'id': row[0], 'chat_id': row[1], 'question': row[2],
            'username': row[3], 'first_name': row[4]
        }
    return {}

def get_all_users() -> List[Dict]:
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT chat_id FROM users')
    users = [{'chat_id': row[0]} for row in c.fetchall()]
    conn.close()
    return users

# /start handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id, user.username, user.first_name)
    keyboard = [
        [KeyboardButton("Help"), KeyboardButton("Info")],
        [KeyboardButton("Contact")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Welcome to the bot. Send your question.", reply_markup=reply_markup)

# User sends a question
async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id in ADMIN_IDS:
        return
    text = update.message.text
    question_id = save_question(user.id, text)
    for admin_id in ADMIN_IDS:
        button = InlineKeyboardButton("Answer", callback_data=f"answer_{question_id}")
        keyboard = InlineKeyboardMarkup([[button]])
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"New question from @{user.username} ({user.first_name}):\n\n{text}",
            reply_markup=keyboard
        )
    await update.message.reply_text("Your question has been sent to the admins.")

# Admin clicks "Answer" or Broadcast
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    await query.answer()
    if user.id not in ADMIN_IDS:
        return

    data = query.data
    context.application.user_data.setdefault(user.id, {})

    if data.startswith("answer_"):
        qid = int(data.split("_")[1])
        context.application.user_data[user.id]['answering'] = qid
        await query.message.reply_text("Please type your answer.")

    elif data == "broadcast":
        context.application.user_data[user.id]['broadcast_mode'] = True
        await query.message.reply_text("Send the message to broadcast.")

# Admin sends response
async def handle_admin_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        return

    context.application.user_data.setdefault(user.id, {})
    user_data = context.application.user_data[user.id]

    if user_data.get("broadcast_mode"):
        for user_data_item in get_all_users():
            try:
                await context.bot.send_message(chat_id=user_data_item['chat_id'], text=update.message.text)
            except Exception as e:
                logger.error(f"Failed to broadcast to {user_data_item['chat_id']}: {e}")
        user_data.pop("broadcast_mode", None)
        await update.message.reply_text("Broadcast sent.")
        return

    qid = user_data.get("answering")
    if not qid:
        return

    answer = update.message.text
    question = get_question(qid)
    save_answer(qid, answer, user.id)

    await context.bot.send_message(chat_id=question['chat_id'], text=f"Admin's answer:\n\n{answer}")

    for admin_id in ADMIN_IDS:
        if admin_id != user.id:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"@{question['username']} ({question['first_name']})'s question was answered by @{user.username}:\n\nQ: {question['question']}\nA: {answer}"
            )

    user_data.pop("answering", None)
    await update.message.reply_text("Answer sent.")

# Broadcast command
async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMIN_IDS:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Start Broadcast", callback_data="broadcast")]])
        await update.message.reply_text("Click to start broadcast:", reply_markup=keyboard)

# Webhook & App
async def web_server(application):
    async def handle(request):
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_post('/webhook', handle)
    return app

async def send_admin_test(bot):
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text="Bot is running. You are registered as admin.")
        except Exception as e:
            logger.error(f"Failed to notify admin: {e}")

if __name__ == "__main__":
    init_db()
    port = int(os.getenv("PORT", 8000))

    async def main():
        application = Application.builder().token(BOT_TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("broadcast", broadcast))
        application.add_handler(CallbackQueryHandler(button_callback))
        application.add_handler(MessageHandler(filters.TEXT & filters.User(ADMIN_IDS), handle_admin_response))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question))

        await application.initialize()
        await application.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
        await send_admin_test(application.bot)
        app = await web_server(application)
        await application.start()
        await web._run_app(app, port=port)

    asyncio.run(main())
