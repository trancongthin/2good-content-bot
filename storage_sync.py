import os
import json
import time
import datetime
import threading
import requests
from config import (
    TELEGRAM_BOT_TOKEN,
    ADMIN_CHAT_ID,
    DATA_DIR,
    VAULT_FILE,
    MEMORY_FILE,
    KB_FILE
)

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
BACKUP_CHAT_FILE = DATA_DIR / "backup_chat.txt"
LAST_BACKUP_MSG_FILE = DATA_DIR / "last_backup_msg_id.txt"

SYNC_DEBOUNCE_TIMER = None
SYNC_LOCK = threading.Lock()

def get_backup_chat_id():
    """Returns the chat/channel ID where backups are pinned. Defaults to ADMIN_CHAT_ID."""
    if BACKUP_CHAT_FILE.exists():
        val = BACKUP_CHAT_FILE.read_text().strip()
        if val:
            return val
    env_val = os.environ.get("BACKUP_CHAT_ID")
    if env_val:
        return env_val.strip()
    return str(ADMIN_CHAT_ID)

def set_backup_chat_id(chat_id):
    BACKUP_CHAT_FILE.write_text(str(chat_id).strip())

def get_last_backup_msg_id():
    if LAST_BACKUP_MSG_FILE.exists():
        try:
            return int(LAST_BACKUP_MSG_FILE.read_text().strip())
        except Exception:
            return None
    return None

def set_last_backup_msg_id(msg_id):
    LAST_BACKUP_MSG_FILE.write_text(str(msg_id))

def restore_vault_from_telegram():
    """
    Scans the pinned message in the backup chat (ADMIN_CHAT_ID or private channel),
    downloads the latest JSON database, and restores local media vault and memory files.
    """
    chat_id = get_backup_chat_id()
    try:
        chat_resp = requests.get(f"{TELEGRAM_API}/getChat?chat_id={chat_id}", timeout=15).json()
        if not chat_resp.get("ok"):
            print(f"⚠️ [RESTORE] Không lấy được thông tin chat {chat_id}: {chat_resp}")
            return False, 0, 0

        pinned = chat_resp.get("result", {}).get("pinned_message")
        if not pinned:
            print(f"ℹ️ [RESTORE] Không tìm thấy tin nhắn được ghim trong chat {chat_id}.")
            return False, 0, 0

        caption = pinned.get("caption", "")
        doc = pinned.get("document")
        if not doc or "#2GOOD_VAULT_BACKUP" not in caption:
            print(f"ℹ️ [RESTORE] Tin nhắn ghim không phải bản sao lưu 2GOOD (caption: {caption[:30]}).")
            return False, 0, 0

        file_id = doc["file_id"]
        file_info = requests.get(f"{TELEGRAM_API}/getFile?file_id={file_id}", timeout=15).json()
        if not file_info.get("ok"):
            print(f"❌ [RESTORE] Không lấy được đường dẫn file từ Telegram: {file_info}")
            return False, 0, 0

        file_path = file_info["result"]["file_path"]
        download_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
        raw_bytes = requests.get(download_url, timeout=30).content

        payload = json.loads(raw_bytes.decode("utf-8"))
        vault_data = payload.get("media_vault", [])
        memory_data = payload.get("content_memory", [])
        kb_data = payload.get("knowledge_base", [])

        # Write to local files
        with open(VAULT_FILE, "w", encoding="utf-8") as f:
            json.dump(vault_data, f, ensure_ascii=False, indent=2)

        with open(MEMORY_FILE, "w", encoding="utf-8") as f:
            json.dump(memory_data, f, ensure_ascii=False, indent=2)

        if kb_data:
            with open(KB_FILE, "w", encoding="utf-8") as f:
                json.dump(kb_data, f, ensure_ascii=False, indent=2)

        set_last_backup_msg_id(pinned["message_id"])
        print(f"✅ [RESTORE THÀNH CÔNG] Đã phục hồi {len(vault_data)} cụm media & {len(memory_data)} bài viết từ Telegram Cloud!")
        return True, len(vault_data), len(memory_data)

    except Exception as e:
        print(f"❌ [RESTORE LỖI]: {e}")
        return False, 0, 0

def sync_vault_to_telegram(silent=True):
    """
    Exports local vault and memory to a JSON backup, sends as document to backup chat,
    pins it silently, and deletes the old pinned backup to keep the chat clean.
    """
    chat_id = get_backup_chat_id()
    try:
        vault = []
        memory = []
        kb = []

        if VAULT_FILE.exists():
            try:
                with open(VAULT_FILE, "r", encoding="utf-8") as f:
                    vault = json.load(f)
            except Exception:
                pass

        if MEMORY_FILE.exists():
            try:
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    memory = json.load(f)
            except Exception:
                pass

        if KB_FILE.exists():
            try:
                with open(KB_FILE, "r", encoding="utf-8") as f:
                    kb = json.load(f)
            except Exception:
                pass

        payload = {
            "version": 1,
            "app": "2good_content_bot",
            "updated_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "media_vault": vault,
            "content_memory": memory,
            "knowledge_base": kb
        }

        json_bytes = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        now_str = datetime.datetime.now().strftime("%H:%M:%S %d/%m/%Y")
        caption = (
            f"📦 <b>[2GOOD DB BACKUP] BẢN SAO LƯU KHO VĨNH CỬU</b>\n"
            f"#2GOOD_VAULT_BACKUP\n\n"
            f"⏰ <b>Cập nhật:</b> {now_str}\n"
            f"📁 <b>Kho Media:</b> {len(vault)} cụm tư liệu\n"
            f"📝 <b>Lịch sử đăng:</b> {len(memory)} bài viết\n"
            f"🛡️ <i>Tự động phục hồi 100% khi server nâng cấp hoặc khởi động lại.</i>"
        )

        resp = requests.post(
            f"{TELEGRAM_API}/sendDocument",
            data={
                "chat_id": chat_id,
                "caption": caption,
                "parse_mode": "HTML",
                "disable_notification": silent
            },
            files={"document": ("2good_vault_backup.json", json_bytes, "application/json")},
            timeout=25
        ).json()

        if not resp.get("ok"):
            print(f"❌ [SYNC BACKUP] Gửi file backup thất bại: {resp}")
            return False, f"Lỗi gửi file: {resp}"

        new_msg_id = resp["result"]["message_id"]

        # Pin new backup message
        pin_resp = requests.post(
            f"{TELEGRAM_API}/pinChatMessage",
            json={
                "chat_id": chat_id,
                "message_id": new_msg_id,
                "disable_notification": True
            },
            timeout=10
        ).json()

        # Clean up old backup message to keep chat uncluttered
        old_msg_id = get_last_backup_msg_id()
        if old_msg_id and old_msg_id != new_msg_id:
            try:
                requests.post(
                    f"{TELEGRAM_API}/deleteMessage",
                    json={"chat_id": chat_id, "message_id": old_msg_id},
                    timeout=5
                )
            except Exception:
                pass

        set_last_backup_msg_id(new_msg_id)
        print(f"✅ [SYNC BACKUP] Đã sao lưu và ghim thành công lên Telegram (msg_id: {new_msg_id})!")
        return True, f"Đã sao lưu thành công {len(vault)} cụm media & {len(memory)} bài viết lên Telegram!"

    except Exception as e:
        print(f"❌ [SYNC BACKUP LỖI]: {e}")
        return False, str(e)

def trigger_debounced_sync(delay_seconds=3):
    """
    Debounces backup sync to avoid excessive Telegram API calls when media is ingested in batch.
    """
    global SYNC_DEBOUNCE_TIMER
    with SYNC_LOCK:
        if SYNC_DEBOUNCE_TIMER and SYNC_DEBOUNCE_TIMER.is_alive():
            SYNC_DEBOUNCE_TIMER.cancel()
        SYNC_DEBOUNCE_TIMER = threading.Timer(delay_seconds, sync_vault_to_telegram, kwargs={"silent": True})
        SYNC_DEBOUNCE_TIMER.daemon = True
        SYNC_DEBOUNCE_TIMER.start()
