import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi. .env faylida BOT_TOKEN ni sozlang.")

_admins_raw = os.getenv("ADMIN_IDS", "").strip()
if not _admins_raw:
    raise ValueError("ADMIN_IDS topilmadi. .env faylida ADMIN_IDS=... qilib yozing.")

ADMIN_IDS = set()
for part in _admins_raw.split(","):
    part = part.strip()
    if part:
        ADMIN_IDS.add(int(part))

DB_PATH = os.getenv("DB_PATH", "bot.db")
