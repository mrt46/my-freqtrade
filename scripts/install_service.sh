#!/bin/bash

# Freqtrade Bot Service Installation Script
# This script installs and enables the freqtrade systemd service

set -e

echo "Freqtrade Bot - Systemd Service Installer"
echo "=========================================="
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "This script must be run as root (use sudo)"
    exit 1
fi

SERVICE_FILE="/home/user/my-freqtrade/scripts/freqtrade-bot.service"
SYSTEMD_PATH="/etc/systemd/system/freqtrade-bot.service"

# Check if service file exists
if [ ! -f "$SERVICE_FILE" ]; then
    echo "Error: Service file not found at $SERVICE_FILE"
    exit 1
fi

echo "1. Copying service file to systemd..."
cp "$SERVICE_FILE" "$SYSTEMD_PATH"
echo "   Done!"

echo ""
echo "2. Reloading systemd daemon..."
systemctl daemon-reload
echo "   Done!"

echo ""
echo "3. Enabling freqtrade-bot service..."
systemctl enable freqtrade-bot.service
echo "   Done!"

echo ""
echo "=========================================="
echo "Installation complete!"
echo ""
echo "Useful commands:"
echo "  Start bot:    sudo systemctl start freqtrade-bot"
echo "  Stop bot:     sudo systemctl stop freqtrade-bot"
echo "  Restart bot:  sudo systemctl restart freqtrade-bot"
echo "  View status:  sudo systemctl status freqtrade-bot"
echo "  View logs:    sudo journalctl -u freqtrade-bot -f"
echo ""
echo "IMPORTANT: Edit user_data/config/config_full.json before starting:"
echo "  - Add your Binance API keys"
echo "  - Set dry_run to false for live trading"
echo "  - Configure Telegram notifications (optional)"
echo ""
