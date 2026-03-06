#!/bin/bash

# Install SSL certificate for instacart-coupons.com

echo "🔒 Installing SSL certificate..."

# Install certbot
apt-get update
apt-get install -y certbot python3-certbot-nginx

# Get SSL certificate for the domain
certbot --nginx -d instacart-coupons.com -d www.instacart-coupons.com --non-interactive --agree-tos --email admin@instacart-coupons.com --redirect

# Test auto-renewal
certbot renew --dry-run

echo "✅ SSL certificate installed successfully!"
echo "🌐 Your site is now available at:"
echo "   https://instacart-coupons.com"
echo "   https://www.instacart-coupons.com"
echo ""
echo "📋 Certificate will auto-renew before expiry"
