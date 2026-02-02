#!/bin/bash

# Quick backtest script for BinanceOptimized strategy

STRATEGY="BinanceOptimized"
TIMEFRAME="4h"
TIMERANGE="20240101-"
CONFIG="user_data/config/config_backtest.json"

echo "=========================================="
echo "Freqtrade - Quick Backtest"
echo "=========================================="
echo "Strategy: $STRATEGY"
echo "Timeframe: $TIMEFRAME"
echo "Time range: $TIMERANGE"
echo ""

# Check if data exists
echo "1. Checking market data..."
if [ ! -d "user_data/data/binance" ] || [ -z "$(ls -A user_data/data/binance)" ]; then
    echo "No data found. Downloading..."
    freqtrade download-data \
        --exchange binance \
        --timeframe $TIMEFRAME \
        --timerange $TIMERANGE \
        --config $CONFIG
    echo "Download complete!"
else
    echo "Data found!"
fi
echo ""

# Run backtest
echo "2. Running backtest..."
echo "-------------------"
freqtrade backtesting \
    --config $CONFIG \
    --strategy $STRATEGY \
    --timeframe $TIMEFRAME \
    --timerange $TIMERANGE \
    --breakdown day

echo ""
echo "=========================================="
echo "Backtest complete!"
echo "=========================================="
