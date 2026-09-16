import os
import sys
import time
import json
import requests
import datetime
import threading
import signal
import http.server
from pathlib import Path
from config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID, DATA_DIR
from ai_engine import (
    analyze_multiple_images_and_generate_content,
    generate_content_from_text_prompt,
    save_memory,
    load_memory
)

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
CHANNEL_FILE = DATA_DIR / "target_channel.txt"
PID_FILE = DATA_DIR / "bot.pid"
BOT_START_TIME = time.time()

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

# --- HTTP HEALTH CHECK SERVER FOR CLOUD HOSTING (RENDER / RAILWAY / KOYEB) ---
class HealthCheckHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "application/json; charset=utf-8")
        self.end_headers()
        uptime = get_uptime_string()
        channel_title, channel_id = get_channel_info()
        resp = {
            "status": "online",
            "service": "2GOOD Content Engine",
            "uptime": uptime,
            "connected_channel": channel_title,
            "channel_id": channel_id,
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

# --- BUFFER & PENDING POSTS STATE ---
BUFFER_FILE_IDS = []
BUFFER_CAPTIONS = []
BUFFER_LOCK = threading.Lock()
DEBOUNCE_TIMER = None
PENDING_POSTS = {}
PENDING_LOCK = threading.Lock()

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
            print(f"🧹 Đã tự động dọn {len(expired_keys)} bài nháp hết hạn khỏi bộ nhớ.")

# --- TELEGRAM MESSAGING UTILITIES ---
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

def send_message(chat_id, text, reply_markup=None, parse_mode="HTML"):
    chunks = split_text_into_chunks(text)
    last_res = {}
    
    for i, chunk in enumerate(chunks):
        is_last = (i == len(chunks) - 1)
        markup = reply_markup if is_last else None
        
        payload = {
            "chat_id": chat_id,
            "text": chunk,
            "parse_mode": parse_mode
        }
        if markup:
            payload["reply_markup"] = json.dumps(markup)
            
        try:
            res = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=20).json()
            if not res.get("ok") and parse_mode:
                payload["parse_mode"] = ""
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
        data = {"chat_id": chat_id, "caption": initial_caption[:1024], "parse_mode": "HTML"}
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
        "chat_id": chat_id,
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
    
    with BUFFER_LOCK:
        buf_count = len(BUFFER_FILE_IDS)
    with PENDING_LOCK:
        pending_count = len(PENDING_POSTS)
        
    uptime = get_uptime_string()
    now_str = datetime.datetime.now().strftime("%H:%M:%S - %d/%m/%Y")

    status_text = f"""📊 <b>BÁO CÁO HỆ THỐNG 2GOOD CONTENT ENGINE (24/7)</b>

🟢 <b>Trạng thái:</b> Đang chạy ổn định (Online)
⏱ <b>Uptime:</b> {uptime}
🕒 <b>Thời gian:</b> {now_str}

━━━━━━━━━━━━━━━━━━━━━
📡 <b>Kênh CTV kết nối:</b> {channel_title}
🆔 <b>Channel ID:</b> <code>{channel_id}</code>
🤖 <b>AI Engine:</b> Google Gemini Flash (Đã nạp 3 Góc chuẩn 2GOOD)
📦 <b>Bộ đệm ảnh đang nhận:</b> {buf_count} ảnh
📝 <b>Bài nháp chờ duyệt:</b> {pending_count} bài
📚 <b>Tổng bài đã xuất bản:</b> {total_posted} bài

💡 <i>Mẹo: Bot tự động gom chùm ảnh và tạo 3 góc bài viết chân thật, dân dã.</i>"""

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🔄 Làm mới trạng thái", "callback_data": "CMD_STATUS"},
                {"text": "📜 Xem 5 bài gần nhất", "callback_data": "CMD_HISTORY"}
            ],
            [
                {"text": "🧹 Dọn sạch hàng chờ (/reset)", "callback_data": "CMD_RESET"}
            ]
        ]
    }
    return status_text, keyboard

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
        summary = item.get("summary", "")[:120].replace("\n", " ")
        lines.append(f"<b>{i}. [{date_str}] — {p_code}</b>")
        lines.append(f"   🎯 Góc: <i>{angle}</i>")
        lines.append(f"   💬 Trích đoạn: <i>{summary}...</i>\n")
        
    return "\n".join(lines)

def execute_reset():
    global BUFFER_FILE_IDS, DEBOUNCE_TIMER
    with BUFFER_LOCK:
        BUFFER_FILE_IDS = []
        if DEBOUNCE_TIMER and DEBOUNCE_TIMER.is_alive():
            DEBOUNCE_TIMER.cancel()
            DEBOUNCE_TIMER = None
            
    with PENDING_LOCK:
        count = len(PENDING_POSTS)
        PENDING_POSTS.clear()
        
    return f"🧹 <b>ĐÃ RESET HỆ THỐNG THÀNH CÔNG:</b>\n- Đã xóa sạch bộ đệm ảnh.\n- Đã giải phóng {count} bài nháp khỏi bộ nhớ RAM."

def build_help_message():
    return """📖 <b>HƯỚNG DẪN SỬ DỤNG 2GOOD CONTENT ENGINE:</b>

1️⃣ <b>Tạo bài viết tổng hợp từ nhiều ảnh:</b>
- Chọn <b>3 đến 6 ảnh</b> sản phẩm / món ăn trong máy.
- Gửi <b>cùng một lúc</b> vào khung chat này.
- AI sẽ gom trọn bộ để phân tích 1 lần và viết <b>01 BÀI TỔNG HỢP VỚI 3 GÓC CHÂN THẬT</b>:
  • 👩‍👧 <b>Góc 1:</b> Mẹ bỉm sữa & Nội trợ gia đình
  • 🥗 <b>Góc 2:</b> Eat-clean, Healthy & Inox 304 chuẩn y tế
  • 🛒 <b>Góc 3:</b> Đại lý / CTV bán hàng dân dã, chất phác

2️⃣ <b>Duyệt & Xuất bản:</b>
- Sau khi AI soạn xong, Sếp bấm nút để đăng:
  • 🚀 Bắn trọn bộ 3 góc + toàn bộ album ảnh vào Kênh CTV.
  • 👩‍👧 Chỉ đăng Góc 1 (Mẹ bỉm).
  • 🥗 Chỉ đăng Góc 2 (Eat-clean).
  • 🛒 Chỉ đăng Góc 3 (Đại lý bán hàng).
  • ❌ Hủy bài.

3️⃣ <b>Các lệnh quản trị:</b>
- <code>/status</code> : Kiểm tra bot online, uptime, kênh CTV.
- <code>/history</code>: Xem 5 bài viết đã đăng gần nhất.
- <code>/reset</code>  : Hủy buffer ảnh & làm sạch hàng chờ.
- <code>/help</code>   : Xem lại hướng dẫn này."""

# --- WORKER: PROCESS BUFFERED PHOTOS ---
def worker_process_all_buffered_photos(file_ids, custom_note=""):
    count = len(file_ids)
    note_prompt = f" + yêu cầu: <i>\"{custom_note}\"</i>" if custom_note else ""
    send_message(ADMIN_CHAT_ID, f"🔍 <i>Đang gom và soi toàn bộ <b>{count} ảnh</b>{note_prompt} để viết <b>01 BÀI TỔNG HỢP (ĐẦY ĐỦ ICON & HASHTAGS)</b>... Vui lòng đợi 5-8 giây!</i>")

    photos_bytes_list = []
    for fid in file_ids:
        b = get_file_bytes(fid)
        if b:
            photos_bytes_list.append(b)

    if not photos_bytes_list:
        send_message(ADMIN_CHAT_ID, "❌ Không tải được ảnh từ Telegram. Vui lòng gửi lại!")
        return

    data = analyze_multiple_images_and_generate_content(photos_bytes_list, custom_note=custom_note)
    if not data:
        send_message(ADMIN_CHAT_ID, "❌ Lỗi khi AI phân tích bộ ảnh (Mạng hoặc API bận). Vui lòng thử lại sau vài giây!")
        return

    post_id = f"post_{int(time.time())}"
    with PENDING_LOCK:
        PENDING_POSTS[post_id] = {
            "photos_list": photos_bytes_list,
            "data": data,
            "timestamp": time.time(),
            "created_at": str(datetime.datetime.now())
        }

    matrix = data.get("content_matrix", {})
    me_bim = matrix.get("me_bim_noi_tro", "N/A")
    eat_clean = matrix.get("eat_clean_inox304", "N/A")
    dai_ly = matrix.get("dai_ly_dan_da", "N/A")

    preview_text = f"""<b>🌟 ĐÃ SOẠN XONG 01 BÀI CHO BỘ {len(photos_bytes_list)} ẢNH — {data.get('product_code', '2GOOD')}!</b>

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
                {"text": f"🚀 BẮN TRỌN BỘ 3 GÓC + {len(photos_bytes_list)} ẢNH VÀO KÊNH CTV", "callback_data": f"PUB_ALL_{post_id}"}
            ],
            [
                {"text": "👩‍👧 Chỉ đăng Góc 1 (Mẹ bỉm)", "callback_data": f"PUB_MB_{post_id}"},
                {"text": "🥗 Chỉ đăng Góc 2 (Eat-clean)", "callback_data": f"PUB_EC_{post_id}"}
            ],
            [
                {"text": "🛒 Chỉ đăng Góc 3 (Đại lý dân dã)", "callback_data": f"PUB_DL_{post_id}"},
                {"text": "❌ Hủy bài này", "callback_data": f"CANCEL_{post_id}"}
            ]
        ]
    }

    send_message(ADMIN_CHAT_ID, preview_text, reply_markup=inline_keyboard)

def on_debounce_timeout():
    global BUFFER_FILE_IDS, BUFFER_CAPTIONS
    with BUFFER_LOCK:
        if not BUFFER_FILE_IDS:
            return
        to_process = list(BUFFER_FILE_IDS)
        BUFFER_FILE_IDS = []
        custom_note = " ".join(dict.fromkeys(BUFFER_CAPTIONS)).strip()
        BUFFER_CAPTIONS = []

    threading.Thread(target=worker_process_all_buffered_photos, args=[to_process, custom_note], daemon=True).start()

def handle_incoming_photo_non_blocking(message):
    global DEBOUNCE_TIMER
    chat_id = str(message["chat"]["id"])
    if chat_id != str(ADMIN_CHAT_ID):
        send_message(chat_id, "⚠️ Bạn không có quyền Admin.")
        return

    photos = message.get("photo", [])
    if not photos:
        return
    highest_photo = photos[-1]
    file_id = highest_photo["file_id"]
    caption = message.get("caption", "").strip()

    with BUFFER_LOCK:
        BUFFER_FILE_IDS.append(file_id)
        if caption:
            BUFFER_CAPTIONS.append(caption)
        if DEBOUNCE_TIMER and DEBOUNCE_TIMER.is_alive():
            DEBOUNCE_TIMER.cancel()
        
        DEBOUNCE_TIMER = threading.Timer(3.0, on_debounce_timeout)
        DEBOUNCE_TIMER.start()

def handle_callback(callback_query):
    query_id = callback_query["id"]
    from_user_id = str(callback_query["from"]["id"])
    data = callback_query["data"]
    
    if from_user_id != str(ADMIN_CHAT_ID):
        answer_callback(query_id, "Bạn không có quyền!")
        return

    if data == "CMD_STATUS":
        text, kb = build_status_message()
        answer_callback(query_id, "Đã cập nhật trạng thái!")
        send_message(ADMIN_CHAT_ID, text, reply_markup=kb)
        return

    if data == "CMD_HISTORY":
        answer_callback(query_id, "Đang tải lịch sử...")
        send_message(ADMIN_CHAT_ID, build_history_message())
        return

    if data == "CMD_RESET":
        msg = execute_reset()
        answer_callback(query_id, "Đã reset hệ thống!")
        send_message(ADMIN_CHAT_ID, msg)
        return

    if "CANCEL" in data:
        post_id = data.replace("CANCEL_", "")
        with PENDING_LOCK:
            if post_id in PENDING_POSTS:
                del PENDING_POSTS[post_id]
        answer_callback(query_id, "Đã hủy bài viết.")
        send_message(ADMIN_CHAT_ID, "🗑️ Đã xóa bài nháp khỏi hàng chờ.")
        return

    target_post = None
    target_pid = None
    with PENDING_LOCK:
        for pid, pdata in list(PENDING_POSTS.items()):
            if pid in data:
                target_post = pdata
                target_pid = pid
                break

    if not target_post:
        answer_callback(query_id, "Bài viết đã hết hạn hoặc đã được đăng trước đó.")
        return

    matrix = target_post["data"].get("content_matrix", {})
    photos_list = target_post["photos_list"]
    prod_code = target_post["data"].get("product_code", "2GOOD")

    content_to_publish = ""
    angle_used = ""
    if "PUB_ALL" in data:
        angle_used = "Trọn bộ 3 góc (Mẹ bỉm, Eat-clean, Đại lý dân dã)"
        content_to_publish = f"""📢 <b>GỢI Ý CONTENT HÔM NAY CHO CTV / ĐẠI LÝ — {prod_code}</b>

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
    elif "PUB_MB" in data:
        angle_used = "Góc 1: Mẹ bỉm sữa & Nội trợ gia đình"
        content_to_publish = f"📢 <b>CONTENT MẸ BỈM & NỘI TRỢ — {prod_code}</b>\n\n{matrix.get('me_bim_noi_tro', '')}"
    elif "PUB_EC" in data:
        angle_used = "Góc 2: Eat-clean & Inox 304 chuẩn y tế"
        content_to_publish = f"📢 <b>CONTENT EAT-CLEAN & INOX 304 — {prod_code}</b>\n\n{matrix.get('eat_clean_inox304', '')}"
    elif "PUB_DL" in data:
        angle_used = "Góc 3: Bài bán hàng dân dã, chất phác"
        content_to_publish = f"📢 <b>CONTENT BÁN HÀNG THỰC CHIẾN — {prod_code}</b>\n\n{matrix.get('dai_ly_dan_da', '')}"

    target_chat = get_target_channel()
    
    if photos_list:
        send_media_group(target_chat, photos_list, initial_caption=f"📸 <b>Album bộ ảnh tư liệu chuẩn gốc ({len(photos_list)} ảnh): {prod_code}</b>")
    send_message(target_chat, content_to_publish)

    save_memory({
        "product_code": prod_code,
        "angle_used": angle_used,
        "num_photos": len(photos_list),
        "date_posted": str(datetime.date.today()),
        "summary": content_to_publish[:250]
    })

    with PENDING_LOCK:
        if target_pid in PENDING_POSTS:
            del PENDING_POSTS[target_pid]

    answer_callback(query_id, "Đã phát sóng thành công!")
    send_message(ADMIN_CHAT_ID, f"✅ <b>ĐÃ ĐĂNG THÀNH CÔNG BÀI VIẾT + BỘ {len(photos_list)} ẢNH VÀO KÊNH CTV!</b>\nĐã lưu góc: <i>{angle_used}</i> vào Bộ nhớ.")

# --- WORKER: PROCESS TEXT-ONLY PROMPTS ---
def worker_process_text_prompt(chat_id, text_prompt):
    send_message(chat_id, f"✍️ <i>Đang soạn bài 2GOOD theo yêu cầu: \"<b>{text_prompt}</b>\"... Vui lòng đợi 5-8 giây!</i>")
    data = generate_content_from_text_prompt(text_prompt)
    if not data:
        send_message(chat_id, "❌ Lỗi khi AI soạn bài. Vui lòng thử lại sau vài giây!")
        return

    post_id = f"post_{int(time.time())}"
    with PENDING_LOCK:
        PENDING_POSTS[post_id] = {
            "photos_list": [],
            "data": data,
            "timestamp": time.time(),
            "created_at": str(datetime.datetime.now())
        }

    matrix = data.get("content_matrix", {})
    me_bim = matrix.get("me_bim_noi_tro", "N/A")
    eat_clean = matrix.get("eat_clean_inox304", "N/A")
    dai_ly = matrix.get("dai_ly_dan_da", "N/A")

    preview_text = f"""<b>🌟 ĐÃ SOẠN XONG 01 BÀI THEO YÊU CẦU: \"{text_prompt[:100]}\" — {data.get('product_code', '2GOOD')}!</b>

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
                {"text": "🚀 BẮN TRỌN BỘ 3 GÓC VÀO KÊNH CTV", "callback_data": f"PUB_ALL_{post_id}"}
            ],
            [
                {"text": "👩‍👧 Chỉ đăng Góc 1 (Mẹ bỉm)", "callback_data": f"PUB_MB_{post_id}"},
                {"text": "🥗 Chỉ đăng Góc 2 (Eat-clean)", "callback_data": f"PUB_EC_{post_id}"}
            ],
            [
                {"text": "🛒 Chỉ đăng Góc 3 (Đại lý dân dã)", "callback_data": f"PUB_DL_{post_id}"},
                {"text": "❌ Hủy bài này", "callback_data": f"CANCEL_{post_id}"}
            ]
        ]
    }

    send_message(chat_id, preview_text, reply_markup=inline_keyboard)

def run_bot():
    acquire_single_instance_lock()
    print(f"🚀 2GOOD TELEGRAM BOT (24/7 ROBUST ENGINE) IS RUNNING (PID: {os.getpid()})...")
    
    threading.Thread(target=start_health_server, daemon=True).start()

    try:
        requests.post(f"{TELEGRAM_API}/deleteWebhook?drop_pending_updates=true", timeout=10)
    except Exception:
        pass
    
    offset = 0
    consecutive_errors = 0
    last_cleanup_time = time.time()
    
    try:
        while True:
            if time.time() - last_cleanup_time > 900:
                cleanup_expired_pending_posts()
                last_cleanup_time = time.time()

            try:
                res = requests.get(f"{TELEGRAM_API}/getUpdates?offset={offset}&timeout=30", timeout=40).json()
                if res.get("ok"):
                    consecutive_errors = 0
                    for update in res["result"]:
                        offset = update["update_id"] + 1
                        
                        if "channel_post" in update:
                            c_post = update["channel_post"]
                            chat = c_post["chat"]
                            c_id = chat["id"]
                            c_title = chat.get("title", "Kênh CTV")
                            set_target_channel(c_id, c_title)
                        
                        elif "my_chat_member" in update:
                            chat = update["my_chat_member"]["chat"]
                            c_id = chat["id"]
                            c_title = chat.get("title", "Kênh CTV")
                            set_target_channel(c_id, c_title)
                        
                        elif "message" in update:
                            msg = update["message"]
                            chat_id = msg["chat"]["id"]
                            if chat_id != str(ADMIN_CHAT_ID):
                                send_message(chat_id, "⚠️ Bạn không có quyền Admin.")
                                continue
                            
                            if "photo" in msg:
                                handle_incoming_photo_non_blocking(msg)
                            elif "text" in msg:
                                text = msg.get("text", "").strip()
                                
                                if text == "/start":
                                    send_message(chat_id, "👋 Chào Sếp Thìn! Tôi là <b>Trợ lý AI Content Engine 2GOOD (24/7)</b>.\n\n📸 Sếp có thể:\n1️⃣ <b>Gửi 3-6 ảnh 1 lần:</b> AI gom soi và viết bài 3 góc.\n2️⃣ <b>Gõ văn bản / ý tưởng bất kỳ:</b> AI sẽ tự động viết bài theo đúng yêu cầu!\n\n💡 Gõ <code>/status</code> để kiểm tra hệ thống hoặc <code>/help</code> để xem hướng dẫn.")
                                elif text in ["/status", "/ping"]:
                                    st_msg, kb = build_status_message()
                                    send_message(chat_id, st_msg, reply_markup=kb)
                                elif text == "/history":
                                    send_message(chat_id, build_history_message())
                                elif text == "/reset":
                                    send_message(chat_id, execute_reset())
                                elif text == "/help":
                                    send_message(chat_id, build_help_message())
                                else:
                                    # Gõ text ý tưởng bất kỳ -> Tự động sinh bài theo yêu cầu
                                    threading.Thread(target=worker_process_text_prompt, args=[chat_id, text], daemon=True).start()
                        
                        elif "callback_query" in update:
                            handle_callback(update["callback_query"])
                else:
                    consecutive_errors += 1
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
