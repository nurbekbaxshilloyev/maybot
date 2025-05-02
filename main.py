# Importlar
import os
import logging
import asyncio
import psycopg2
from datetime import datetime
from dotenv import load_dotenv
from aiohttp import web
from typing import List, Dict, Optional
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    KeyboardButton, 
    ReplyKeyboardMarkup
)
from telegram.ext import (
    Application, 
    CommandHandler, 
    MessageHandler,
    CallbackQueryHandler, 
    ContextTypes, 
    filters
)

# Logging sozlamalari
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Environment o'zgaruvchilari
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
ADMIN_IDS = [int(id) for id in os.getenv("ADMIN_IDS", "").split(',') if id.strip().isdigit()]
DATABASE_URL = os.getenv('DATABASE_URL')

# Database funksiyalari
def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Users jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            chat_id BIGINT PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            registered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_banned BOOLEAN DEFAULT FALSE
        )
    ''')
    
    # Questions jadvali
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id SERIAL PRIMARY KEY,
            chat_id BIGINT REFERENCES users(chat_id),
            question TEXT NOT NULL,
            answer TEXT,
            answered_by BIGINT REFERENCES users(chat_id),
            answered_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_answered BOOLEAN DEFAULT FALSE
        )
    ''')
    
    # Adminlar uchun qo'shimcha jadval
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS admin_settings (
            admin_id BIGINT PRIMARY KEY,
            can_broadcast BOOLEAN DEFAULT TRUE,
            can_ban_users BOOLEAN DEFAULT TRUE,
            last_activity TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized successfully")

def register_user(chat_id: int, username: str, first_name: str, last_name: str = None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO users (chat_id, username, first_name, last_name)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (chat_id) 
        DO UPDATE SET 
            username = EXCLUDED.username,
            first_name = EXCLUDED.first_name,
            last_name = EXCLUDED.last_name
    ''', (chat_id, username, first_name, last_name))
    
    conn.commit()
    conn.close()

def save_question(chat_id: int, question: str) -> int:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO questions (chat_id, question)
        VALUES (%s, %s)
        RETURNING id
    ''', (chat_id, question))
    
    question_id = cursor.fetchone()[0]
    conn.commit()
    conn.close()
    return question_id

def save_answer(question_id: int, answer: str, answered_by: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE questions
        SET answer = %s, answered_by = %s, answered_at = CURRENT_TIMESTAMP, is_answered = TRUE
        WHERE id = %s
        RETURNING chat_id, question
    ''', (answer, answered_by, question_id))
    
    result = cursor.fetchone()
    conn.commit()
    conn.close()
    
    if result:
        return {'chat_id': result[0], 'question': result[1]}
    return None

def get_question(question_id: int) -> Optional[Dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT q.id, q.chat_id, q.question, q.answer, 
               u.username, u.first_name, u.last_name,
               a.username as admin_username, a.first_name as admin_first_name
        FROM questions q
        JOIN users u ON q.chat_id = u.chat_id
        LEFT JOIN users a ON q.answered_by = a.chat_id
        WHERE q.id = %s
    ''', (question_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            'id': row[0],
            'chat_id': row[1],
            'question': row[2],
            'answer': row[3],
            'username': row[4],
            'first_name': row[5],
            'last_name': row[6],
            'admin_username': row[7],
            'admin_first_name': row[8]
        }
    return None

def get_all_users() -> List[Dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT chat_id, username, first_name, last_name
        FROM users
        WHERE is_banned = FALSE
    ''')
    
    users = [
        {
            'chat_id': row[0],
            'username': row[1],
            'first_name': row[2],
            'last_name': row[3]
        }
        for row in cursor.fetchall()
    ]
    
    conn.close()
    return users

def get_unanswered_questions() -> List[Dict]:
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT q.id, q.question, u.username, u.first_name, u.last_name
        FROM questions q
        JOIN users u ON q.chat_id = u.chat_id
        WHERE q.is_answered = FALSE
        ORDER BY q.created_at ASC
    ''')
    
    questions = [
        {
            'id': row[0],
            'question': row[1],
            'username': row[2],
            'first_name': row[3],
            'last_name': row[4]
        }
        for row in cursor.fetchall()
    ]
    
    conn.close()
    return questions

def ban_user(chat_id: int, admin_id: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE users
        SET is_banned = TRUE
        WHERE chat_id = %s
        RETURNING username, first_name
    ''', (chat_id,))
    
    result = cursor.fetchone()
    conn.commit()
    conn.close()
    
    if result:
        return {'username': result[0], 'first_name': result[1]}
    return None

# Bot funksiyalari
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    register_user(user.id, user.username, user.first_name, user.last_name)
    
    keyboard = [
        [KeyboardButton("Yordam"), KeyboardButton("Biz haqimizda")],
        [KeyboardButton("Admin bilan bog'lanish")]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Assalomu alaykum! Botimizga xush kelibsiz.\n\n"
        "Savollaringizni yuboring, adminlar javob berishadi.",
        reply_markup=reply_markup
    )

async def handle_question(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message
    
    # Adminlar uchun alohida handler
    if user.id in ADMIN_IDS:
        return
    
    # Foydalanuvchi banlanganligini tekshirish
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT is_banned FROM users WHERE chat_id = %s', (user.id,))
    is_banned = cursor.fetchone()
    conn.close()
    
    if is_banned and is_banned[0]:
        await message.reply_text("⚠️ Sizning profilingiz bloklangan. Adminlar bilan bog'laning.")
        return
    
    # Savolni saqlash
    question_id = save_question(user.id, message.text)
    
    # Adminlarga xabar yuborish
    for admin_id in ADMIN_IDS:
        try:
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("Javob berish", callback_data=f"answer_{question_id}"),
                    InlineKeyboardButton("Bloklash", callback_data=f"ban_{user.id}")
                ]
            ])
            
            await context.bot.send_message(
                chat_id=admin_id,
                text=f"📨 Yangi savol:\n\n"
                     f"👤 Foydalanuvchi: {user.full_name} (@{user.username if user.username else 'nomaʼlum'})\n"
                     f"🆔 ID: {user.id}\n"
                     f"📝 Savol:\n{message.text}",
                reply_markup=keyboard
            )
        except Exception as e:
            logger.error(f"Admin {admin_id} ga xabar yuborishda xato: {e}")
    
    await message.reply_text(
        "✅ Savolingiz qabul qilindi. Adminlar tez orada javob berishadi.\n\n"
        "Qo'shimcha savollar uchun shu yerda yozishingiz mumkin."
    )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user
    
    # Faqat adminlar uchun
    if user.id not in ADMIN_IDS:
        await query.answer("Sizda bunday amalni bajarish uchun ruxsat yo'q!")
        return
    
    await query.answer()
    data = query.data
    
    # Javob berish tugmasi
    if data.startswith("answer_"):
        question_id = int(data.split("_")[1])
        context.user_data['answering'] = question_id
        
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(
            chat_id=user.id,
            text=f"❓ Savol ID: {question_id}\n\n"
                 f"Javobingizni yuboring:",
            reply_to_message_id=query.message.message_id
        )
    
    # Bloklash tugmasi
    elif data.startswith("ban_"):
        user_id = int(data.split("_")[1])
        result = ban_user(user_id, user.id)
        
        if result:
            await query.edit_message_text(
                text=f"⛔️ Foydalanuvchi bloklandi:\n\n"
                     f"👤 {result['first_name']} (@{result['username']})\n"
                     f"🆔 {user_id}",
                reply_markup=None
            )
            await context.bot.send_message(
                chat_id=user_id,
                text="⚠️ Sizning profilingiz admin tomonidan bloklangan. "
                     "Agar bu xato deb hisoblasangiz, boshqa adminlar bilan bog'laning."
            )
        else:
            await query.edit_message_text(
                text="❌ Foydalanuvchi topilmadi yoki allaqachon bloklangan!",
                reply_markup=None
            )
    
    # Broadcast tugmasi
    elif data == "broadcast":
        context.user_data['broadcast_mode'] = True
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(
            chat_id=user.id,
            text="📢 Barcha foydalanuvchilarga yuboriladigan xabarni kiriting:",
            reply_to_message_id=query.message.message_id
        )

async def handle_admin_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.message
    
    if user.id not in ADMIN_IDS:
        return
    
    # Broadcast rejimi
    if context.user_data.get("broadcast_mode"):
        users = get_all_users()
        total = len(users)
        success = 0
        
        # Progress xabari
        progress_msg = await message.reply_text(f"📤 Xabar yuborilmoqda... 0/{total}")
        
        for i, user_data in enumerate(users, 1):
            try:
                await context.bot.send_message(
                    chat_id=user_data['chat_id'],
                    text=message.text
                )
                success += 1
                
                # Har 10ta yuborilganda progress yangilash
                if i % 10 == 0 or i == total:
                    await progress_msg.edit_text(
                        f"📤 Xabar yuborilmoqda... {i}/{total}\n"
                        f"✅ Muvaffaqiyatli: {success}\n"
                        f"❌ Xatolar: {i - success}"
                    )
                
                await asyncio.sleep(0.1)  # Rate limit uchun
            except Exception as e:
                logger.error(f"Foydalanuvchi {user_data['chat_id']} ga xabar yuborishda xato: {e}")
        
        context.user_data.pop("broadcast_mode", None)
        await progress_msg.edit_text(
            f"📢 Broadcast yakunlandi!\n\n"
            f"🔢 Jami: {total}\n"
            f"✅ Muvaffaqiyatli: {success}\n"
            f"❌ Xatolar: {total - success}"
        )
        return
    
    # Javob berish rejimi
    if 'answering' in context.user_data:
        question_id = context.user_data['answering']
        answer = message.text
        
        result = save_answer(question_id, answer, user.id)
        if not result:
            await message.reply_text("❌ Savol topilmadi yoki allaqachon javob berilgan!")
            context.user_data.pop('answering', None)
            return
        
        # Foydalanuvchiga javob yuborish
        try:
            await context.bot.send_message(
                chat_id=result['chat_id'],
                text=f"📨 Sizning savolingizga javob:\n\n"
                     f"❓ Savol: {result['question']}\n\n"
                     f"💡 Javob: {answer}"
            )
        except Exception as e:
            logger.error(f"Foydalanuvchiga javob yuborishda xato: {e}")
            await message.reply_text(
                f"✅ Javob saqlandi, lekin foydalanuvchiga yuborib bo'lmadi. "
                f"U bloklangan yoki botdan chiqib ketgan bo'lishi mumkin."
            )
        else:
            await message.reply_text("✅ Javob muvaffaqiyatli yuborildi!")
        
        # Boshqa adminlarga xabar berish
        for admin_id in ADMIN_IDS:
            if admin_id != user.id:
                try:
                    await context.bot.send_message(
                        chat_id=admin_id,
                        text=f"ℹ️ Admin @{user.username} savolga javob berdi:\n\n"
                             f"🆔 Savol ID: {question_id}\n"
                             f"👤 Foydalanuvchi: {result['chat_id']}\n"
                             f"❓ Savol: {result['question'][:100]}...\n"
                             f"💡 Javob: {answer[:100]}..."
                    )
                except Exception as e:
                    logger.error(f"Admin {admin_id} ga xabar yuborishda xato: {e}")
        
        context.user_data.pop('answering', None)
        return
    
    # Oddiy admin xabari
    await message.reply_text(
        "Buyruqlar ro'yxati:\n"
        "/start - Botni qayta ishga tushirish\n"
        "/broadcast - Barchaga xabar yuborish\n"
        "/stats - Bot statistikasi\n"
        "/unanswered - Javobsiz savollar"
    )

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]
    ])
    
    await update.message.reply_text(
        "Barcha foydalanuvchilarga xabar yuborish uchun quyidagi tugmani bosing:",
        reply_markup=keyboard
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE is_banned = FALSE')
    active_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM users WHERE is_banned = TRUE')
    banned_users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM questions WHERE is_answered = FALSE')
    unanswered = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM questions WHERE is_answered = TRUE')
    answered = cursor.fetchone()[0]
    
    conn.close()
    
    await update.message.reply_text(
        "📊 Bot statistikasi:\n\n"
        f"👥 Faol foydalanuvchilar: {active_users}\n"
        f"⛔️ Bloklangan foydalanuvchilar: {banned_users}\n"
        f"❓ Javobsiz savollar: {unanswered}\n"
        f"✅ Javob berilgan savollar: {answered}"
    )

async def unanswered_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    
    questions = get_unanswered_questions()
    if not questions:
        await update.message.reply_text("🎉 Hozircha javobsiz savollar yo'q!")
        return
    
    text = "📨 Javobsiz savollar:\n\n"
    for i, q in enumerate(questions, 1):
        text += (
            f"{i}. 🆔 {q['id']}\n"
            f"👤 {q['first_name']} (@{q['username']})\n"
            f"📝 {q['question'][:50]}...\n\n"
        )
    
    await update.message.reply_text(text[:4000])  # Telegram xabar chegarasi

# Web server sozlamalari
async def web_server(application):
    async def handle(request):
        data = await request.json()
        update = Update.de_json(data, application.bot)
        await application.process_update(update)
        return web.Response(text="OK")

    app = web.Application()
    app.router.add_post('/webhook', handle)
    return app

async def send_admin_notification(bot):
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                chat_id=admin_id,
                text="🤖 Bot ishga tushdi!\n\n"
                     "Siz admin sifatida ro'yxatga olingansiz. "
                     "/buyruqlar orqali barcha buyruqlarni ko'rishingiz mumkin."
            )
        except Exception as e:
            logger.error(f"Admin {admin_id} ga xabar yuborishda xato: {e}")

if __name__ == "__main__":
    # Database ishga tushirish
    init_db()
    
    # Portni olish (Railway uchun)
    port = int(os.getenv("PORT", 8000))
    
    async def main():
        # Botni yaratish
        application = Application.builder().token(BOT_TOKEN).build()
        
        # Handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("broadcast", broadcast_command))
        application.add_handler(CommandHandler("stats", stats_command))
        application.add_handler(CommandHandler("unanswered", unanswered_command))
        application.add_handler(CallbackQueryHandler(button_callback))
        application.add_handler(MessageHandler(
            filters.TEXT & filters.User(ADMIN_IDS),
            handle_admin_response
        ))
        application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_question
        ))
        
        # Production (Railway) yoki Development (Polling) rejimi
        if os.getenv('RAILWAY_ENVIRONMENT'):
            logger.info("Production mode (Webhook) ishga tushmoqda...")
            
            await application.initialize()
            await application.bot.set_webhook(
                url=f"{WEBHOOK_URL}/webhook",
                drop_pending_updates=True
            )
            
            app = await web_server(application)
            await send_admin_notification(application.bot)
            await web._run_app(app, port=port)
        else:
            logger.info("Development mode (Polling) ishga tushmoqda...")
            await application.run_polling(drop_pending_updates=True)
    
    asyncio.run(main())
