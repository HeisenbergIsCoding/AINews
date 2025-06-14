#!/bin/bash

# SSL Setup Script for AI News Application
# This script helps you set up HTTPS with Let's Encrypt SSL certificates

set -e

echo "🔒 AI News HTTPS Setup Script"
echo "=============================="

# Check if domain and email are provided
if [ $# -lt 2 ]; then
    echo "Usage: $0 <domain> <email>"
    echo "Example: $0 example.com admin@example.com"
    echo ""
    echo "For local development, you can use:"
    echo "$0 localhost admin@localhost.local"
    exit 1
fi

DOMAIN=$1
EMAIL=$2

echo "Domain: $DOMAIN"
echo "Email: $EMAIL"
echo ""

# Update docker-compose.yml with actual domain and email
echo "📝 Updating docker-compose.yml with your domain and email..."
sed -i.bak "s/your-domain\.com/$DOMAIN/g" docker-compose.yml
sed -i.bak "s/your-email@example\.com/$EMAIL/g" docker-compose.yml

# For production, remove --staging flag
if [ "$DOMAIN" != "localhost" ]; then
    echo "🌐 Setting up for production domain..."
    sed -i.bak "s/--staging //g" docker-compose.yml
else
    echo "🏠 Setting up for local development..."
fi

echo "✅ Configuration updated!"
echo ""

# Build and start services
echo "🚀 Building and starting services..."
docker-compose down
docker-compose build
docker-compose up -d frontend

# Wait for frontend to be ready
echo "⏳ Waiting for frontend service to be ready..."
sleep 10

# Run certbot to get SSL certificate
if [ "$DOMAIN" != "localhost" ]; then
    echo "🔐 Requesting SSL certificate from Let's Encrypt..."
    docker-compose run --rm certbot
    
    # Reload nginx to use the new certificate
    echo "🔄 Reloading nginx with new SSL certificate..."
    docker-compose exec frontend nginx -s reload
else
    echo "🔐 Using self-signed certificate for local development..."
fi

echo ""
echo "✅ HTTPS setup complete!"
echo ""
echo "Your application is now available at:"
echo "🌐 HTTP:  http://$DOMAIN"
echo "🔒 HTTPS: https://$DOMAIN"
echo ""

if [ "$DOMAIN" != "localhost" ]; then
    echo "📋 SSL Certificate Information:"
    docker-compose exec frontend openssl x509 -in /etc/letsencrypt/live/$DOMAIN/fullchain.pem -text -noout | grep -A 2 "Validity"
    echo ""
    echo "🔄 To renew certificates automatically, add this to your crontab:"
    echo "0 12 * * * cd $(pwd) && docker-compose run --rm certbot renew && docker-compose exec frontend nginx -s reload"
fi

echo ""
echo "🎉 Setup completed successfully!"