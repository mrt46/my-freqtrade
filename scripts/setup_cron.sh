#!/bin/bash

# Setup cron jobs for automated monitoring

echo "Setting up automated monitoring..."

# Create cron jobs
CRON_FILE="/tmp/freqtrade_cron"

cat > "$CRON_FILE" << 'EOF'
# Freqtrade Bot Monitoring
# Health check every 15 minutes
*/15 * * * * /home/user/my-freqtrade/scripts/health_check.sh

# Daily performance report at 9 AM
0 9 * * * /home/user/my-freqtrade/scripts/performance_report.sh

# Weekly full report on Sundays at 10 AM
0 10 * * 0 /home/user/my-freqtrade/scripts/performance_report.sh

EOF

# Install cron jobs
crontab -l > /tmp/current_cron 2>/dev/null || true
cat /tmp/current_cron "$CRON_FILE" | crontab -

echo "Cron jobs installed successfully!"
echo ""
echo "Scheduled tasks:"
echo "  - Health check: Every 15 minutes"
echo "  - Daily report: 9:00 AM"
echo "  - Weekly report: Sunday 10:00 AM"
echo ""
echo "View cron jobs: crontab -l"
echo "Remove cron jobs: crontab -e (then delete the lines)"

rm -f "$CRON_FILE" /tmp/current_cron
