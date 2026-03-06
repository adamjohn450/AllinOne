#!/bin/bash

# Deploy Instacart clone to VPS

echo "🚀 Deploying Instacart clone to VPS..."

# VPS details
VPS_IP="87.120.37.72"
VPS_USER="root"
VPS_DIR="/var/www/instacart"

# Create deployment package
echo "📦 Creating deployment package..."
cd /workspaces/AllinOne/instacart

# Upload files to VPS
echo "📤 Uploading files to VPS..."
sshpass -p 'Canada123$' ssh -o StrictHostKeyChecking=no $VPS_USER@$VPS_IP "mkdir -p $VPS_DIR"
sshpass -p 'Canada123$' scp -o StrictHostKeyChecking=no -r ./* $VPS_USER@$VPS_IP:$VPS_DIR/

# Install dependencies and setup on VPS
echo "⚙️ Setting up on VPS..."
sshpass -p 'Canada123$' ssh -o StrictHostKeyChecking=no $VPS_USER@$VPS_IP << 'ENDSSH'
# Install Python and dependencies
apt-get update
apt-get install -y python3 python3-pip nginx

# Install Python packages
cd /var/www/instacart
pip3 install -r requirements.txt

# Setup systemd service for bot
cat > /etc/systemd/system/instacart-bot.service << 'EOF'
[Unit]
Description=Instacart Telegram Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/var/www/instacart
ExecStart=/usr/bin/python3 /var/www/instacart/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Setup nginx
cat > /etc/nginx/sites-available/instacart << 'EOF'
server {
    listen 80;
    server_name 87.120.37.72;
    
    root /var/www/instacart;
    index index.html;
    
    location / {
        try_files $uri $uri/ =404;
    }
    
    location /api/ {
        proxy_pass http://localhost:8081;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
EOF

# Enable site
ln -sf /etc/nginx/sites-available/instacart /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Restart services
systemctl daemon-reload
systemctl enable instacart-bot
systemctl restart instacart-bot
systemctl restart nginx

echo "✅ Deployment complete!"
echo "🌐 Website: http://87.120.37.72"
echo "🤖 Bot service status:"
systemctl status instacart-bot --no-pager

ENDSSH

echo "🎉 Deployment finished!"
echo "🌐 Access your site at: http://87.120.37.72"
echo "🤖 Bot is running and monitoring Telegram"
