#!/bin/bash
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "🛑 Đang dừng 2GOOD Content Engine..."

if [ -f data/supervisor.pid ]; then
    SUP_PID=$(cat data/supervisor.pid)
    kill -TERM "$SUP_PID" 2>/dev/null
    rm -f data/supervisor.pid
fi

if [ -f data/bot.pid ]; then
    BOT_PID=$(cat data/bot.pid)
    kill -TERM "$BOT_PID" 2>/dev/null
    rm -f data/bot.pid
fi

# Dọn dẹp các tiến trình python liên quan nếu còn sót
pkill -f "python3 supervisor.py" 2>/dev/null
pkill -f "python3 bot.py" 2>/dev/null

echo "✅ Đã dừng hoàn toàn Bot và Supervisor."
