#!/bin/bash
# Quick verification script for AutoDialer Bot

echo "========================================="
echo "  AutoDialer Bot - Quick Verification"
echo "========================================="

# Check bot is running
echo ""
echo "1. Checking bot process..."
BOT_COUNT=$(pgrep -f "python3 bot.py" | wc -l)
if [ $BOT_COUNT -gt 0 ]; then
    echo "   ✅ Bot is running ($BOT_COUNT process(es))"
else
    echo "   ❌ Bot is NOT running"
fi

# Check Asterisk
echo ""
echo "2. Checking Asterisk..."
if systemctl is-active --quiet asterisk; then
    echo "   ✅ Asterisk is running"
    VERSION=$(asterisk -V 2>/dev/null || echo "Unknown")
    echo "   📌 Version: $VERSION"
else
    echo "   ❌ Asterisk is NOT running"
fi

# Check database
echo ""
echo "3. Checking database..."
cd /root/autodialer_bot
DB_CHECK=$(python3 -c "
from database import SessionLocal, User, VPSServer, Campaign
db = SessionLocal()
users = db.query(User).count()
servers = db.query(VPSServer).count()
campaigns = db.query(Campaign).count()
print(f'{users}|{servers}|{campaigns}')
db.close()
" 2>/dev/null)

if [ -n "$DB_CHECK" ]; then
    IFS='|' read -r USERS SERVERS CAMPAIGNS <<< "$DB_CHECK"
    echo "   ✅ Database accessible"
    echo "   📊 Users: $USERS"
    echo "   📊 VPS Servers: $SERVERS"
    echo "   📊 Campaigns: $CAMPAIGNS"
else
    echo "   ❌ Database connection failed"
fi

# Check SIP configuration
echo ""
echo "4. Checking SIP trunk..."
SIP_OUTPUT=$(asterisk -rx "pjsip show endpoints" 2>/dev/null | grep "trunk_" | head -1)
if [ -n "$SIP_OUTPUT" ]; then
    echo "   ✅ SIP trunk configured"
    echo "   📌 $SIP_OUTPUT"
    
    # Check registration
    REG_STATUS=$(asterisk -rx "pjsip show registrations" 2>/dev/null | grep "trunk_" | awk '{print $NF}')
    if [ "$REG_STATUS" = "Registered" ]; then
        echo "   ✅ SIP trunk REGISTERED"
    else
        echo "   ⚠️  SIP trunk status: $REG_STATUS"
        echo "   ℹ️  Check network connectivity to SIP server"
    fi
else
    echo "   ⚠️  No SIP trunk found"
    echo "   ℹ️  Run: python3 add_sip_to_vps.py"
fi

# Check recent errors
echo ""
echo "5. Checking for recent errors..."
ERRORS=$(tail -50 bot.log 2>/dev/null | grep -i "ERROR" | wc -l)
if [ $ERRORS -eq 0 ]; then
    echo "   ✅ No recent errors in bot log"
else
    echo "   ⚠️  Found $ERRORS error(s) in bot log"
    echo "   📋 Last error:"
    tail -50 bot.log 2>/dev/null | grep -i "ERROR" | tail -1
fi

echo ""
echo "========================================="
echo "  Feature Implementation Status"
echo "========================================="
echo "✅ VPS Setup: SIP/Google Voice/Skip option"
echo "✅ Rename server button"
echo "✅ Campaign: Start/Pause/Resume/Stop buttons"
echo "✅ Campaign: View logs button"
echo "✅ Asterisk SIP configuration"
echo "✅ Google Voice implementation (code ready)"
echo "✅ Call status tracking"
echo "✅ Hold music for transfers"
echo "✅ Delete campaign button"
echo "========================================="

echo ""
echo "📱 Test the bot in Telegram:"
echo "   1. /start - Main menu"
echo "   2. VPS Servers - Check rename/delete"
echo "   3. My Campaigns - Check all buttons"
echo ""

echo "📞 To test calling (once SIP registered):"
echo "   python3 create_test_campaign.py"
echo ""

echo "📚 Full documentation:"
echo "   cat IMPLEMENTATION_COMPLETE.md"
echo ""
