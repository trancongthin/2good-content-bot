import os
import sys
import json
import time
import base64
import requests
import datetime
from pathlib import Path

# --- CONFIGURATION ---
TELEGRAM_BOT_TOKEN = "8731818178:AAEkY02lSyPqt63I5l0tDuCTtIRj5QHRbx0"
GEMINI_API_KEY = "AQ.Ab8RN6LMEUII65PkLCq6qQzcmRwekVN4FBVewIp6-IvejbbWoQ"
ADMIN_CHAT_ID = "6143441477"  # ID của Sếp Thìn
# TARGET_GROUP_CHAT_ID: Nhóm CTV (nếu chưa set thì gửi demo về admin)
TARGET_GROUP_CHAT_ID = os.environ.get("CTV_GROUP_CHAT_ID", ADMIN_CHAT_ID)

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
INBOX_DIR = BASE_DIR / "inbox"
INBOX_DIR.mkdir(exist_ok=True)

KB_FILE = DATA_DIR / "knowledge_base.json"
MEMORY_FILE = DATA_DIR / "content_memory.json"

if not KB_FILE.exists():
    with open(KB_FILE, "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=2)

if not MEMORY_FILE.exists():
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        json.dump([], f, ensure_ascii=False, indent=2)

print("🚀 2GOOD AI CONTENT ENGINE IS INITIALIZED...")
