#!/bin/bash

# Performance Report Generator
# Generates daily/weekly performance summary

REPORT_DIR="/home/user/my-freqtrade/user_data/reports"
DB_FILE="/home/user/my-freqtrade/user_data/tradesv3.sqlite"

mkdir -p "$REPORT_DIR"

REPORT_FILE="$REPORT_DIR/performance_$(date +%Y%m%d).txt"

echo "=========================================="  > "$REPORT_FILE"
echo "Freqtrade Performance Report"              >> "$REPORT_FILE"
echo "Generated: $(date)"                        >> "$REPORT_FILE"
echo "=========================================="  >> "$REPORT_FILE"
echo ""                                          >> "$REPORT_FILE"

if [ ! -f "$DB_FILE" ]; then
    echo "No trade database found yet."          >> "$REPORT_FILE"
    cat "$REPORT_FILE"
    exit 0
fi

# Check if sqlite3 is available
if ! command -v sqlite3 &> /dev/null; then
    echo "sqlite3 not installed. Install with: sudo apt install sqlite3" >> "$REPORT_FILE"
    cat "$REPORT_FILE"
    exit 1
fi

# Total Trades
echo "TRADE STATISTICS"                          >> "$REPORT_FILE"
echo "----------------"                          >> "$REPORT_FILE"

TOTAL_TRADES=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM trades WHERE is_open=0;")
OPEN_TRADES=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM trades WHERE is_open=1;")
WINNING_TRADES=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM trades WHERE is_open=0 AND close_profit_abs > 0;")
LOSING_TRADES=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM trades WHERE is_open=0 AND close_profit_abs < 0;")

echo "Total Closed Trades: $TOTAL_TRADES"       >> "$REPORT_FILE"
echo "Open Trades: $OPEN_TRADES"                >> "$REPORT_FILE"
echo "Winning Trades: $WINNING_TRADES"          >> "$REPORT_FILE"
echo "Losing Trades: $LOSING_TRADES"            >> "$REPORT_FILE"

if [ "$TOTAL_TRADES" -gt 0 ]; then
    WIN_RATE=$(echo "scale=2; $WINNING_TRADES * 100 / $TOTAL_TRADES" | bc)
    echo "Win Rate: ${WIN_RATE}%"               >> "$REPORT_FILE"
fi

echo ""                                          >> "$REPORT_FILE"

# Profit Statistics
echo "PROFIT STATISTICS"                         >> "$REPORT_FILE"
echo "-------------------"                       >> "$REPORT_FILE"

TOTAL_PROFIT=$(sqlite3 "$DB_FILE" "SELECT ROUND(SUM(close_profit_abs), 2) FROM trades WHERE is_open=0;")
AVG_PROFIT=$(sqlite3 "$DB_FILE" "SELECT ROUND(AVG(close_profit_abs), 2) FROM trades WHERE is_open=0;")
BEST_TRADE=$(sqlite3 "$DB_FILE" "SELECT ROUND(MAX(close_profit_abs), 2) FROM trades WHERE is_open=0;")
WORST_TRADE=$(sqlite3 "$DB_FILE" "SELECT ROUND(MIN(close_profit_abs), 2) FROM trades WHERE is_open=0;")

echo "Total Profit: $TOTAL_PROFIT USDT"         >> "$REPORT_FILE"
echo "Average Profit per Trade: $AVG_PROFIT USDT" >> "$REPORT_FILE"
echo "Best Trade: $BEST_TRADE USDT"             >> "$REPORT_FILE"
echo "Worst Trade: $WORST_TRADE USDT"           >> "$REPORT_FILE"

echo ""                                          >> "$REPORT_FILE"

# Recent Trades (Last 10)
echo "RECENT TRADES (Last 10)"                   >> "$REPORT_FILE"
echo "------------------------"                  >> "$REPORT_FILE"

sqlite3 -header -column "$DB_FILE" "
SELECT
    pair,
    ROUND(close_profit_abs, 2) as profit_usdt,
    ROUND(close_profit * 100, 2) as profit_pct,
    close_date
FROM trades
WHERE is_open=0
ORDER BY close_date DESC
LIMIT 10;
" >> "$REPORT_FILE"

echo ""                                          >> "$REPORT_FILE"

# Top Performing Pairs
echo "TOP PERFORMING PAIRS"                      >> "$REPORT_FILE"
echo "----------------------"                    >> "$REPORT_FILE"

sqlite3 -header -column "$DB_FILE" "
SELECT
    pair,
    COUNT(*) as trades,
    ROUND(SUM(close_profit_abs), 2) as total_profit,
    ROUND(AVG(close_profit_abs), 2) as avg_profit
FROM trades
WHERE is_open=0
GROUP BY pair
ORDER BY total_profit DESC
LIMIT 5;
" >> "$REPORT_FILE"

echo ""                                          >> "$REPORT_FILE"
echo "=========================================="  >> "$REPORT_FILE"

# Display the report
cat "$REPORT_FILE"

# Keep only last 30 reports
find "$REPORT_DIR" -name "performance_*.txt" -mtime +30 -delete

exit 0
