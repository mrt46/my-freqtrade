#!/bin/bash

# Freqtrade Bot Monitoring Script
# Displays bot status, recent trades, and performance

echo "=========================================="
echo "Freqtrade Bot - Status Monitor"
echo "=========================================="
echo ""

# Check if service is running
echo "1. Service Status:"
echo "-------------------"
if systemctl is-active --quiet freqtrade-bot; then
    echo "Status: RUNNING"
    uptime_seconds=$(systemctl show freqtrade-bot --property=ActiveEnterTimestamp --value | xargs -I {} date -d {} +%s)
    current_seconds=$(date +%s)
    uptime=$((current_seconds - uptime_seconds))
    uptime_hours=$((uptime / 3600))
    uptime_minutes=$(((uptime % 3600) / 60))
    echo "Uptime: ${uptime_hours}h ${uptime_minutes}m"
else
    echo "Status: STOPPED"
fi
echo ""

# Recent logs
echo "2. Recent Logs (Last 20 lines):"
echo "--------------------------------"
journalctl -u freqtrade-bot -n 20 --no-pager | tail -n 20
echo ""

# Trade statistics (if available)
echo "3. Quick Stats:"
echo "---------------"
if [ -f "/home/user/my-freqtrade/user_data/tradesv3.sqlite" ]; then
    echo "Database: Found"
    # Count trades (requires sqlite3)
    if command -v sqlite3 &> /dev/null; then
        total_trades=$(sqlite3 /home/user/my-freqtrade/user_data/tradesv3.sqlite "SELECT COUNT(*) FROM trades WHERE is_open=0;")
        open_trades=$(sqlite3 /home/user/my-freqtrade/user_data/tradesv3.sqlite "SELECT COUNT(*) FROM trades WHERE is_open=1;")
        echo "Closed trades: $total_trades"
        echo "Open trades: $open_trades"
    fi
else
    echo "Database: Not found (no trades yet)"
fi
echo ""

echo "=========================================="
echo "Commands:"
echo "  View live logs:  sudo journalctl -u freqtrade-bot -f"
echo "  Restart bot:     sudo systemctl restart freqtrade-bot"
echo "  Stop bot:        sudo systemctl stop freqtrade-bot"
echo "=========================================="
