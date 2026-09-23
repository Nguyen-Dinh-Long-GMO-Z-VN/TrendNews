#!/bin/bash
# TrendNews auto-run script
# Chạy bởi cron job

PROJECT_DIR="/home/dinhlong-vnlab/Documents/TrendNews"
LOG_DIR="$PROJECT_DIR/logs"
LOG_FILE="$LOG_DIR/trenднews_$(date +%Y%m%d).log"

mkdir -p "$LOG_DIR"

echo "========================================" >> "$LOG_FILE"
echo "Start: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
echo "========================================" >> "$LOG_FILE"

cd "$PROJECT_DIR" && /usr/bin/python3 main.py >> "$LOG_FILE" 2>&1

echo "End: $(date '+%Y-%m-%d %H:%M:%S')" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Giữ log tối đa 7 ngày
find "$LOG_DIR" -name "*.log" -mtime +7 -delete
