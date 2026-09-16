#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

# Dừng process cũ nếu có
bash stop_bot.sh >/dev/null 2>&1

echo "🚀 Đang khởi động 2GOOD Content Engine 24/7 (Supervisor + Bot)..."
nohup python3 supervisor.py > data/run.log 2>&1 &
SUP_PID=$!
echo $SUP_PID > data/supervisor.pid

echo "✅ Hệ thống đã chạy ngầm thành công! (PID: $SUP_PID)"
echo "📝 Log hệ thống theo dõi tại: data/run.log"
