#!/bin/bash
# Install healthcheck.sh on the server and register it in cron (every 2 min).
# Run once: bash deploy/install_healthcheck.sh

set -euo pipefail

SCRIPT_SRC="$(dirname "$0")/healthcheck.sh"
SCRIPT_DST="/usr/local/bin/sbc_healthcheck.sh"
LOG_FILE="/var/log/sbc_healthcheck.log"
CRON_MARKER="sbc_healthcheck"

echo "Installing health-check script..."
cp "$SCRIPT_SRC" "$SCRIPT_DST"
chmod +x "$SCRIPT_DST"

echo "Creating log file..."
touch "$LOG_FILE"
chmod 644 "$LOG_FILE"

echo "Registering cron job (every 2 minutes)..."
# Remove old entry if exists, then add fresh one
(crontab -l 2>/dev/null | grep -v "$CRON_MARKER" ; \
 echo "*/2 * * * * /usr/local/bin/sbc_healthcheck.sh # $CRON_MARKER") | crontab -

echo ""
echo "Done! Cron entry:"
crontab -l | grep "$CRON_MARKER"
echo ""
echo "Test run:"
bash "$SCRIPT_DST"
echo ""
echo "Log file: $LOG_FILE"
echo "Check logs: tail -f $LOG_FILE"
