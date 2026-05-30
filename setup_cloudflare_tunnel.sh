#!/bin/bash
# Setup Cloudflare Tunnel for Razorpay Webhook Testing

echo "🌐 Setting up Cloudflare Tunnel..."

# Check if already installed
if ! command -v cloudflared &> /dev/null; then
    echo "📥 Installing cloudflared..."
    
    # For Linux/Ubuntu
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
        sudo dpkg -i cloudflared.deb
        rm cloudflared.deb
    fi
    
    # For macOS
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install cloudflare/cloudflare/cloudflared
    fi
fi

echo "✅ Cloudflared installed!"

echo ""
echo "🔐 Authenticating with Cloudflare..."
cloudflared tunnel login

echo ""
echo "🏗️  Creating tunnel..."
TUNNEL_NAME="flora-api-tunnel"
cloudflared tunnel create $TUNNEL_NAME

echo ""
echo "📝 Getting tunnel URL..."
TUNNEL_URL=$(cloudflared tunnel info $TUNNEL_NAME | grep "Tunnel URL" | awk '{print $NF}')

echo ""
echo "✅ Tunnel created!"
echo ""
echo "Your webhook URL:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "https://$TUNNEL_URL/api/v1/payments/razorpay/webhook"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "📋 To use this in production, add to .env:"
echo "RAZORPAY_WEBHOOK_URL=https://$TUNNEL_URL/api/v1/payments/razorpay/webhook"

echo ""
echo "🚀 Starting tunnel..."
cloudflared tunnel route dns $TUNNEL_NAME $TUNNEL_URL
cloudflared tunnel run $TUNNEL_NAME --url http://localhost:8000

echo ""
echo "✅ Tunnel is running!"
echo ""
echo "To stop: Press Ctrl+C"
