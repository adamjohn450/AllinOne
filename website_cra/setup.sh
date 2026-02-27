#!/bin/bash
set -e
DEPLOY_DIR="/var/www/cra"
echo "=== CRAcrypto Deploy ==="
apt-get update -qq
curl -fsSL https://deb.nodesource.com/setup_20.x | bash - >/dev/null
apt-get install -y nodejs nginx
npm install -g pm2
cd "$DEPLOY_DIR"
npm install --production
pm2 delete cracrypto 2>/dev/null || true
pm2 start api/verify-claim.js --name cracrypto --restart-delay 3000
pm2 save
pm2 startup systemd -u root --hp /root 2>/dev/null | grep "^sudo" | bash || true
cat > /etc/nginx/sites-available/cra <<'NGINXCONF'
server {
    listen 80 default_server;
    listen [::]:80 default_server;
    root /var/www/cra;
    index index.html;
    location /api/ {
        proxy_pass         http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }
    location / {
        try_files $uri $uri/ /index.html;
    }
}
NGINXCONF
ln -sf /etc/nginx/sites-available/cra /etc/nginx/sites-enabled/cra
rm -f /etc/nginx/sites-enabled/default
nginx -t && systemctl restart nginx
echo "=== DONE ==="
pm2 status cracrypto
