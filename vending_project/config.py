import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")
SECRET_KEY = os.getenv("SECRET_KEY", "default-secret-key-change-me")
WEB_PORT = int(os.getenv("WEB_PORT", 5000))
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'data.db')}")
BOT_PREFIX = os.getenv("BOT_PREFIX", "!")

UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads", "receipts")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)