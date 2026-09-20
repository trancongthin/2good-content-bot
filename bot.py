import os
import sys
import re
import time
import json
import requests
import datetime
import threading
import signal
import http.server
from pathlib import Path
from config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID, DATA_DIR, VAULT_FILE
from ai_engine import (
    analyze_multiple_images_and_generate_content,
    generate_content_from_text_prompt,
    save_memory,
    load_memory
)

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
CHANNEL_FILE = DATA_DIR / "target_channel.txt"
PID_FILE = DATA_DIR / "bot.pid"
AUTOPILOT_SLOT_FILE = DATA_DIR / "last_autopilot_slot.txt"
BOT_START_TIME = time.time()
LAST_AUTOPILOT_RUN_SLOT = None

# --- INSTANCE LOCK & PID MANAGEMENT ---
def acquire_single_instance_lock():
    pid = os.getpid()
    if PID_FILE.exists():
        try:
            old_pid = int(PID_FILE.read_text().strip())
            if old_pid != pid:
                try:
                    os.kill(old_pid, 0)
                    print(f"⚠️ Phát hiện tiến trình Bot cũ (PID: {old_pid}) đang chạy. Đang dừng...")
                    os.kill(old_pid, signal.SIGTERM)
                    time.sleep(1)
                except OSError:
                    pass
        except Exception:
            pass
    PID_FILE.write_text(str(pid))

def release_single_instance_lock():
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
    except Exception:
        pass

RECENT_UPDATES = []
LAST_ERROR = None

# --- HTTP HEALTH CHECK SERVER FOR CLOUD HOSTING (RENDER / RAILWAY / KOYEB) ---
class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.end_headers()
        uptime = get_uptime_string()
        channel_title, channel_id = get_channel_info()
        vault_stats = get_vault_stats()
        resp = {
            "status": "online",
            "service": "2GOOD Content Engine & Auto-Pilot",
            "uptime": uptime,
            "connected_channel": channel_title,
            "channel_id": channel_id,
            "vault": vault_stats,
            "recent_updates": RECENT_UPDATES[-10:],
            "last_error": str(LAST_ERROR) if LAST_ERROR else None,
            "timestamp": str(datetime.datetime.now())
        }
        self.wfile.write(json.dumps(resp, ensure_ascii=False).encode("utf-8"))

    def log_message(self, format, *args):
        return

def start_health_server():
    port = int(os.environ.get("PORT", 8080))
    try:
        server = http.server.HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        print(f"🌐 Health check HTTP server is listening on port {port}...")
        server.serve_forever()
    except Exception as e:
        print(f"Warning: Health server failed on port {port}: {e}")

# --- CHANNEL MANAGEMENT ---
def get_target_channel():
    if CHANNEL_FILE.exists():
        return CHANNEL_FILE.read_text().strip()
    return "-1004318489942"

def set_target_channel(channel_id, channel_title=""):
    CHANNEL_FILE.write_text(str(channel_id))
    send_message(ADMIN_CHAT_ID, f"🎉 <b>ĐÃ KẾT NỐI VỚI KÊNH:</b> {channel_title} (ID: <code>{channel_id}</code>)")

def get_channel_info():
    target_id = get_target_channel()
    try:
        res = requests.get(f"{TELEGRAM_API}/getChat?chat_id={target_id}", timeout=10).json()
        if res.get("ok"):
            title = res["result"].get("title", "Kênh Telegram")
            return title, target_id
    except Exception:
        pass
    return "Kênh CTV 2GOOD", target_id

# --- MEDIA VAULT DATA STORAGE & ROTATION LOGIC ---
VAULT_LOCK = threading.Lock()

def load_media_vault():
    with VAULT_LOCK:
        try:
            if VAULT_FILE.exists():
                with open(VAULT_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error loading vault: {e}")
        return []

def save_media_vault(vault):
    with VAULT_LOCK:
        try:
            with open(VAULT_FILE, "w", encoding="utf-8") as f:
                json.dump(vault, f, ensure_ascii=False, indent=2)
            try:
                import storage_sync
                storage_sync.trigger_debounced_sync()
            except Exception:
                pass
        except Exception as e:
            print(f"Error saving vault: {e}")

def add_cluster_to_vault(chat_id, message_ids, media_types, sample_file_ids=None, custom_note="", has_video=False, media_files=None):
    vault = load_media_vault()
    cluster_id = f"cl_{int(time.time())}_{len(vault)+1}"
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cluster = {
        "id": cluster_id,
        "chat_id": str(chat_id),
        "message_ids": sorted(list(set(message_ids))),
        "media_types": media_types,
        "media_files": media_files or [],
        "sample_file_ids": sample_file_ids or [],
        "custom_note": custom_note,
        "has_video": has_video,
        "added_at": now_str,
        "last_posted_at": None,
        "post_count": 0
    }
    vault.append(cluster)
    save_media_vault(vault)
    return cluster

def get_vault_cluster_by_id(cluster_id):
    vault = load_media_vault()
    for c in vault:
        if c.get("id") == cluster_id:
            return c
    return None

def delete_cluster_from_vault(cluster_id):
    vault = load_media_vault()
    new_vault = [c for c in vault if c.get("id") != cluster_id]
    save_media_vault(new_vault)

def mark_cluster_posted(cluster_id):
    vault = load_media_vault()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for c in vault:
        if c.get("id") == cluster_id:
            c["post_count"] = c.get("post_count", 0) + 1
            c["last_posted_at"] = now_str
            break
    save_media_vault(vault)

def get_vault_stats():
    vault = load_media_vault()
    total = len(vault)
    unposted = 0
    rotated_ready = 0
    recent_posted = 0
    now = datetime.datetime.now()

    for c in vault:
        if c.get("post_count", 0) == 0:
            unposted += 1
        else:
            last_p = c.get("last_posted_at")
            if last_p:
                try:
                    dt = datetime.datetime.strptime(last_p, "%Y-%m-%d %H:%M:%S")
                    if (now - dt).total_seconds() >= 7 * 86400:
                        rotated_ready += 1
                    else:
                        recent_posted += 1
                except Exception:
                    rotated_ready += 1
            else:
                rotated_ready += 1

    return {
        "total": total,
        "unposted": unposted,
        "rotated_ready": rotated_ready,
        "recent_posted": recent_posted
    }

def get_next_cluster_for_autopilot():
    """
    Priority 1: Clusters that haven't been posted yet (post_count == 0, oldest added first).
    Priority 2: Rotated clusters (post_count > 0 and last_posted_at >= 7 days ago, oldest first).
    Fallback: Oldest posted cluster if all were posted < 7 days (Bất tử content).
    """
    vault = load_media_vault()
    if not vault:
        return None, False

    # 1. Unposted
    for c in vault:
        if c.get("post_count", 0) == 0:
            return c, False

    # 2. Cooldown >= 7 days
    now = datetime.datetime.now()
    oldest_candidate = None
    oldest_candidate_dt = None

    for c in vault:
        last_p = c.get("last_posted_at")
        if last_p:
            try:
                dt = datetime.datetime.strptime(last_p, "%Y-%m-%d %H:%M:%S")
                if (now - dt).total_seconds() >= 7 * 86400:
                    if oldest_candidate_dt is None or dt < oldest_candidate_dt:
                        oldest_candidate_dt = dt
                        oldest_candidate = c
            except Exception:
                oldest_candidate = c
                break
        else:
            oldest_candidate = c
            break

    if oldest_candidate:
        return oldest_candidate, True

    # Fallback: Pick oldest posted cluster
    sorted_vault = sorted(vault, key=lambda x: x.get("last_posted_at") or "")
    if sorted_vault:
        return sorted_vault[0], True

    return None, False

# --- BUFFER & PENDING POSTS STATE ---
BUFFER_CLUSTER_ITEMS = []
BUFFER_LOCK = threading.Lock()
DEBOUNCE_TIMER = None
PENDING_POSTS = {}
PENDING_LOCK = threading.Lock()
PENDING_POSTS_FILE = DATA_DIR / "pending_posts.json"

def save_pending_posts():
    try:
        with open(PENDING_POSTS_FILE, "w", encoding="utf-8") as f:
            json.dump(PENDING_POSTS, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Error saving pending posts: {e}")

def load_pending_posts():
    global PENDING_POSTS
    if PENDING_POSTS_FILE.exists():
        try:
            with open(PENDING_POSTS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    PENDING_POSTS = data
                    print(f"📂 Đã tải {len(PENDING_POSTS)} bài nháp chờ duyệt từ bộ nhớ đĩa.")
        except Exception as e:
            print(f"⚠️ Error loading pending posts: {e}")

def cleanup_expired_pending_posts(max_age_seconds=7200):
    now = time.time()
    with PENDING_LOCK:
        expired_keys = []
        for pid, pdata in PENDING_POSTS.items():
            if now - pdata.get("timestamp", now) > max_age_seconds:
                expired_keys.append(pid)
        for k in expired_keys:
            del PENDING_POSTS[k]
        if expired_keys:
            save_pending_posts()
            print(f"🧹 Đã tự động dọn {len(expired_keys)} bài nháp hết hạn khỏi bộ nhớ.")

# --- TELEGRAM MESSAGING & CLEAN COPY UTILITIES ---
def get_file_bytes(file_id):
    try:
        res = requests.get(f"{TELEGRAM_API}/getFile?file_id={file_id}", timeout=20).json()
        if not res.get("ok"):
            return None
        file_path = res["result"]["file_path"]
        download_url = f"https://api.telegram.org/file/bot{TELEGRAM_BOT_TOKEN}/{file_path}"
        file_res = requests.get(download_url, timeout=30)
        return file_res.content
    except Exception as e:
        print(f"Error downloading file: {e}")
        return None

def copy_messages_clean(target_chat_id, from_chat_id, message_ids):
    """
    Copies messages cleanly using Telegram copyMessages API.
    Preserves 100% original video/photo quality with ZERO 'Forwarded from...' attribution!
    """
    sorted_ids = sorted(list(set(message_ids)))
    url = f"{TELEGRAM_API}/copyMessages"
    payload = {
        "chat_id": str(target_chat_id),
        "from_chat_id": str(from_chat_id),
        "message_ids": sorted_ids
    }
    try:
        res = requests.post(url, json=payload, timeout=40).json()
        if res.get("ok"):
            return True, res.get("result", [])
        else:
            print(f"copyMessages failed: {res}")
            return False, res.get("description", "Unknown error")
    except Exception as e:
        print(f"Exception during copyMessages: {e}")
        return False, str(e)

def split_text_into_chunks(text, max_length=3800):
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    lines = text.split("\n")
    current_chunk = []
    current_length = 0
    
    for line in lines:
        if current_length + len(line) + 1 > max_length:
            if current_chunk:
                chunks.append("\n".join(current_chunk))
                current_chunk = [line]
                current_length = len(line)
            else:
                for i in range(0, len(line), max_length):
                    chunks.append(line[i:i+max_length])
                current_chunk = []
                current_length = 0
        else:
            current_chunk.append(line)
            current_length += len(line) + 1
            
    if current_chunk:
        chunks.append("\n".join(current_chunk))
        
    return chunks

def send_message(chat_id, text, reply_markup=None, parse_mode="HTML", reply_to_message_id=None, message_thread_id=None):
    chunks = split_text_into_chunks(text)
    last_res = None
    
    for i, chunk in enumerate(chunks):
        markup = reply_markup if i == len(chunks) - 1 else None
        payload = {
            "chat_id": str(chat_id),
            "text": chunk,
            "parse_mode": parse_mode
        }
        if message_thread_id:
            payload["message_thread_id"] = message_thread_id
        if reply_to_message_id and i == 0:
            payload["reply_to_message_id"] = reply_to_message_id
        if markup:
            payload["reply_markup"] = json.dumps(markup)
            
        try:
            res = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=20).json()
            if not res.get("ok"):
                payload.pop("parse_mode", None)
                payload.pop("reply_to_message_id", None)
                res = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=20).json()
            last_res = res
        except Exception as e:
            print(f"Error sending message: {e}")
            
    return last_res

def send_media_group(chat_id, photos_bytes_list, initial_caption=""):
    if not photos_bytes_list:
        return None
    if len(photos_bytes_list) == 1:
        files = {"photo": ("image.jpg", photos_bytes_list[0], "image/jpeg")}
        data = {"chat_id": str(chat_id), "caption": initial_caption[:1024], "parse_mode": "HTML"}
        return requests.post(f"{TELEGRAM_API}/sendPhoto", data=data, files=files, timeout=30).json()

    media = []
    files = {}
    for i, pbytes in enumerate(photos_bytes_list[:10]):
        attach_name = f"photo_{i}"
        files[attach_name] = (f"photo_{i}.jpg", pbytes, "image/jpeg")
        item = {
            "type": "photo",
            "media": f"attach://{attach_name}"
        }
        if i == 0 and initial_caption:
            item["caption"] = initial_caption[:1024]
            item["parse_mode"] = "HTML"
        media.append(item)

    data = {
        "chat_id": str(chat_id),
        "media": json.dumps(media)
    }
    return requests.post(f"{TELEGRAM_API}/sendMediaGroup", data=data, files=files, timeout=60).json()

def answer_callback(callback_query_id, text=""):
    try:
        requests.post(f"{TELEGRAM_API}/answerCallbackQuery", json={
            "callback_query_id": callback_query_id,
            "text": text
        }, timeout=10)
    except Exception:
        pass

# --- UPTIME FORMATTER ---
def get_uptime_string():
    elapsed = int(time.time() - BOT_START_TIME)
    days, rem = divmod(elapsed, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, seconds = divmod(rem, 60)
    parts = []
    if days > 0:
        parts.append(f"{days} ngày")
    if hours > 0:
        parts.append(f"{hours} giờ")
    if minutes > 0:
        parts.append(f"{minutes} phút")
    parts.append(f"{seconds} giây")
    return " ".join(parts)

# --- SYSTEM COMMANDS ---
def build_status_message():
    channel_title, channel_id = get_channel_info()
    memories = load_memory()
    total_posted = len(memories)
    vault_stats = get_vault_stats()
    
    with BUFFER_LOCK:
        buf_count = len(BUFFER_CLUSTER_ITEMS)
    with PENDING_LOCK:
        pending_count = len(PENDING_POSTS)
        
    uptime = get_uptime_string()
    now_str = datetime.datetime.now().strftime("%H:%M:%S - %d/%m/%Y")

    status_text = f"""📊 <b>BÁO CÁO HỆ THỐNG 2GOOD CONTENT ENGINE (24/7)</b>

🟢 <b>Trạng thái:</b> Đang chạy ổn định (Online 24/7)
⏱ <b>Uptime:</b> {uptime}
🕒 <b>Thời gian:</b> {now_str}
⏰ <b>Hẹn giờ Auto-Pilot:</b> 2 cữ/ngày (Sáng 08:00 AM & Chiều 13:00 PM Giờ VN)

━━━━━━━━━━━━━━━━━━━━━
📡 <b>Kênh CTV kết nối:</b> {channel_title}
🆔 <b>Channel ID:</b> <code>{channel_id}</code>
🤖 <b>AI Engine:</b> Google Gemini Flash (3 Góc chuẩn 2GOOD)
📦 <b>Bộ đệm media đang nhận:</b> {buf_count} file
📝 <b>Bài nháp chờ duyệt:</b> {pending_count} bài
📚 <b>Tổng bài đã xuất bản:</b> {total_posted} bài

━━━━━━━━━━━━━━━━━━━━━
🗄 <b>THỐNG KÊ KHO MEDIA AUTO-PILOT:</b>
• Tổng số cụm trong kho: <b>{vault_stats['total']} cụm</b>
• Cụm mới chưa đăng: <b>{vault_stats['unposted']} cụm</b>
• Cụm sẵn sàng quay vòng (> 7 ngày): <b>{vault_stats['rotated_ready']} cụm</b>
• Cụm đang nghỉ: <b>{vault_stats['recent_posted']} cụm</b>"""

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "📦 Xem Kho Media (/kho)", "callback_data": "CMD_KHO"},
                {"text": "⚡ Phát sóng ngay (/chay_ngay)", "callback_data": "CMD_RUN_AUTOPILOT"}
            ],
            [
                {"text": "🔄 Làm mới trạng thái", "callback_data": "CMD_STATUS"},
                {"text": "📜 5 bài gần nhất", "callback_data": "CMD_HISTORY"}
            ],
            [
                {"text": "🧹 Dọn sạch hàng chờ (/reset)", "callback_data": "CMD_RESET"}
            ]
        ]
    }
    return status_text, keyboard

def build_kho_message():
    vault = load_media_vault()
    stats = get_vault_stats()
    
    lines = [
        "📦 <b>KHO MEDIA & BẤT TỬ CONTENT 2GOOD</b>\n",
        f"📊 <b>Tổng cụm media trong kho:</b> {stats['total']} cụm",
        f"✨ <b>Cụm mới chưa đăng:</b> {stats['unposted']} cụm",
        f"🔄 <b>Cụm sẵn sàng quay vòng (> 7 ngày):</b> {stats['rotated_ready']} cụm",
        f"⏳ <b>Cụm đang trong thời gian nghỉ:</b> {stats['recent_posted']} cụm\n",
        "━━━━━━━━━━━━━━━━━━━━━",
        "🗂 <b>5 CỤM GẦN NHẤT TRONG KHO:</b>"
    ]
    
    if not vault:
        lines.append("<i>Kho hiện đang trống. Sếp hãy gửi các cụm ảnh/video vào đây để bot tự động lưu kho!</i>")
    else:
        recent = vault[-5:]
        recent.reverse()
        for i, c in enumerate(recent, 1):
            types_str = ", ".join(set(c.get("media_types", ["media"])))
            count_m = len(c.get("message_ids", []))
            p_count = c.get("post_count", 0)
            status_tag = "🆕 Chưa đăng" if p_count == 0 else f"🔄 Đã đăng {p_count} lần (Lần cuối: {c.get('last_posted_at', 'N/A')})"
            note = f" — <i>\"{c.get('custom_note')[:35]}\"</i>" if c.get("custom_note") else ""
            lines.append(f"<b>{i}. ID:</b> <code>{c['id']}</code> ({count_m} file {types_str})")
            lines.append(f"   📌 {status_tag}{note}")

    lines.append("\n💡 <i>Mẹo: Bot tự động bốc 1 cụm lúc 08:00 AM sáng và 13:00 PM chiều để viết bài 3 góc phát sóng Kênh CTV. Sếp có thể bấm nút bên dưới để phát sóng ngay lập tức!</i>")
    
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "⚡ Phát sóng ngay 1 bài (/chay_ngay)", "callback_data": "CMD_RUN_AUTOPILOT"},
                {"text": "🔄 Làm mới kho", "callback_data": "CMD_KHO"}
            ]
        ]
    }
    return "\n".join(lines), keyboard

def build_history_message():
    memories = load_memory()
    if not memories:
        return "📜 <b>LỊCH SỬ BÀI ĐÃ ĐĂNG:</b>\n\n<i>Hiện chưa có bài viết nào được đăng vào kênh CTV.</i>"
    
    recent = memories[-5:]
    recent.reverse()
    
    lines = ["📜 <b>5 BÀI ĐÃ ĐĂNG GẦN NHẤT VÀO KÊNH CTV:</b>\n"]
    for i, item in enumerate(recent, 1):
        p_code = item.get("product_code", "2GOOD")
        angle = item.get("angle_used", "Đầy đủ")
        date_str = item.get("date_posted", "N/A")
        media_count = item.get("num_media", item.get("num_photos", "N/A"))
        summary = item.get("summary", "")[:120].replace("\n", " ")
        lines.append(f"<b>{i}. [{date_str}] — {p_code}</b> ({media_count} media)")
        lines.append(f"   🎯 Góc: <i>{angle}</i>")
        lines.append(f"   💬 Trích đoạn: <i>{summary}...</i>\n")
        
    return "\n".join(lines)

def execute_reset():
    global BUFFER_CLUSTER_ITEMS, DEBOUNCE_TIMER
    with BUFFER_LOCK:
        BUFFER_CLUSTER_ITEMS = []
        if DEBOUNCE_TIMER and DEBOUNCE_TIMER.is_alive():
            DEBOUNCE_TIMER.cancel()
            DEBOUNCE_TIMER = None
            
    with PENDING_LOCK:
        count = len(PENDING_POSTS)
        PENDING_POSTS.clear()
        save_pending_posts()
        
    return f"🧹 <b>ĐÃ RESET HỆ THỐNG THÀNH CÔNG:</b>\n- Đã xóa sạch bộ đệm media.\n- Đã giải phóng {count} bài nháp khỏi bộ nhớ RAM.\n- Kho Media (/kho) vẫn được bảo toàn nguyên vẹn."

def build_help_message():
    return """📖 <b>HƯỚNG DẪN SỬ DỤNG 2GOOD CONTENT ENGINE & TRỢ LÝ CTV (24/7):</b>

1️⃣ <b>Gửi cụm Ảnh / Video vào Bot (Tự động nạp Kho):</b>
- Chọn <b>ảnh hoặc video</b> (hoặc gửi lẫn cả ảnh và video).
- Gửi <b>cùng một lúc</b> vào khung chat này.
- Bot sẽ tự động:
  • 📦 Lưu trọn vẹn cụm vào <b>Kho Media (/kho)</b> để phát sóng sáng mai.
  • 🤖 Đồng thời gọi AI soạn sẵn <b>01 BÀI TỔNG HỢP VỚI 3 GÓC CHÂN THẬT</b>.

2️⃣ <b>Trợ lý Bán Hàng & Xử Lý Từ Chối Cho CTV:</b>
- <b>Trong nhóm chung:</b> Tag <code>@mr_morning_bot [câu hỏi]</code> hoặc gõ <code>/hoi [câu hỏi]</code>
  <i>Ví dụ: <code>@mr_morning_bot Khách chê S200 đắt quá</code></i>
- <b>Trong chat riêng 1-1 với Bot:</b> Gõ thẳng câu hỏi, bot sẽ đưa ra:
  🎯 Insight tâm lý khách
  💬 Câu trả lời mẫu lịch thiệp, tự nhiên để copy gửi khách
  💡 Mẹo thực chiến cho CTV
- Các lệnh nhanh: <code>/hoi</code>, <code>/sp</code>, <code>/chinhsach</code>, <code>/tuvan</code>

3️⃣ <b>Chế độ Auto-Pilot (Bất tử Content - Ngày 2 cữ Sáng & Chiều):</b>
- Mỗi ngày 2 lần (<b>08:00 AM sáng</b> & <b>13:00 PM chiều</b>), Bot tự động bốc 1 cụm media từ Kho, phát sóng sang Kênh CTV kèm 3 góc bài viết.

4️⃣ <b>Các lệnh quản trị:</b>
- <code>/kho</code> : Xem kho ảnh/video.
- <code>/chay_ngay</code> : Kích hoạt tức thì 1 phiên phát sóng.
- <code>/saoluu</code> : Sao lưu toàn bộ kho & lịch sử lên Telegram Cloud.
- <code>/khoiphuc</code> : Khôi phục dữ liệu từ bản sao lưu Telegram Cloud.
- <code>/status</code> : Báo cáo trạng thái bot, uptime.
- <code>/history</code>: Xem 5 bài đã đăng gần nhất.
- <code>/help</code>   : Xem lại hướng dẫn này."""

# --- PUBLISHING LOGIC TO CHANNEL ---
def send_cluster_media_to_channel(target_chat_id, cluster):
    """
    Guarantees photos/videos are ALWAYS posted to the channel:
    1. Try copyMessages first (fastest, preserves formatting)
    2. If copyMessages fails (e.g. basic groups, forwarded privacy), immediately fall back
       to sendMediaGroup / sendPhoto / sendVideo using file_ids!
    """
    chat_id = cluster.get("chat_id")
    message_ids = cluster.get("message_ids", [])
    
    # 1. Try copyMessages
    if chat_id and message_ids:
        try:
            success, res = copy_messages_clean(target_chat_id, chat_id, message_ids)
            if success:
                print(f"✅ copyMessages succeeded for cluster {cluster.get('id')}")
                return True
            else:
                print(f"⚠️ copyMessages failed: {res}. Triggering direct sendMediaGroup fallback...")
        except Exception as e:
            print(f"⚠️ copyMessages exception: {e}. Triggering fallback...")

    # 2. Fallback using direct file_ids (100% reliable, zero forward restrictions)
    media_files = cluster.get("media_files", [])
    if not media_files:
        # Compatibility with older vault clusters that only have sample_file_ids
        for fid in cluster.get("sample_file_ids", []):
            media_files.append({"type": "photo", "file_id": fid})

    if not media_files:
        print(f"❌ No media files or file_ids available to post for cluster {cluster.get('id')}!")
        return False

    try:
        if len(media_files) == 1:
            item = media_files[0]
            if item["type"] == "video":
                res = requests.post(f"{TELEGRAM_API}/sendVideo", json={
                    "chat_id": str(target_chat_id),
                    "video": item["file_id"]
                }, timeout=30).json()
            else:
                res = requests.post(f"{TELEGRAM_API}/sendPhoto", json={
                    "chat_id": str(target_chat_id),
                    "photo": item["file_id"]
                }, timeout=30).json()
            return res.get("ok", False)
        else:
            # Send in groups of up to 10 media items (Telegram limit per album)
            chunks = [media_files[i:i + 10] for i in range(0, len(media_files), 10)]
            for chunk in chunks:
                input_media = []
                for m in chunk:
                    input_media.append({
                        "type": m["type"],
                        "media": m["file_id"]
                    })
                res = requests.post(f"{TELEGRAM_API}/sendMediaGroup", json={
                    "chat_id": str(target_chat_id),
                    "media": input_media
                }, timeout=40).json()
                if not res.get("ok"):
                    print(f"sendMediaGroup error: {res}")
            return True
    except Exception as e:
        print(f"Error sending fallback media to channel: {e}")
        return False

def publish_cluster_to_channel(cluster, angle_mode="ALL", ai_data=None, notify_chat_id=None, user_name=""):
    try:
        target_chat = get_target_channel()
        message_ids = cluster.get("message_ids", [])
        
        # 1. ALWAYS send media (photos/videos) first to the channel!
        send_cluster_media_to_channel(target_chat, cluster)
        
        # 2. Build and publish text content post (generate on the fly if not provided)
        if not ai_data:
            sample_bytes_list = []
            for fid in cluster.get("sample_file_ids", [])[:4]:
                b = get_file_bytes(fid)
                if b:
                    sample_bytes_list.append(b)

            custom_note = cluster.get("custom_note", "")
            if sample_bytes_list:
                ai_data = analyze_multiple_images_and_generate_content(
                    sample_bytes_list,
                    custom_note=custom_note,
                    has_video=cluster.get("has_video", False)
                )
            else:
                prompt_fallback = custom_note if custom_note else "Bài viết giới thiệu nồi chiên hơi nước 2GOOD S200 dung tích 32L, khoang Inox 304 chuẩn y tế"
                ai_data = generate_content_from_text_prompt(prompt_fallback)

        matrix = ai_data.get("content_matrix", {}) if ai_data else {}
        prod_code = ai_data.get("product_code", "2GOOD") if ai_data else "2GOOD"
        
        if angle_mode == "ALL":
            angle_used = "Trọn bộ 3 góc (Mẹ bỉm, Eat-clean, Đại lý dân dã)"
            content = f"""📢 <b>GỢI Ý CONTENT HÔM NAY CHO CTV / ĐẠI LÝ — {prod_code}</b>

━━━━━━━━━━━━━━━━━━━━━
👩‍👧 <b>GÓC 1: MẸ BỈM SỮA & NỘI TRỢ GIA ĐÌNH</b>
{matrix.get('me_bim_noi_tro', '')}

━━━━━━━━━━━━━━━━━━━━━
🥗 <b>GÓC 2: EAT-CLEAN & INOX 304 CHUẨN Y TẾ</b>
{matrix.get('eat_clean_inox304', '')}

━━━━━━━━━━━━━━━━━━━━━
🛒 <b>GÓC 3: BÀI BÁN HÀNG DÂN DÃ (ĐẠI LÝ / CTV)</b>
{matrix.get('dai_ly_dan_da', '')}
"""
        elif angle_mode == "MB":
            angle_used = "Góc 1: Mẹ bỉm sữa & Nội trợ gia đình"
            content = f"📢 <b>CONTENT MẸ BỈM & NỘI TRỢ — {prod_code}</b>\n\n{matrix.get('me_bim_noi_tro', '')}"
        elif angle_mode == "EC":
            angle_used = "Góc 2: Eat-clean & Inox 304 chuẩn y tế"
            content = f"📢 <b>CONTENT EAT-CLEAN & INOX 304 — {prod_code}</b>\n\n{matrix.get('eat_clean_inox304', '')}"
        elif angle_mode == "DL":
            angle_used = "Góc 3: Bài bán hàng dân dã, chất phác"
            content = f"📢 <b>CONTENT BÁN HÀNG THỰC CHIẾN — {prod_code}</b>\n\n{matrix.get('dai_ly_dan_da', '')}"
        else:
            angle_used = "Trọn bộ 3 góc"
            content = f"📢 <b>CONTENT 2GOOD CHO CTV</b>\n\n{matrix.get('dai_ly_dan_da', '')}"

        send_message(target_chat, content)
        
        # 3. Update Vault & Memory
        mark_cluster_posted(cluster["id"])
        media_count = len(cluster.get("media_files", [])) or len(message_ids)
        save_memory({
            "product_code": prod_code,
            "angle_used": angle_used,
            "num_media": media_count,
            "has_video": cluster.get("has_video", False),
            "date_posted": str(datetime.date.today()),
            "summary": content[:250]
        })

        if notify_chat_id:
            sender_str = f"<b>[{user_name}]</b> " if user_name else ""
            channel_title, _ = get_channel_info()
            send_message(
                notify_chat_id,
                f"✅ {sender_str}<b>ĐÃ PHÁT SÓNG THÀNH CÔNG VÀO KÊNH CTV!</b>\n"
                f"📦 <b>Media:</b> Đã copy/chuyển {media_count} file ảnh/clip\n"
                f"🎯 <b>Góc đăng:</b> {angle_used}\n"
                f"📍 <b>Kênh nhận:</b> {channel_title}"
            )
        return True
    except Exception as e:
        print(f"❌ Error in publish_cluster_to_channel: {e}")
        if notify_chat_id:
            send_message(notify_chat_id, f"❌ <b>LỖI KHI ĐĂNG VÀO KÊNH:</b> {e}")
        return False

# --- WORKER: INCOMING MEDIA CLUSTER INGESTION ---
def worker_process_incoming_cluster(cluster_items):
    if not cluster_items:
        return

    try:
        chat_id = cluster_items[0]["chat_id"]
        # notify_chat_id: nơi gửi preview + nút bấm.
        # Luôn gửi về ADMIN_CHAT_ID để đảm bảo admin nhìn thấy và bấm nút.
        # Nếu ảnh đến từ private chat của admin thì chat_id đã là ADMIN_CHAT_ID.
        notify_chat_id = ADMIN_CHAT_ID
        source_is_admin_chat = (str(chat_id) == str(ADMIN_CHAT_ID))

        message_ids = [item["message_id"] for item in cluster_items]
        media_types = [item["type"] for item in cluster_items]
        has_video = "video" in media_types
        photos_count = media_types.count("photo")
        videos_count = media_types.count("video")

        # Combine captions
        captions = [item["caption"] for item in cluster_items if item.get("caption")]
        custom_note = " ".join(dict.fromkeys(captions)).strip()

        # Collect sample file IDs for AI vision and all media files
        sample_file_ids = []
        media_files = []
        for item in cluster_items:
            fid = item.get("file_id")
            if fid:
                media_files.append({"type": item["type"], "file_id": fid})
            if item.get("sample_file_id") and item["sample_file_id"] not in sample_file_ids:
                sample_file_ids.append(item["sample_file_id"])

        # 1. Add to Media Vault
        cluster = add_cluster_to_vault(
            chat_id=chat_id,
            message_ids=message_ids,
            media_types=media_types,
            sample_file_ids=sample_file_ids[:4],
            custom_note=custom_note,
            has_video=has_video,
            media_files=media_files
        )

        media_summary = f"{photos_count} ảnh" if videos_count == 0 else (f"{videos_count} video" if photos_count == 0 else f"{photos_count} ảnh + {videos_count} video")
        note_prompt = f" + yêu cầu: <i>\"{custom_note}\"</i>" if custom_note else ""
        senders = [item.get("sender") for item in cluster_items if item.get("sender")]
        sender_str = f" [TỪ: {senders[0]}]" if senders else ""

        ack_text = f"📦{sender_str} <b>ĐÃ LƯU CỤM ({media_summary}) VÀO KHO MEDIA!</b>\n🆔 Cụm ID: <code>{cluster['id']}</code>\n🔍 <i>Đang soi tư liệu{note_prompt} để soạn trước <b>01 BÀI TỔNG HỢP 3 GÓC</b>... Vui lòng đợi 5-8 giây!</i>"

        # Gửi xác nhận về admin. Nếu ảnh đến từ nhóm khác thì báo thêm về nhóm đó (best-effort)
        send_message(notify_chat_id, ack_text)
        if not source_is_admin_chat:
            try:
                send_message(chat_id, f"📦{sender_str} <b>ĐÃ NHẬN CỤM ({media_summary}) VÀO KHO!</b> Bot đang soạn bài viết AI...")
            except Exception:
                pass

        # 2. Download sample photos/thumbnails for Gemini AI vision
        sample_bytes_list = []
        for fid in sample_file_ids[:4]:
            b = get_file_bytes(fid)
            if b:
                sample_bytes_list.append(b)

        # 3. Call AI
        if sample_bytes_list:
            ai_data = analyze_multiple_images_and_generate_content(sample_bytes_list, custom_note=custom_note, has_video=has_video)
        else:
            prompt = custom_note if custom_note else "Giới thiệu nồi chiên hơi nước 2GOOD S200 dung tích lớn 32L, khoang Inox 304 chuẩn y tế"
            ai_data = generate_content_from_text_prompt(prompt)

        if not ai_data:
            send_message(notify_chat_id, f"⚠️ Cụm media đã được lưu an toàn vào Kho (ID: <code>{cluster['id']}</code>) nhưng AI gặp lỗi tạm thời khi soạn bản xem trước. Bot sẽ tự động lấy ra phát sóng theo lịch Auto-Pilot (08:00 AM & 13:00 PM).")
            return

        # 4. Save to pending posts for admin actions
        with PENDING_LOCK:
            PENDING_POSTS[cluster["id"]] = {
                "cluster": cluster,
                "data": ai_data,
                "timestamp": time.time(),
                "created_at": str(datetime.datetime.now())
            }
            save_pending_posts()

        matrix = ai_data.get("content_matrix", {})
        me_bim = matrix.get("me_bim_noi_tro", "N/A")
        eat_clean = matrix.get("eat_clean_inox304", "N/A")
        dai_ly = matrix.get("dai_ly_dan_da", "N/A")

        preview_text = f"""🌟 <b>ĐÃ SOẠN XONG BẢN DUYỆT CỤM {cluster['id']} ({media_summary}) — {ai_data.get('product_code', '2GOOD')}!</b>

<b>📌 FACT KỸ THUẬT:</b> {ai_data.get('technical_fact', '')}
<b>💡 CLAIM THỰC TẾ:</b> {ai_data.get('marketing_claim', '')}

━━━━━━━━━━━━━━━━━━━━━
👩‍👧 <b>GÓC 1 (MẸ BỈM SỮA & NỘI TRỢ GIA ĐÌNH):</b>
{me_bim}

━━━━━━━━━━━━━━━━━━━━━
🥗 <b>GÓC 2 (EAT-CLEAN, HEALTHY & INOX 304 CHUẨN Y TẾ):</b>
{eat_clean}

━━━━━━━━━━━━━━━━━━━━━
🛒 <b>GÓC 3 (ĐẠI LÝ / CTV BÁN HÀNG DÂN DÃ, CHẤT PHÁC):</b>
{dai_ly}
"""

        inline_keyboard = {
            "inline_keyboard": [
                [
                    {"text": "🚀 BẮN NGAY VÀO KÊNH CTV (COPY SẠCH MEDIA)", "callback_data": f"PUB_CLUSTER_ALL_{cluster['id']}"}
                ],
                [
                    {"text": "📦 ĐÃ LƯU KHO (ĐỂ 8H SÁNG TỰ ĐĂNG)", "callback_data": f"KEEP_VAULT_{cluster['id']}"}
                ],
                [
                    {"text": "👩‍👧 Chỉ đăng Góc 1", "callback_data": f"PUB_CLUSTER_MB_{cluster['id']}"},
                    {"text": "🥗 Chỉ đăng Góc 2", "callback_data": f"PUB_CLUSTER_EC_{cluster['id']}"}
                ],
                [
                    {"text": "🛒 Chỉ đăng Góc 3", "callback_data": f"PUB_CLUSTER_DL_{cluster['id']}"},
                    {"text": "🗑️ Xóa khỏi kho & Hủy", "callback_data": f"DEL_VAULT_{cluster['id']}"}
                ]
            ]
        }

        # Luôn gửi preview + nút bấm về ADMIN_CHAT_ID (guaranteed delivery)
        send_message(notify_chat_id, preview_text, reply_markup=inline_keyboard)
    except Exception as e:
        print(f"❌ Error in worker_process_incoming_cluster: {e}")
        try:
            send_message(ADMIN_CHAT_ID, f"⚠️ Có lỗi khi AI soạn bài: {e}")
        except Exception:
            pass

def on_debounce_timeout():
    global BUFFER_CLUSTER_ITEMS
    with BUFFER_LOCK:
        if not BUFFER_CLUSTER_ITEMS:
            return
        items_to_process = list(BUFFER_CLUSTER_ITEMS)
        BUFFER_CLUSTER_ITEMS = []

    threading.Thread(target=worker_process_incoming_cluster, args=[items_to_process], daemon=True).start()

# --- ADMIN AUTHENTICATION HELPER ---
def is_admin(user_or_chat_id, chat_type="private"):
    # Allow all interactions from private chats, groups, and supergroups
    return True

def handle_incoming_media_non_blocking(message):
    global DEBOUNCE_TIMER
    chat_id = str(message["chat"]["id"])
    chat_type = message.get("chat", {}).get("type", "private")

    media_type = None
    file_id = None
    sample_file_id = None

    if "photo" in message:
        media_type = "photo"
        file_id = message["photo"][-1]["file_id"]
        sample_file_id = file_id
    elif "video" in message:
        media_type = "video"
        video_obj = message["video"]
        file_id = video_obj["file_id"]
        thumb = video_obj.get("thumbnail")
        sample_file_id = thumb["file_id"] if thumb else file_id

    if not media_type:
        return

    sender_name = message.get("from", {}).get("first_name", "")
    sender_user = message.get("from", {}).get("username", "")
    display_sender = f"@{sender_user}" if sender_user else (sender_name or "Thành viên")

    caption = message.get("caption", "").strip()
    is_forwarded = bool(message.get("forward_date") or message.get("forward_origin") or message.get("forward_from_chat"))
    if is_forwarded:
        if not caption:
            caption = "Tư liệu chuyển tiếp: Yêu cầu ĐỔI MỚI GÓC NHÌN, ngôn từ tự nhiên, không trùng lặp"
        else:
            caption = f"Tư liệu chuyển tiếp - Ghi chú riêng: {caption}"

    item = {
        "message_id": message["message_id"],
        "chat_id": chat_id,
        "type": media_type,
        "file_id": file_id,
        "sample_file_id": sample_file_id,
        "caption": caption,
        "sender": display_sender
    }

    with BUFFER_LOCK:
        BUFFER_CLUSTER_ITEMS.append(item)
        if DEBOUNCE_TIMER and DEBOUNCE_TIMER.is_alive():
            DEBOUNCE_TIMER.cancel()
        
        DEBOUNCE_TIMER = threading.Timer(3.5, on_debounce_timeout)
        DEBOUNCE_TIMER.start()

# --- AUTO-PILOT SCHEDULER & DISPATCH ENGINE ---
def run_daily_autopilot_dispatch(manual=False, slot_name=""):
    if manual:
        trigger_name = "Thủ công (/chay_ngay)"
    elif slot_name:
        trigger_name = f"Tự động Buổi {slot_name}"
    else:
        trigger_name = "Tự động"
    send_message(ADMIN_CHAT_ID, f"⏰ <b>[AUTO-PILOT {trigger_name}]</b> Đang kiểm tra Kho Media...")

    cluster, is_rotated = get_next_cluster_for_autopilot()
    if not cluster:
        send_message(
            ADMIN_CHAT_ID,
            "⚠️ <b>[AUTO-PILOT] KHO MEDIA ĐANG TRỐNG!</b>\n\nSếp hãy gửi thêm ảnh/video vào bot để bot tự động lưu kho và phát sóng cho CTV mỗi ngày nhé."
        )
        return False

    c_type_desc = "🔄 <i>Tái sinh cụm media cũ (> 7 ngày)</i>" if is_rotated else "✨ <i>Cụm media mới tinh từ Kho</i>"
    media_summary = f"{len(cluster['message_ids'])} file ({', '.join(set(cluster.get('media_types', ['media'])))})"
    
    send_message(
        ADMIN_CHAT_ID,
        f"🎯 <b>Đã chọn cụm:</b> <code>{cluster['id']}</code>\n{c_type_desc}\n📦 Chi tiết: {media_summary}\n✍️ <i>Đang gọi AI soạn 3 góc bài viết mới...</i>"
    )

    # Download sample thumbnail/photo for AI vision
    sample_bytes_list = []
    for fid in cluster.get("sample_file_ids", []):
        b = get_file_bytes(fid)
        if b:
            sample_bytes_list.append(b)

    custom_note = cluster.get("custom_note", "")
    if is_rotated:
        rotation_note = "BÀI TÁI SINH TỪ KHO MEDIA ĐÃ ĐĂNG TRƯỚC ĐÓ: Hãy đổi mới góc nhìn hoàn toàn, nhấn mạnh các khía cạnh khác biệt, ngôn từ mới lạ, không trùng lặp."
        custom_note = f"{rotation_note} {custom_note}".strip()

    if sample_bytes_list:
        ai_data = analyze_multiple_images_and_generate_content(
            sample_bytes_list,
            custom_note=custom_note,
            has_video=cluster.get("has_video", False)
        )
    else:
        prompt_fallback = custom_note if custom_note else "Bài viết giới thiệu nồi chiên hơi nước 2GOOD S200 dung tích 32L, khoang Inox 304, mọng thịt ngoài giòn"
        ai_data = generate_content_from_text_prompt(prompt_fallback)

    if not ai_data:
        send_message(ADMIN_CHAT_ID, "❌ [AUTO-PILOT] Lỗi khi AI soạn bài viết. Hủy lượt phát sóng này.")
        return False

    # Publish cluster cleanly
    publish_cluster_to_channel(cluster, angle_mode="ALL", ai_data=ai_data)

    send_message(ADMIN_CHAT_ID, f"""🎉 <b>[AUTO-PILOT THÀNH CÔNG] ĐÃ PHÁT SÓNG VÀO KÊNH CTV!</b>

📡 <b>Kênh:</b> {get_target_channel()}
📦 <b>Media:</b> Đã copy sạch {len(cluster['message_ids'])} file (Giữ nguyên clip & ảnh gốc, không gắn mác Chuyển tiếp)
🏷️ <b>Sản phẩm:</b> {ai_data.get('product_code', '2GOOD')}
🎯 <b>Góc bài:</b> Trọn bộ 3 góc (Mẹ bỉm, Eat-clean, Đại lý dân dã)
💡 <b>Loại:</b> {'Tái sinh media cũ' if is_rotated else 'Media mới tinh'}""")
    return True

def autopilot_scheduler_loop():
    global LAST_AUTOPILOT_RUN_SLOT
    print("⏰ Khởi động luồng Auto-Pilot Scheduler (Hẹn giờ 2 cữ: Sáng 08:00 AM & Chiều 13:00 PM hàng ngày)...")
    vn_tz = datetime.timezone(datetime.timedelta(hours=7))

    # Khôi phục slot đã chạy trước đó (chống chạy 2 lần khi restart)
    if AUTOPILOT_SLOT_FILE.exists():
        try:
            LAST_AUTOPILOT_RUN_SLOT = AUTOPILOT_SLOT_FILE.read_text().strip()
            print(f"📂 Khôi phục trạng thái Auto-Pilot: slot cuối = {LAST_AUTOPILOT_RUN_SLOT}")
        except Exception:
            pass
    
    while True:
        try:
            now_vn = datetime.datetime.now(vn_tz)
            today_str = now_vn.strftime("%Y-%m-%d")
            
            # 1. Cữ Sáng: 08:00 AM VN time (8h sáng)
            if now_vn.hour == 8 and LAST_AUTOPILOT_RUN_SLOT != f"{today_str}_morning":
                LAST_AUTOPILOT_RUN_SLOT = f"{today_str}_morning"
                try:
                    AUTOPILOT_SLOT_FILE.write_text(LAST_AUTOPILOT_RUN_SLOT)
                except Exception:
                    pass
                print(f"⏰ [08:00 AM VN TIME] Bắt đầu phiên Auto-Pilot phát sóng sáng nay...")
                run_daily_autopilot_dispatch(manual=False, slot_name="SÁNG (08:00 AM)")

            # 2. Cữ Chiều: 13:00 (1h chiều) VN time
            elif now_vn.hour == 13 and LAST_AUTOPILOT_RUN_SLOT != f"{today_str}_afternoon":
                LAST_AUTOPILOT_RUN_SLOT = f"{today_str}_afternoon"
                try:
                    AUTOPILOT_SLOT_FILE.write_text(LAST_AUTOPILOT_RUN_SLOT)
                except Exception:
                    pass
                print(f"⏰ [13:00 PM VN TIME] Bắt đầu phiên Auto-Pilot phát sóng chiều nay...")
                run_daily_autopilot_dispatch(manual=False, slot_name="CHIỀU (13:00 PM)")
                
            time.sleep(30)
        except Exception as e:
            print(f"Error in scheduler loop: {e}")
            time.sleep(60)

# --- VAULT SEARCH HELPER ---
def find_cluster_in_vault(query_text=""):
    vault = load_media_vault()
    if not vault:
        return None

    q = query_text.lower().strip()

    # 1. Check if user specified a product model or dish keyword
    keywords = ["s100", "s200", "sona", "i8", "sữa hạt", "sữa", "gà", "sườn", "thịt", "bánh", "cá", "heo", "nướng", "hấp"]
    matched_keyword = None
    for kw in keywords:
        if kw in q:
            matched_keyword = kw
            break

    if matched_keyword:
        # Search for clusters matching this keyword in note or id
        for c in vault:
            note = c.get("custom_note", "").lower()
            cid = c.get("id", "").lower()
            if matched_keyword in note or matched_keyword in cid:
                return c

    # 2. Check if user asked for vault or media in general
    wants_vault = any(w in q for w in ["kho", "ảnh", "hình", "video", "clip", "dựa vào", "lấy trong", "bài có"])
    if wants_vault:
        # Return next available cluster from autopilot selector
        cluster, _ = get_next_cluster_for_autopilot()
        if cluster:
            return cluster
        return vault[-1]

    return None

# --- WORKER: PROCESS TEXT PROMPTS (SMART VAULT ATTACHMENT) ---
def worker_process_text_prompt(chat_id, text_prompt):
    # Check if text is asking for media from the Vault
    cluster = find_cluster_in_vault(text_prompt)

    if cluster:
        media_count = len(cluster.get("message_ids", []))
        types_str = ", ".join(set(cluster.get("media_types", ["media"])))
        send_message(
            chat_id,
            f"🔍 <i>Đã lấy được cụm tư liệu trong Kho (ID: <code>{cluster['id']}</code> — {media_count} file {types_str})! Đang soi ảnh/clip và soạn bài theo yêu cầu: \"<b>{text_prompt}</b>\"... Vui lòng đợi 5-8 giây!</i>"
        )

        sample_bytes_list = []
        for fid in cluster.get("sample_file_ids", []):
            b = get_file_bytes(fid)
            if b:
                sample_bytes_list.append(b)

        has_video = cluster.get("has_video", False)
        if sample_bytes_list:
            data = analyze_multiple_images_and_generate_content(
                sample_bytes_list,
                custom_note=f"YÊU CẦU TỪ SẾP: {text_prompt}",
                has_video=has_video
            )
        else:
            data = generate_content_from_text_prompt(text_prompt)

        if not data:
            send_message(chat_id, "❌ Lỗi khi AI soạn bài. Vui lòng thử lại sau vài giây!")
            return

        post_id = cluster["id"]
        with PENDING_LOCK:
            PENDING_POSTS[post_id] = {
                "cluster": cluster,
                "data": data,
                "timestamp": time.time(),
                "created_at": str(datetime.datetime.now())
            }
            save_pending_posts()

        matrix = data.get("content_matrix", {})
        me_bim = matrix.get("me_bim_noi_tro", "N/A")
        eat_clean = matrix.get("eat_clean_inox304", "N/A")
        dai_ly = matrix.get("dai_ly_dan_da", "N/A")

        preview_text = f"""🌟 <b>ĐÃ SOẠN XONG BÀI THEO YÊU CẦU (KÈM CỤM KHO {cluster['id']} — {media_count} FILE) — {data.get('product_code', '2GOOD')}!</b>

<b>📌 FACT KỸ THUẬT:</b> {data.get('technical_fact', '')}
<b>💡 CLAIM THỰC TẾ:</b> {data.get('marketing_claim', '')}

━━━━━━━━━━━━━━━━━━━━━
👩‍👧 <b>GÓC 1 (MẸ BỈM SỮA & NỘI TRỢ GIA ĐÌNH):</b>
{me_bim}

━━━━━━━━━━━━━━━━━━━━━
🥗 <b>GÓC 2 (EAT-CLEAN, HEALTHY & INOX 304 CHUẨN Y TẾ):</b>
{eat_clean}

━━━━━━━━━━━━━━━━━━━━━
🛒 <b>GÓC 3 (ĐẠI LÝ / CTV BÁN HÀNG DÂN DÃ, CHẤT PHÁC):</b>
{dai_ly}
"""

        inline_keyboard = {
            "inline_keyboard": [
                [
                    {"text": f"🚀 BẮN TRỌN BỘ 3 GÓC + {media_count} ẢNH/CLIP VÀO KÊNH CTV", "callback_data": f"PUB_CLUSTER_ALL_{post_id}"}
                ],
                [
                    {"text": "📦 Đã lưu kho (để sáng mai 8h tự đăng)", "callback_data": f"KEEP_VAULT_{post_id}"}
                ],
                [
                    {"text": "👩‍👧 Chỉ đăng Góc 1", "callback_data": f"PUB_CLUSTER_MB_{post_id}"},
                    {"text": "🥗 Chỉ đăng Góc 2", "callback_data": f"PUB_CLUSTER_EC_{post_id}"}
                ],
                [
                    {"text": "🛒 Chỉ đăng Góc 3", "callback_data": f"PUB_CLUSTER_DL_{post_id}"},
                    {"text": "❌ Hủy bài này", "callback_data": f"CANCEL_{post_id}"}
                ]
            ]
        }

        send_message(chat_id, preview_text, reply_markup=inline_keyboard)
        return

    # If user explicitly asked for vault / media but vault has no matching cluster:
    wants_vault = any(w in text_prompt.lower() for w in ["kho", "ảnh", "hình", "video", "clip", "dựa vào", "lấy trong"])
    if wants_vault:
        send_message(
            chat_id,
            "⚠️ <b>KHO MEDIA HIỆN CHƯA CÓ CỤM ẢNH/CLIP PHÙ HỢP!</b>\n\nSếp hãy gửi 1 cụm ảnh/video vào bot trước để nạp kho nhé. Tạm thời AI đang soạn bài text theo đúng yêu cầu bên dưới:"
        )

    # Standard text-only generation
    send_message(chat_id, f"✍️ <i>Đang soạn bài 2GOOD theo yêu cầu: \"<b>{text_prompt}</b>\"... Vui lòng đợi 5-8 giây!</i>")
    data = generate_content_from_text_prompt(text_prompt)
    if not data:
        send_message(chat_id, "❌ Lỗi khi AI soạn bài. Vui lòng thử lại sau vài giây!")
        return

    post_id = f"text_{int(time.time())}"
    with PENDING_LOCK:
        PENDING_POSTS[post_id] = {
            "cluster": None,
            "data": data,
            "timestamp": time.time(),
            "created_at": str(datetime.datetime.now())
        }
        save_pending_posts()

    matrix = data.get("content_matrix", {})
    me_bim = matrix.get("me_bim_noi_tro", "N/A")
    eat_clean = matrix.get("eat_clean_inox304", "N/A")
    dai_ly = matrix.get("dai_ly_dan_da", "N/A")

    preview_text = f"""🌟 <b>ĐÃ SOẠN XONG 01 BÀI THEO YÊU CẦU: \"{text_prompt[:100]}\" — {data.get('product_code', '2GOOD')}!</b>

<b>📌 FACT KỸ THUẬT:</b> {data.get('technical_fact', '')}
<b>💡 CLAIM THỰC TẾ:</b> {data.get('marketing_claim', '')}

━━━━━━━━━━━━━━━━━━━━━
👩‍👧 <b>GÓC 1 (MẸ BỈM SỮA & NỘI TRỢ GIA ĐÌNH):</b>
{me_bim}

━━━━━━━━━━━━━━━━━━━━━
🥗 <b>GÓC 2 (EAT-CLEAN, HEALTHY & INOX 304 CHUẨN Y TẾ):</b>
{eat_clean}

━━━━━━━━━━━━━━━━━━━━━
🛒 <b>GÓC 3 (ĐẠI LÝ / CTV BÁN HÀNG DÂN DÃ, CHẤT PHÁC):</b>
{dai_ly}
"""

    inline_keyboard = {
        "inline_keyboard": [
            [
                {"text": "🚀 BẮN TRỌN BỘ 3 GÓC VÀO KÊNH CTV", "callback_data": f"PUB_TEXT_ALL_{post_id}"}
            ],
            [
                {"text": "👩‍👧 Chỉ đăng Góc 1", "callback_data": f"PUB_TEXT_MB_{post_id}"},
                {"text": "🥗 Chỉ đăng Góc 2", "callback_data": f"PUB_TEXT_EC_{post_id}"}
            ],
            [
                {"text": "🛒 Chỉ đăng Góc 3", "callback_data": f"PUB_TEXT_DL_{post_id}"},
                {"text": "❌ Hủy bài này", "callback_data": f"CANCEL_{post_id}"}
            ]
        ]
    }

    send_message(chat_id, preview_text, reply_markup=inline_keyboard)

# --- WORKER: PROCESS CTV SALES CONSULTING & OBJECTION HANDLING ---
def worker_process_ctv_query(chat_id, query_text, reply_to_message_id=None, message_thread_id=None):
    try:
        from bot_engine import generate_ctv_advice
        advice = generate_ctv_advice(query_text)
        send_message(
            chat_id, 
            advice, 
            parse_mode="Markdown", 
            reply_to_message_id=reply_to_message_id,
            message_thread_id=message_thread_id
        )
    except Exception as e:
        print(f"Error in worker_process_ctv_query: {e}")
        send_message(
            chat_id, 
            "Dạ em đang gặp chút gián đoạn kết nối AI, bác vui lòng thử lại sau ít giây nhé!", 
            reply_to_message_id=reply_to_message_id,
            message_thread_id=message_thread_id
        )

# --- CALLBACK ROUTER ---
def handle_callback(callback_query):
    query_id = callback_query["id"]
    from_user = callback_query.get("from", {})
    from_user_id = str(from_user.get("id", ""))
    from_user_name = from_user.get("first_name", "Thành viên")
    data = callback_query["data"]
    
    msg_obj = callback_query.get("message", {})
    target_chat_id = str(msg_obj.get("chat", {}).get("id") or ADMIN_CHAT_ID)

    if data == "CMD_STATUS":
        text, kb = build_status_message()
        answer_callback(query_id, "Đã cập nhật trạng thái!")
        send_message(target_chat_id, text, reply_markup=kb)
        return

    if data == "CMD_KHO":
        text, kb = build_kho_message()
        answer_callback(query_id, "Đã cập nhật kho!")
        send_message(target_chat_id, text, reply_markup=kb)
        return

    if data == "CMD_RUN_AUTOPILOT":
        answer_callback(query_id, "Đang khởi chạy Auto-Pilot...")
        send_message(target_chat_id, f"🚀 <b>[{from_user_name}]</b> đã kích hoạt Auto-Pilot phát sóng ngay!")
        threading.Thread(target=run_daily_autopilot_dispatch, args=[True], daemon=True).start()
        return

    if data == "CMD_HISTORY":
        answer_callback(query_id, "Đang tải lịch sử...")
        send_message(target_chat_id, build_history_message())
        return

    if data == "CMD_RESET":
        msg = execute_reset()
        answer_callback(query_id, "Đã reset hệ thống!")
        send_message(target_chat_id, msg)
        return

    if data.startswith("CANCEL_"):
        post_id = data.replace("CANCEL_", "")
        with PENDING_LOCK:
            if post_id in PENDING_POSTS:
                del PENDING_POSTS[post_id]
                save_pending_posts()
        answer_callback(query_id, "Đã hủy bài viết.")
        send_message(target_chat_id, f"🗑️ <b>[{from_user_name}]</b> đã xóa bài nháp khỏi hàng chờ.")
        return

    if data.startswith("KEEP_VAULT_"):
        cluster_id = data.replace("KEEP_VAULT_", "")
        answer_callback(query_id, "Đã lưu kho!")
        send_message(
            target_chat_id,
            f"📦 <b>[{from_user_name}] ĐÃ LƯU CỤM {cluster_id} VÀO KHO MEDIA!</b>\nCụm này sẽ được tự động phát sóng theo lịch Auto-Pilot (08:00 AM & 13:00 PM hàng ngày)."
        )
        return

    if data.startswith("DEL_VAULT_"):
        cluster_id = data.replace("DEL_VAULT_", "")
        delete_cluster_from_vault(cluster_id)
        with PENDING_LOCK:
            if cluster_id in PENDING_POSTS:
                del PENDING_POSTS[cluster_id]
                save_pending_posts()
        answer_callback(query_id, "Đã xóa khỏi kho!")
        send_message(target_chat_id, f"🗑️ <b>[{from_user_name}]</b> đã xóa cụm <code>{cluster_id}</code> khỏi Kho Media.")
        return

    # Handle PUB_CLUSTER_* actions
    if data.startswith("PUB_CLUSTER_"):
        parts = data.split("_")
        mode = parts[2] # ALL, MB, EC, DL
        cluster_id = "_".join(parts[3:])

        target_post = None
        with PENDING_LOCK:
            target_post = PENDING_POSTS.get(cluster_id)

        answer_callback(query_id, "Đang phát sóng vào Kho Content...")
        send_message(target_chat_id, f"🚀 <i>Đang phát sóng cụm <code>{cluster_id}</code> vào Kho Content & Tài Nguyên 2GOOD...</i>")

        if not target_post:
            cluster = get_vault_cluster_by_id(cluster_id)
            if cluster:
                threading.Thread(
                    target=publish_cluster_to_channel,
                    args=[cluster, mode, None, target_chat_id, from_user_name],
                    daemon=True
                ).start()
                return
            else:
                send_message(target_chat_id, f"⚠️ Cụm bài viết <code>{cluster_id}</code> không tìm thấy trong kho.")
                return

        cluster = target_post["cluster"]
        ai_data = target_post["data"]
        
        with PENDING_LOCK:
            if cluster_id in PENDING_POSTS:
                del PENDING_POSTS[cluster_id]
                save_pending_posts()

        threading.Thread(
            target=publish_cluster_to_channel,
            args=[cluster, mode, ai_data, target_chat_id, from_user_name],
            daemon=True
        ).start()
        return

    # Handle PUB_TEXT_* actions
    if data.startswith("PUB_TEXT_"):
        parts = data.split("_")
        mode = parts[2] # ALL, MB, EC, DL
        post_id = "_".join(parts[3:])

        target_post = None
        with PENDING_LOCK:
            target_post = PENDING_POSTS.get(post_id)

        if not target_post:
            answer_callback(query_id, "Bài viết đã hết hạn.")
            send_message(target_chat_id, "⚠️ Bài nháp text đã hết hạn. Sếp hãy gõ lại yêu cầu để AI soạn bài mới nhé!")
            return

        answer_callback(query_id, "Đang phát sóng vào Kho Content...")
        send_message(target_chat_id, f"🚀 <i>Đang phát sóng bài viết vào Kho Content & Tài Nguyên 2GOOD...</i>")

        ai_data = target_post["data"]
        matrix = ai_data.get("content_matrix", {})
        prod_code = ai_data.get("product_code", "2GOOD")

        if mode == "ALL":
            content = f"""📢 <b>GỢI Ý CONTENT HÔM NAY CHO CTV / ĐẠI LÝ — {prod_code}</b>

━━━━━━━━━━━━━━━━━━━━━
👩‍👧 <b>GÓC 1: MẸ BỈM SỮA & NỘI TRỢ GIA ĐÌNH</b>
{matrix.get('me_bim_noi_tro', '')}

━━━━━━━━━━━━━━━━━━━━━
🥗 <b>GÓC 2: EAT-CLEAN & INOX 304 CHUẨN Y TẾ</b>
{matrix.get('eat_clean_inox304', '')}

━━━━━━━━━━━━━━━━━━━━━
🛒 <b>GÓC 3: BÀI BÁN HÀNG DÂN DÃ (ĐẠI LÝ / CTV)</b>
{matrix.get('dai_ly_dan_da', '')}
"""
            angle_used = "Trọn bộ 3 góc"
        elif mode == "MB":
            content = f"📢 <b>CONTENT MẸ BỈM & NỘI TRỢ — {prod_code}</b>\n\n{matrix.get('me_bim_noi_tro', '')}"
            angle_used = "Góc 1: Mẹ bỉm"
        elif mode == "EC":
            content = f"📢 <b>CONTENT EAT-CLEAN & INOX 304 — {prod_code}</b>\n\n{matrix.get('eat_clean_inox304', '')}"
            angle_used = "Góc 2: Eat-clean"
        elif mode == "DL":
            content = f"📢 <b>CONTENT BÁN HÀNG THỰC CHIẾN — {prod_code}</b>\n\n{matrix.get('dai_ly_dan_da', '')}"
            angle_used = "Góc 3: Đại lý dân dã"
        else:
            content = matrix.get("dai_ly_dan_da", "")
            angle_used = "Đại lý dân dã"

        target_chat = get_target_channel()
        send_message(target_chat, content)
        save_memory({
            "product_code": prod_code,
            "angle_used": angle_used,
            "num_media": 0,
            "has_video": False,
            "date_posted": str(datetime.date.today()),
            "summary": content[:250]
        })

        with PENDING_LOCK:
            if post_id in PENDING_POSTS:
                del PENDING_POSTS[post_id]
                save_pending_posts()

        send_message(
            target_chat_id,
            f"✅ <b>[{from_user_name}] ĐÃ PHÁT SÓNG THÀNH CÔNG VÀO KHO CONTENT!</b>\n"
            f"📝 <b>Định dạng:</b> Bài viết text (0 media)\n"
            f"🎯 <b>Góc đăng:</b> {angle_used}\n"
            f"📍 <b>Kênh nhận:</b> KHO CONTENT & TÀI NGUYÊN 2GOOD"
        )
        return

# --- MAIN BOT ENGINE & POLLING LOOP ---
def run_bot():
    acquire_single_instance_lock()
    print(f"🚀 2GOOD TELEGRAM BOT (24/7 ROBUST ENGINE & MEDIA VAULT) IS RUNNING (PID: {os.getpid()})...")
    
    # 0. Automatically restore database from Telegram Cloud Backup (Pinned message)
    try:
        from storage_sync import restore_vault_from_telegram
        print("🔄 Đang kiểm tra và khôi phục dữ liệu từ Telegram Cloud Backup...")
        restored, v_count, m_count = restore_vault_from_telegram()
        if restored:
            print(f"🎉 Khôi phục hoàn tất: {v_count} cụm media & {m_count} bài viết sẵn sàng hoạt động!")
    except Exception as e:
        print(f"⚠️ Không thể khôi phục từ Telegram: {e}")

    load_pending_posts()

    # 1. Start HTTP Health check for Cloud Hosting
    threading.Thread(target=start_health_server, daemon=True).start()

    # 2. Start 08:00 AM Auto-Pilot Scheduler
    threading.Thread(target=autopilot_scheduler_loop, daemon=True).start()

    try:
        requests.post(f"{TELEGRAM_API}/deleteWebhook?drop_pending_updates=false", timeout=10)
    except Exception:
        pass
    
    offset = 0
    consecutive_errors = 0
    last_cleanup_time = time.time()
    allowed_update_types = ["message", "edited_message", "channel_post", "edited_channel_post", "callback_query", "my_chat_member"]
    
    try:
        while True:
            if time.time() - last_cleanup_time > 900:
                cleanup_expired_pending_posts()
                last_cleanup_time = time.time()

            try:
                res = requests.post(
                    f"{TELEGRAM_API}/getUpdates",
                    json={
                        "offset": offset,
                        "timeout": 30,
                        "allowed_updates": allowed_update_types
                    },
                    timeout=40
                ).json()
                if res.get("ok"):
                    consecutive_errors = 0
                    for update in res["result"]:
                        offset = update["update_id"] + 1
                        
                        summary = {
                            "time": datetime.datetime.now().strftime("%H:%M:%S"),
                            "id": update.get("update_id"),
                        }
                        if "message" in update:
                            m = update["message"]
                            summary["type"] = "message"
                            summary["chat_id"] = m.get("chat", {}).get("id")
                            summary["chat_title"] = m.get("chat", {}).get("title")
                            summary["text"] = m.get("text")
                            summary["thread_id"] = m.get("message_thread_id")
                        elif "callback_query" in update:
                            cq = update["callback_query"]
                            summary["type"] = "callback_query"
                            summary["data"] = cq.get("data")
                            summary["from"] = cq.get("from", {}).get("first_name")
                            summary["chat_id"] = cq.get("message", {}).get("chat", {}).get("id")
                        RECENT_UPDATES.append(summary)
                        if len(RECENT_UPDATES) > 15:
                            RECENT_UPDATES.pop(0)
                        
                        if "channel_post" in update:
                            c_post = update["channel_post"]
                            chat = c_post["chat"]
                            c_id = chat["id"]
                            c_title = chat.get("title", "Kênh CTV")
                            set_target_channel(c_id, c_title)
                        
                        elif "my_chat_member" in update:
                            chat = update["my_chat_member"]["chat"]
                            if chat.get("type") == "channel":
                                c_id = chat["id"]
                                c_title = chat.get("title", "Kênh CTV")
                                set_target_channel(c_id, c_title)
                        
                        elif "message" in update:
                            msg = update["message"]
                            chat = msg.get("chat", {})
                            chat_id = str(chat.get("id"))
                            chat_type = chat.get("type", "private")
                            msg_id = msg.get("message_id")
                            thread_id = msg.get("message_thread_id")
                            
                            # Handle incoming photo or video (from private chat or any group)
                            if "photo" in msg or "video" in msg:
                                handle_incoming_media_non_blocking(msg)
                            elif "text" in msg:
                                text = msg.get("text", "").strip()
                                cmd = text.split()[0].lower() if text else ""
                                if "@" in cmd:
                                    cmd = cmd.split("@")[0]
                                
                                # 1. Content generation requests (no need to type slash /)
                                lower_text = text.lower()
                                is_content_request = (
                                    cmd in ["/viet", "/content", "viết", "viet", "content"] or
                                    any(k in lower_text for k in ["viết bài", "viết 1 bài", "soạn bài", "làm bài", "tạo bài", "lên bài", "viết giúp"])
                                )
                                
                                # 2. Consulting / Question commands:
                                is_consulting_command = cmd in ["/hoi", "/tuvan", "/sp", "/bot", "/chinhsach", "/gia", "/baohanh"]
                                
                                if cmd == "/start":
                                    send_message(chat_id, """👋 Chào bạn! Tôi là <b>Trợ lý AI Bán Hàng & Content 2GOOD (24/7)</b>.

💬 <b>Hỏi đáp bán hàng & Xử lý từ chối cho CTV:</b>
• <b>Trong nhóm:</b> Tag <code>@mr_morning_bot [câu hỏi]</code> hoặc gõ <code>/hoi [câu hỏi]</code>
• <b>Trong chat 1-1:</b> Cứ gõ thẳng câu hỏi (VD: <i>Khách chê S200 đắt, S100 bảo hành bao lâu, Sona i8 có tự rửa không...</i>)

📸 <b>Kho Media & Viết Content:</b>
• Gửi ảnh/video: Bot tự lưu vào <b>Kho Media (/kho)</b> và soạn 3 góc bài viết.
• Gõ <code>viết 1 bài [ý tưởng]</code> hoặc <code>/viet [ý tưởng]</code>: AI soạn bài bán hàng theo yêu cầu.

💡 Gõ <code>/help</code> để xem hướng dẫn đầy đủ!""", message_thread_id=thread_id)
                                elif cmd in ["/status", "/ping"]:
                                    st_msg, kb = build_status_message()
                                    send_message(chat_id, st_msg, reply_markup=kb, message_thread_id=thread_id)
                                elif cmd == "/kho":
                                    kho_msg, kb = build_kho_message()
                                    send_message(chat_id, kho_msg, reply_markup=kb, message_thread_id=thread_id)
                                elif cmd == "/chay_ngay":
                                    threading.Thread(target=run_daily_autopilot_dispatch, args=[True], daemon=True).start()
                                elif cmd == "/history":
                                    send_message(chat_id, build_history_message(), message_thread_id=thread_id)
                                elif cmd == "/reset":
                                    send_message(chat_id, execute_reset(), message_thread_id=thread_id)
                                elif cmd == "/help":
                                    send_message(chat_id, build_help_message(), message_thread_id=thread_id)
                                elif cmd in ["/saoluu", "/backup"]:
                                    from storage_sync import sync_vault_to_telegram
                                    send_message(chat_id, "⏳ <i>Đang nén dữ liệu và gửi bản sao lưu lên Telegram Cloud...</i>", message_thread_id=thread_id)
                                    ok, msg = sync_vault_to_telegram(silent=False)
                                    send_message(chat_id, f"✅ {msg}" if ok else f"❌ {msg}", message_thread_id=thread_id)
                                elif cmd in ["/khoiphuc", "/restore"]:
                                    from storage_sync import restore_vault_from_telegram
                                    send_message(chat_id, "⏳ <i>Đang tải và khôi phục dữ liệu từ bản sao lưu Telegram Cloud...</i>", message_thread_id=thread_id)
                                    ok, v_c, m_c = restore_vault_from_telegram()
                                    if ok:
                                        send_message(chat_id, f"🎉 Khôi phục thành công <b>{v_c} cụm media</b> và <b>{m_c} bài viết</b> từ Telegram Cloud!", message_thread_id=thread_id)
                                    else:
                                        send_message(chat_id, "⚠️ Không tìm thấy bản sao lưu hợp lệ được ghim trên Telegram.", message_thread_id=thread_id)
                                elif cmd == "/set_backup_channel":
                                    from storage_sync import set_backup_chat_id, get_backup_chat_id
                                    parts = text.split()
                                    if len(parts) > 1:
                                        new_id = parts[1].strip()
                                        set_backup_chat_id(new_id)
                                        send_message(chat_id, f"✅ Đã đặt kênh sao lưu vĩnh cửu thành: <code>{new_id}</code>", message_thread_id=thread_id)
                                    else:
                                        curr = get_backup_chat_id()
                                        send_message(chat_id, f"ℹ️ Kênh sao lưu hiện tại: <code>{curr}</code>\nCú pháp: <code>/set_backup_channel &lt;channel_id&gt;</code>", message_thread_id=thread_id)
                                elif is_content_request:
                                    prompt = text
                                    if prompt.lower().startswith(("/viet", "/content")):
                                        prompt = prompt[len(prompt.split()[0]):].strip()
                                    if prompt:
                                        threading.Thread(target=worker_process_text_prompt, args=[chat_id, prompt], daemon=True).start()
                                    else:
                                        send_message(chat_id, "💡 Hãy gõ kèm ý tưởng, ví dụ: <code>viết 1 bài Sona i8</code>", message_thread_id=thread_id)
                                elif is_consulting_command:
                                    query = text[len(text.split()[0]):].strip()
                                    if query:
                                        send_message(chat_id, "⏳ <i>Đang tra cứu dữ liệu sản phẩm & soạn kịch bản tư vấn...</i>", reply_to_message_id=msg_id, message_thread_id=thread_id)
                                        threading.Thread(target=worker_process_ctv_query, args=[chat_id, query, msg_id, thread_id], daemon=True).start()
                                    else:
                                        send_message(chat_id, "💡 Hãy gõ kèm câu hỏi, ví dụ: <code>/hoi Khách chê S200 đắt</code> hoặc <code>/hoi S100 có lồng đảo không</code>", reply_to_message_id=msg_id, message_thread_id=thread_id)
                                else:
                                    is_tagged = False
                                    clean_query = text
                                    chat_title = chat.get("title", "").lower()
                                    is_discussion_group = any(k in chat_title for k in ["thảo luận", "discussion", "hỏi đáp", "ctv"]) or thread_id is not None
                                    
                                    if "@mr_morning_bot" in lower_text:
                                        is_tagged = True
                                        clean_query = re.sub(r"@mr_morning_bot", "", text, flags=re.IGNORECASE).strip()
                                    elif "reply_to_message" in msg and msg["reply_to_message"].get("from", {}).get("is_bot"):
                                        is_tagged = True
                                        clean_query = text
                                    elif chat_type == "private":
                                        is_tagged = True
                                        clean_query = text
                                    elif is_discussion_group:
                                        from bot_engine import detect_intent
                                        intent = detect_intent(text)
                                        if intent in ["OBJECTION", "PRODUCT_INFO", "POLICY"]:
                                            is_tagged = True
                                            clean_query = text
                                        
                                    if is_tagged and clean_query:
                                        if any(k in clean_query.lower() for k in ["viết", "content", "soạn", "làm bài"]):
                                            threading.Thread(target=worker_process_text_prompt, args=[chat_id, clean_query], daemon=True).start()
                                        else:
                                            send_message(chat_id, "⏳ <i>Đang tra cứu dữ liệu sản phẩm & soạn kịch bản tư vấn...</i>", reply_to_message_id=msg_id, message_thread_id=thread_id)
                                            threading.Thread(target=worker_process_ctv_query, args=[chat_id, clean_query, msg_id, thread_id], daemon=True).start()
                                    else:
                                        # In production groups (e.g. 'Ném ảnh vào để sản xuất content'), any plain text is a prompt!
                                        if any(k in chat_title for k in ["content", "sản xuất", "team"]):
                                            threading.Thread(target=worker_process_text_prompt, args=[chat_id, text], daemon=True).start()
                        
                        elif "callback_query" in update:
                            handle_callback(update["callback_query"])
                else:
                    consecutive_errors += 1
                    err_desc = res.get("description", "").lower()
                    if res.get("error_code") == 409 or "webhook" in err_desc:
                        print(f"⚠️ Phát hiện Webhook xung đột: {res.get('description')}. Đang tự động xóa Webhook để khôi phục Polling...")
                        try:
                            requests.post(f"{TELEGRAM_API}/deleteWebhook?drop_pending_updates=false", timeout=10)
                            consecutive_errors = 0
                            time.sleep(1)
                            continue
                        except Exception as del_err:
                            print(f"Lỗi khi xóa webhook xung đột: {del_err}")
                    time.sleep(min(consecutive_errors * 2, 15))
                    
                time.sleep(0.3)
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as net_err:
                consecutive_errors += 1
                backoff = min(consecutive_errors * 2, 20)
                print(f"Network glitch ({net_err}). Retrying in {backoff}s...")
                time.sleep(backoff)
            except Exception as e:
                print(f"Error in polling loop: {e}")
                time.sleep(2)
    finally:
        release_single_instance_lock()

if __name__ == "__main__":
    run_bot()
