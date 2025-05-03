import os
import logging
import asyncio
import sqlite3
from dotenv import load_dotenv
from aiohttp import web
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters, DictPersistence
)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL")
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(",") if id.strip().isdigit()]
PORT = int(os.getenv("PORT", 8000))

# Database init
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
    question_id = c.lastrowid
    conn.close()
    return question_id

def save_answer(question_id, answer, admin_id):
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('UPDATE questions SET answer = ?, answered_by = ? WHERE id = ?', (answer, admin_id, question_id))
    conn.commit()
    conn.close()

def get_question(question_id):
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

def get_all_users():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT chat_id FROM users')
    users = [{'chat_id': row[0]} for row in c.fetchall()]
    conn.close()
    return users

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id, user.username, user.first_name)
    keyboard = [
        [KeyboardButton("Help"), KeyboardButton("Info")],
        [KeyboardButton("Contact")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Welcome! Please send your question.", reply_markup=reply_markup)

async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = update.message.text.lower()

    if text == "help":
        await update.message.reply_text("This bot forwards your questions to admins. Just send your message.")
        return
    elif text == "info":
        await update.message.reply_text("This is a support bot. Admins will respond to your question shortly.")
        return
    elif text == "contact":
        await update.message.reply_text("Contact us at support@example.com")
        return

    if user.id in ADMIN_IDS:
        return

    question_id = save_question(user.id, update.message.text)
    for admin_id in ADMIN_IDS:
        button = InlineKeyboardButton("Answer", callback_data=f"answer_{question_id}")
        keyboard = InlineKeyboardMarkup([[button]])
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"New question from @{user.username} ({user.first_name}):\n\n{update.message.text}",
            reply_markup=keyboard
        )
    await update.message.reply_text("Your question has been sent to the admins.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    await query.answer()

    if user.id not in ADMIN_IDS:
        return

    data = query.data
    chat_data = context.chat_data

    if data.startswith("answer_"):
        question_id = int(data.split("_")[1])
        chat_data["answering"] = question_id
        await query.message.reply_text("Please type your answer to the question.")

    elif data == "broadcast":
        chat_data["broadcast_mode"] = True
        await query.message.reply_text("Send the message to broadcast to all users.")

async def handle_admin_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_data = context.chat_data

    if chat_data.get("broadcast_mode"):
        for u in get_all_users():
            try:
                await context.bot.send_message(chat_id=u['chat_id'], text=update.message.text)
            except Exception as e:
                logger.error(f"Broadcast error: {e}")
        chat_data.pop("broadcast_mode", None)
        await update.message.reply_text("Broadcast sent.")
        return

    question_id = chat_data.get("answering")
    if not question_id:
        return

    answer = update.message.text
    question = get_question(question_id)
    if not question:
        await update.message.reply_text("Original question not found.")
        return

    save_answer(question_id, answer, user.id)
    await context.bot.send_message(chat_id=question['chat_id'], text=f"Admin's answer:\n\n{answer}")
    
    for admin_id in ADMIN_IDS:
        if admin_id != user.id:
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"@{question['username']} ({question['first_name']})'s question was answered:\n\nQ: {question['question']}\nA: {answer}"
            )
    chat_data.pop("answering", None)
    await update.message.reply_text("Answer sent.")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id in ADMIN_IDS:
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("Start Broadcast", callback_data="broadcast")]])
        await update.message.reply_text("Click below to start broadcast:", reply_markup=keyboard)

# Webhook server
async def web_server(app: Application):
    async def handler(request):
        data = await request.json()
        update = Update.de_json(data, app.bot)
        await app.process_update(update)
        return web.Response(text="OK")

    web_app = web.Application()
    web_app.router.add_post("/webhook", handler)
    return web_app

async def send_admin_notice(bot):
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text="Bot is running. You are registered as admin.")
        except Exception as e:
            logger.error(f"Admin notify failed: {e}")

# Main
if __name__ == "__main__":
    init_db()

    async def main():
        persistence = DictPersistence()
        app = Application.builder().token(BOT_TOKEN).persistence(persistence).build()

        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("broadcast", broadcast_command))
        app.add_handler(CallbackQueryHandler(button_callback))
        app.add_handler(MessageHandler(filters.TEXT & filters.User(ADMIN_IDS), handle_admin_response))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question))

        await app.initialize()
        await app.bot.set_webhook(url=f"{WEBHOOK_URL}/webhook")
        await send_admin_notice(app.bot)

        runner = web.AppRunner(await web_server(app))
        await runner.setup()
        site = web.TCPSite(runner, port=PORT)
        await site.start()

        logger.info("Bot is running with webhook...")
        await app.start()
        await asyncio.Event().wait()

    asyncio.run(main())
