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

# Loglar
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# Environment o'qish
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_IDS = [int(i) for i in os.getenv("ADMIN_IDS", "").split(",") if i.strip().isdigit()]
PORT = int(os.getenv('PORT', '8080'))
WEBHOOK_URL = os.getenv('WEBHOOK_URL')  # Masalan: https://yourproject.up.railway.app

# SQLite baza
def init_db():
    conn = sqlite3.connect("users.db")
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
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO users (chat_id, username, first_name) VALUES (?, ?, ?)",
              (chat_id, username or 'Unknown', first_name or 'Unknown'))
    conn.commit()
    conn.close()

def save_question(chat_id: int, question: str):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("INSERT INTO questions (chat_id, question) VALUES (?, ?)", (chat_id, question))
    conn.commit()
    question_id = c.lastrowid
    conn.close()
    return question_id

def save_answer(question_id: int, answer: str, answered_by: int):
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("UPDATE questions SET answer = ?, answered_by = ? WHERE id = ?", 
              (answer, answered_by, question_id))
    conn.commit()
    conn.close()

def get_all_users() -> List[Dict]:
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT chat_id, username, first_name FROM users")
    users = [{'chat_id': row[0], 'username': row[1], 'first_name': row[2]} for row in c.fetchall()]
    conn.close()
    return users

def get_question(question_id: int) -> Dict:
    conn = sqlite3.connect("users.db")
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

# Telegram komandalar
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id, user.username, user.first_name)
    await update.message.reply_text('Welcome to LawSupportBot! Send your legal questions.')

async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id in ADMIN_IDS:
        return
    register_user(user.id, user.username, user.first_name)
    question = update.message.text
    question_id = save_question(user.id, question)
    for admin_id in ADMIN_IDS:
        keyboard = [[InlineKeyboardButton("Answer", callback_data=f"answer_{question_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await context.bot.send_message(
            chat_id=admin_id,
            text=f"New question from @{user.username}:\n\n{question}",
            reply_markup=reply_markup
        )
    await update.message.reply_text('Your question was sent to admins.')

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    await query.answer()
    if user.id not in ADMIN_IDS:
        await query.message.reply_text("Admins only.")
        return
    if query.data.startswith('answer_'):
        question_id = int(query.data.split('_')[1])
        context.user_data['answering_question_id'] = question_id
        await query.message.reply_text("Please type your answer.")

    elif query.data == "broadcast":
        await query.message.reply_text("Send broadcast message.")
        context.user_data["broadcast_mode"] = True

async def handle_admin_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        return

    if context.user_data.get("broadcast_mode"):
        message = update.message.text
        users = get_all_users()
        for u in users:
            try:
                await context.bot.send_message(chat_id=u['chat_id'], text=message)
            except Exception as e:
                logger.warning(f"Error sending to {u['chat_id']}: {e}")
        await update.message.reply_text("Broadcast sent.")
        context.user_data.pop("broadcast_mode", None)
        return

    question_id = context.user_data.get("answering_question_id")
    if not question_id:
        return
    answer = update.message.text
    question = get_question(question_id)
    if not question:
        await update.message.reply_text("Question not found.")
        return
    save_answer(question_id, answer, user.id)
    await context.bot.send_message(chat_id=question["chat_id"], text=f"Admin's answer:\n\n{answer}")
    await update.message.reply_text("Answer sent.")
    context.user_data.pop("answering_question_id", None)

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("Admins only.")
        return
    keyboard = [[InlineKeyboardButton("Start Broadcast", callback_data="broadcast")]]
    await update.message.reply_text("Click to broadcast.", reply_markup=InlineKeyboardMarkup(keyboard))

# Webhook endpoint
async def telegram_webhook(request):
    data = await request.json()
    await request.app['application'].update_queue.put(Update.de_json(data, request.app['application'].bot))
    return web.Response()

# Web server
async def web_server(application: Application):
    app = web.Application()
    app['application'] = application
    app.router.add_post(f"/webhook/{BOT_TOKEN}", telegram_webhook)
    app.router.add_get("/", lambda request: web.Response(text="LawSupportBot is running"))
    return app

# Botni ishga tushirish
async def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("broadcast", broadcast))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_response))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_question))

    await application.bot.set_webhook(f"{WEBHOOK_URL}/webhook/{BOT_TOKEN}")

    app = await web_server(application)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()

    logging.info(f"Webhook started on port {PORT}")
    await application.start()
    await application.updater.start_polling()  # Needed for internal queue
    await application.updater.idle()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
