from telegram import Update
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, ContextTypes, filters
)
from config import BOT_TOKEN, ADMIN_IDS, DB_PATH
from db import DB
import keyboards as kb

db = DB(DB_PATH)

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    db.upsert_user(u.id, u.username or "", (u.full_name or "").strip())
    context.user_data["state"] = None
    await update.message.reply_text("Assalomu alaykum! Menyudan tanlang 👇", reply_markup=kb.user_menu())

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🆘 Yordam: Menyudan 'Savol yuborish' ni tanlang.")

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("Siz admin emassiz.")
        return
    context.user_data["state"] = None
    await update.message.reply_text("🛠 Admin panel:", reply_markup=kb.admin_panel())

async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    uid = query.from_user.id

    # USER callbacks
    if data.startswith("u:"):
        action = data.split(":", 1)[1]
        if action == "menu":
            context.user_data["state"] = None
            await query.message.reply_text("🏠 Menyu:", reply_markup=kb.user_menu())

        elif action == "ask":
            context.user_data["state"] = "WAIT_QUESTION"
            await query.message.reply_text("✉️ Savolingizni yozing:")

        elif action == "history":
            rows = db.get_user_history(uid, limit=10)
            if not rows:
                await query.message.reply_text("🕓 Hozircha tarix yo‘q.", reply_markup=kb.user_menu())
                return
            out = ["🕓 So‘nggi 10 ta savolingiz:"]
            for tid, q, a, status, created_at in rows:
                out.append(f"\n#{tid} • {status}\n❓ {q}\n✅ {a}")
            await query.message.reply_text("\n".join(out), reply_markup=kb.user_menu())

        elif action == "info":
            await query.message.reply_text(
                "ℹ️ Bot funksiyalari:\n• Savol yuborish\n• Admin javobi\n• Savollar tarixi\n• Admin panel + broadcast",
                reply_markup=kb.user_menu()
            )

        elif action == "contact":
            await query.message.reply_text("📞 Bot orqali savol yuboring — adminlar javob qaytaradi.", reply_markup=kb.user_menu())
        return

    # ADMIN callbacks
    if data.startswith("a:"):
        if not is_admin(uid):
            await query.message.reply_text("Siz admin emassiz.")
            return

        parts = data.split(":")
        action = parts[1]

        if action == "panel":
            context.user_data["state"] = None
            await query.message.reply_text("🛠 Admin panel:", reply_markup=kb.admin_panel())

        elif action == "stats":
            uc = db.user_count()
            tc = db.ticket_count()
            open_c = db.ticket_count_by_status("open")
            prog_c = db.ticket_count_by_status("in_progress")
            ans_c = db.ticket_count_by_status("answered")
            await query.message.reply_text(
                f"📊 Statistika:\n"
                f"👥 Userlar: {uc}\n"
                f"🧾 Jami ticket: {tc}\n"
                f"🟢 Open: {open_c}\n"
                f"🟡 In progress: {prog_c}\n"
                f"✅ Answered: {ans_c}",
                reply_markup=kb.admin_back_panel()
            )

        elif action == "filter_menu":
            await query.message.reply_text("🧾 Filtr tanlang:", reply_markup=kb.admin_filter_menu())

        elif action == "list":
            # a:list:<status>
            status = parts[2]
            if status == "all":
                rows = db.get_recent_tickets(limit=15, status=None)
                title = "🧾 So‘nggi 15 ticket (hammasi):"
            else:
                rows = db.get_recent_tickets(limit=15, status=status)
                title = f"🧾 So‘nggi 15 ticket ({status}):"

            if not rows:
                await query.message.reply_text("Hozircha ticket yo‘q.", reply_markup=kb.admin_filter_menu())
                return

            out = [title]
            for tid, user_id, q, st, claimed_by, created_at in rows:
                who = f" | claimed_by: {claimed_by}" if claimed_by else ""
                out.append(f"\n#{tid} • {st}{who} • user:{user_id}\n❓ {q}")
            await query.message.reply_text("\n".join(out), reply_markup=kb.admin_filter_menu())

        elif action == "broadcast":
            context.user_data["state"] = "ADMIN_BROADCAST"
            await query.message.reply_text("📢 Broadcast uchun matn yozing:")

        elif action == "claim":
            ticket_id = int(parts[2])
            ok, msg, claimed_by = db.claim_ticket(ticket_id, uid)
            if not ok:
                extra = f"\n👤 claimed_by: {claimed_by}" if claimed_by else ""
                await query.message.reply_text(f"⚠️ {msg}{extra}", reply_markup=kb.admin_back_panel())
                return
            # claim bo‘ldi — endi javob yozishga o‘tish yoki unclaim
            await query.message.reply_text(f"✅ {msg}\nTicket: #{ticket_id}", reply_markup=kb.admin_claimed_actions(ticket_id))

        elif action == "unclaim":
            ticket_id = int(parts[2])
            ok, msg = db.unclaim_ticket(ticket_id, uid)
            if ok:
                await query.message.reply_text(f"✅ {msg}", reply_markup=kb.admin_back_panel())
            else:
                await query.message.reply_text(f"⚠️ {msg}", reply_markup=kb.admin_back_panel())

        elif action == "answer":
            ticket_id = int(parts[2])
            ticket = db.get_ticket(ticket_id)
            if not ticket:
                await query.message.reply_text("Ticket topilmadi.", reply_markup=kb.admin_back_panel())
                return

            status = ticket[5]
            claimed_by = ticket[6]
            if status != "in_progress" or claimed_by != uid:
                await query.message.reply_text(
                    "⚠️ Javob yozish uchun ticket sizga biriktirilgan bo‘lishi kerak.\n"
                    "Avval 'Javob yozish (claim)' ni bosing.",
                    reply_markup=kb.admin_back_panel()
                )
                return

            context.user_data["state"] = "ADMIN_ANSWER"
            context.user_data["answer_ticket_id"] = ticket_id
            await query.message.reply_text(f"✍️ #{ticket_id} uchun javob yozing:")

        return

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    text = update.message.text.strip()
    db.upsert_user(u.id, u.username or "", (u.full_name or "").strip())
    state = context.user_data.get("state")

    # ADMIN flow
    if is_admin(u.id):
        if state == "ADMIN_BROADCAST":
            user_ids = db.get_all_user_ids()
            sent = 0
            for uid in user_ids:
                try:
                    await context.bot.send_message(chat_id=uid, text=f"📢 {text}")
                    sent += 1
                except:
                    pass
            context.user_data["state"] = None
            await update.message.reply_text(f"✅ Broadcast yuborildi: {sent} ta user.", reply_markup=kb.admin_panel())
            return

        if state == "ADMIN_ANSWER":
            ticket_id = context.user_data.get("answer_ticket_id")
            ticket = db.get_ticket(ticket_id) if ticket_id else None
            if not ticket:
                context.user_data["state"] = None
                await update.message.reply_text("⚠️ Ticket topilmadi.", reply_markup=kb.admin_panel())
                return

            ok, msg = db.answer_ticket(ticket_id, text, u.id)
            if not ok:
                # ticket sizga tegishli emas yoki status mos emas
                context.user_data["state"] = None
                context.user_data["answer_ticket_id"] = None
                await update.message.reply_text(f"⚠️ {msg}", reply_markup=kb.admin_panel())
                return

            user_id = ticket[1]
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📨 Admin javobi (#{ticket_id}):\n\n{text}",
                reply_markup=kb.after_answer_menu()
            )

            context.user_data["state"] = None
            context.user_data["answer_ticket_id"] = None
            await update.message.reply_text("✅ Javob yuborildi.", reply_markup=kb.admin_panel())
            return

        await update.message.reply_text("🛠 Admin panel uchun /admin ni bosing.", reply_markup=kb.admin_panel())
        return

    # USER flow
    if state == "WAIT_QUESTION":
        ticket_id = db.create_ticket(u.id, text)

        for admin_id in ADMIN_IDS:
            try:
                await context.bot.send_message(
                    chat_id=admin_id,
                    text=(
                        f"📩 Yangi savol (#{ticket_id}):\n\n"
                        f"{text}\n\n"
                        f"👤 @{u.username or 'Nomaʼlum'} | {u.full_name or ''}\n"
                        f"🆔 ID: {u.id}"
                    ),
                    reply_markup=kb.admin_claim_button(ticket_id)  # ✅ claim tugmasi
                )
            except:
                pass

        context.user_data["state"] = None
        await update.message.reply_text("✅ Savolingiz adminlarga yuborildi.", reply_markup=kb.user_menu())
        return

    await update.message.reply_text("Menyudan tanlang 👇", reply_markup=kb.user_menu())

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("admin", admin_command))

    app.add_handler(CallbackQueryHandler(callback_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    print("✅ Bot ishga tushdi.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
