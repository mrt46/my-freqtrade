#!/bin/bash
# Autonomous Trading Bot - Startup Script

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}    Autonomous Trading Bot Launcher    ${NC}"
echo -e "${BLUE}========================================${NC}"

# Change to project directory
cd "$(dirname "$0")/.." || exit

# Activate virtualenv
source .venv/bin/activate || { echo "Error: .venv not found. Run: python -m venv .venv && pip install -e ."; exit 1; }

# Check if config file exists
CONFIG_FILE="user_data/config/config_full.json"
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}Error: Config file not found: $CONFIG_FILE${NC}"
    exit 1
fi

# Function to show menu
show_menu() {
    echo ""
    echo -e "${YELLOW}Select mode:${NC}"
    echo "1) Dry Run (Simulation - No real money)"
    echo "2) Live Trading (Real money - Be careful!)"
    echo "3) Backtesting"
    echo "4) Download Data"
    echo "5) List available pairs"
    echo "6) Show strategy info"
    echo "0) Exit"
    echo ""
    read -p "Enter choice [1-6]: " choice
}

# Function to start dry run
start_dry_run() {
    echo -e "${GREEN}Starting in DRY RUN mode...${NC}"
    echo -e "${YELLOW}No real money will be used.${NC}"
    python -m freqtrade trade \
        --config "$CONFIG_FILE" \
        --strategy BinanceOptimized
}

# Function to start live trading
start_live() {
    echo -e "${RED}WARNING: You are about to start LIVE trading!${NC}"
    echo -e "${RED}Real money will be at risk!${NC}"
    read -p "Type 'YES' to confirm: " confirm

    if [ "$confirm" = "YES" ]; then
        echo -e "${GREEN}Starting LIVE trading...${NC}"
        python -m freqtrade trade \
            --config "$CONFIG_FILE" \
            --strategy BinanceOptimized
    else
        echo -e "${YELLOW}Live trading cancelled.${NC}"
    fi
}

# Function to run backtesting
run_backtest() {
    echo -e "${BLUE}Starting backtesting...${NC}"
    echo -e "${YELLOW}Using offline runner (no exchange needed)${NC}"
    python run_backtest.py
}

# Function to download data
download_data() {
    echo -e "${BLUE}Downloading market data...${NC}"
    read -p "Enter number of days to download (default 30): " days
    days=${days:-30}

    python -m freqtrade download-data \
        --config "$CONFIG_FILE" \
        --days "$days" \
        --timeframes 5m 15m 1h 4h 1d
}

# Function to list pairs
list_pairs() {
    echo -e "${BLUE}Available trading pairs:${NC}"
    python -m freqtrade list-pairs \
        --config "$CONFIG_FILE" \
        --print-list
}

# Function to show strategy info
show_strategy_info() {
    echo -e "${BLUE}Strategy Information:${NC}"
    python -m freqtrade list-strategies \
        --config "$CONFIG_FILE" \
        --strategy-path user_data/strategies/adaptive
}

# Main loop
while true; do
    show_menu

    case $choice in
        1) start_dry_run ;;
        2) start_live ;;
        3) run_backtest ;;
        4) download_data ;;
        5) list_pairs ;;
        6) show_strategy_info ;;
        0)
            echo -e "${GREEN}Goodbye!${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid option. Please try again.${NC}"
            ;;
    esac

    echo ""
    read -p "Press Enter to continue..."
done
