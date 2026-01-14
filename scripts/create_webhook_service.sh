#!/bin/bash
# Script to create webhook.service file on the server

cat > /etc/systemd/system/silent-couple-bot-webhook.service << 'EOF'
[Unit]
Description=Silent Couple Bot Webhook Server
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/Silent-Couple-Bot
Environment="PATH=/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONUNBUFFERED=1"
ExecStart=/usr/bin/python3 -m src.entrypoints.webhook
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

# Security settings
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

echo "✅ Service file created at /etc/systemd/system/silent-couple-bot-webhook.service"
echo ""
echo "Next steps:"
echo "1. sudo systemctl daemon-reload"
echo "2. sudo systemctl start silent-couple-bot-webhook"
echo "3. sudo systemctl enable silent-couple-bot-webhook"
echo "4. sudo systemctl status silent-couple-bot-webhook"

