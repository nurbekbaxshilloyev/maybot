from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def user_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✉️ Savol yuborish", callback_data="u:ask")],
        [InlineKeyboardButton("🕓 Savollar tarixi", callback_data="u:history")],
        [InlineKeyboardButton("ℹ️ Info", callback_data="u:info"),
         InlineKeyboardButton("📞 Kontakt", callback_data="u:contact")],
    ])

def after_answer_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✉️ Yana savol yuborish", callback_data="u:ask")],
        [InlineKeyboardButton("🕓 Tarix", callback_data="u:history")],
        [InlineKeyboardButton("🏠 Menyu", callback_data="u:menu")],
    ])

def admin_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Statistika", callback_data="a:stats")],
        [InlineKeyboardButton("🧾 Savollar (filtr)", callback_data="a:filter_menu")],
        [InlineKeyboardButton("📢 Broadcast", callback_data="a:broadcast")],
    ])

def admin_filter_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🟢 Open", callback_data="a:list:open"),
         InlineKeyboardButton("🟡 In progress", callback_data="a:list:in_progress")],
        [InlineKeyboardButton("✅ Answered", callback_data="a:list:answered"),
         InlineKeyboardButton("🧾 Hammasi", callback_data="a:list:all")],
        [InlineKeyboardButton("⬅️ Panel", callback_data="a:panel")]
    ])

# Admin ticketni OLISH (claim) tugmasi
def admin_claim_button(ticket_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✍️ Javob yozish (claim)", callback_data=f"a:claim:{ticket_id}")]
    ])

# Claim qilingandan keyin: javob yozish yoki bo‘shatish
def admin_claimed_actions(ticket_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Javob yozishga o‘tish", callback_data=f"a:answer:{ticket_id}")],
        [InlineKeyboardButton("♻️ Bo‘shatish (unclaim)", callback_data=f"a:unclaim:{ticket_id}")],
    ])

def admin_back_panel():
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Panelga qaytish", callback_data="a:panel")]])
