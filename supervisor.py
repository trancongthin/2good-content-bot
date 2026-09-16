import os
import sys
import time
import signal
import subprocess
import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
LOG_FILE = DATA_DIR / "supervisor.log"

def log_event(message):
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{ts}] {message}"
    print(formatted)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(formatted + "\n")
    except Exception:
        pass

running = True
current_process = None

def signal_handler(signum, frame):
    global running, current_process
    log_event("🛑 Nhận tín hiệu dừng từ người dùng. Đang tắt Bot an toàn...")
    running = False
    if current_process:
        try:
            current_process.terminate()
            current_process.wait(timeout=5)
        except Exception:
            try:
                current_process.kill()
            except Exception:
                pass
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def run_supervisor():
    global current_process, running
    log_event("🛡️ SUPERVISOR 24/7 ĐANG KHỞI CHẠY (WATCHDOG GIÁM SÁT BOT)...")
    
    restart_count = 0
    while running:
        log_event(f"🚀 Đang khởi động Bot (Lần chạy #{restart_count + 1})...")
        start_time = time.time()
        
        try:
            current_process = subprocess.Popen(
                [sys.executable, str(BASE_DIR / "bot.py")],
                cwd=str(BASE_DIR)
            )
            exit_code = current_process.wait()
            duration = time.time() - start_time
            
            if not running:
                break
                
            log_event(f"⚠️ Bot đã dừng (Mã thoát: {exit_code}, chạy được: {int(duration)}s).")
            restart_count += 1
            
            # Nếu crash quá nhanh (< 5 giây), chờ 5s tránh nghẽn CPU
            if duration < 5:
                log_event("⏳ Bot dừng quá nhanh, tạm dừng 5 giây trước khi thử lại...")
                time.sleep(5)
            else:
                log_event("🔄 Tự động khôi phục và chạy lại sau 2 giây...")
                time.sleep(2)
                
        except Exception as e:
            log_event(f"❌ Lỗi ngoại lệ trong Supervisor: {e}")
            time.sleep(3)

if __name__ == "__main__":
    run_supervisor()
