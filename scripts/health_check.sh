#!/bin/bash

# Health Check Script for Freqtrade Bot
# Checks bot health and sends alerts if issues detected

LOG_FILE="/home/user/my-freqtrade/user_data/logs/health_check.log"
ERROR_COUNT_FILE="/tmp/freqtrade_error_count"

# Initialize error counter
if [ ! -f "$ERROR_COUNT_FILE" ]; then
    echo "0" > "$ERROR_COUNT_FILE"
fi

ERROR_COUNT=$(cat "$ERROR_COUNT_FILE")
CURRENT_ERRORS=0

echo "[$(date)] Starting health check..." >> "$LOG_FILE"

# 1. Check if service is running
if ! systemctl is-active --quiet freqtrade-bot; then
    echo "[$(date)] ERROR: Bot service is not running!" >> "$LOG_FILE"
    CURRENT_ERRORS=$((CURRENT_ERRORS + 1))

    # Try to restart
    echo "[$(date)] Attempting to restart bot..." >> "$LOG_FILE"
    systemctl restart freqtrade-bot
    sleep 5

    if systemctl is-active --quiet freqtrade-bot; then
        echo "[$(date)] Bot successfully restarted" >> "$LOG_FILE"
    else
        echo "[$(date)] CRITICAL: Failed to restart bot!" >> "$LOG_FILE"
    fi
fi

# 2. Check for recent errors in logs
RECENT_ERRORS=$(journalctl -u freqtrade-bot --since "5 minutes ago" | grep -i "error\|exception\|critical" | wc -l)
if [ "$RECENT_ERRORS" -gt 5 ]; then
    echo "[$(date)] WARNING: $RECENT_ERRORS errors in last 5 minutes" >> "$LOG_FILE"
    CURRENT_ERRORS=$((CURRENT_ERRORS + 1))
fi

# 3. Check if bot is stuck (no activity in 1 hour)
LAST_LOG_TIME=$(journalctl -u freqtrade-bot -n 1 --output=short-unix | awk '{print $1}')
CURRENT_TIME=$(date +%s)
TIME_DIFF=$((CURRENT_TIME - LAST_LOG_TIME))

if [ "$TIME_DIFF" -gt 3600 ]; then
    echo "[$(date)] WARNING: No log activity for $((TIME_DIFF/60)) minutes" >> "$LOG_FILE"
    CURRENT_ERRORS=$((CURRENT_ERRORS + 1))
fi

# 4. Check database size
if [ -f "/home/user/my-freqtrade/user_data/tradesv3.sqlite" ]; then
    DB_SIZE=$(du -m /home/user/my-freqtrade/user_data/tradesv3.sqlite | awk '{print $1}')
    if [ "$DB_SIZE" -gt 100 ]; then
        echo "[$(date)] INFO: Database size is ${DB_SIZE}MB (consider cleanup)" >> "$LOG_FILE"
    fi
fi

# 5. Check disk space
DISK_USAGE=$(df /home/user/my-freqtrade | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -gt 90 ]; then
    echo "[$(date)] WARNING: Disk usage at ${DISK_USAGE}%" >> "$LOG_FILE"
    CURRENT_ERRORS=$((CURRENT_ERRORS + 1))
fi

# Update error count
echo "$CURRENT_ERRORS" > "$ERROR_COUNT_FILE"

# Summary
if [ "$CURRENT_ERRORS" -eq 0 ]; then
    echo "[$(date)] Health check PASSED - All systems normal" >> "$LOG_FILE"
else
    echo "[$(date)] Health check FAILED - $CURRENT_ERRORS issues detected" >> "$LOG_FILE"
fi

# Optional: Send notification if too many errors
if [ "$CURRENT_ERRORS" -gt 3 ]; then
    echo "[$(date)] ALERT: Multiple critical issues detected!" >> "$LOG_FILE"
    # Add Telegram notification here if configured
fi

exit 0
