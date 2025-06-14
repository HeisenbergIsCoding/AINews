#!/bin/bash

# SSL Certificate Renewal Script for AI News Application
# This script renews Let's Encrypt SSL certificates

set -e

echo "🔄 SSL Certificate Renewal Script"
echo "================================="

# Check if containers are running
if ! docker-compose ps | grep -q "ai-news-frontend.*Up"; then
    echo "❌ Frontend container is not running. Please start the application first."
    echo "Run: docker-compose up -d"
    exit 1
fi

echo "🔐 Renewing SSL certificates..."

# Renew certificates
docker-compose run --rm certbot renew

# Check if renewal was successful
if [ $? -eq 0 ]; then
    echo "✅ Certificate renewal successful!"
    
    # Reload nginx to use renewed certificates
    echo "🔄 Reloading nginx configuration..."
    docker-compose exec frontend nginx -s reload
    
    if [ $? -eq 0 ]; then
        echo "✅ Nginx reloaded successfully!"
        echo ""
        echo "📋 Updated certificate information:"
        docker-compose exec frontend openssl x509 -in /etc/letsencrypt/live/*/fullchain.pem -text -noout | grep -A 2 "Validity" | head -3
    else
        echo "❌ Failed to reload nginx. Please check the configuration."
        exit 1
    fi
else
    echo "❌ Certificate renewal failed. Please check the logs."
    exit 1
fi

echo ""
echo "🎉 SSL certificate renewal completed successfully!"
echo ""
echo "💡 Tip: Add this script to your crontab for automatic renewal:"
echo "0 12 * * * cd $(pwd) && ./renew_ssl.sh >> /var/log/ssl-renewal.log 2>&1"