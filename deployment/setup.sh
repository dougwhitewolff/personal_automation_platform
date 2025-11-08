#!/bin/bash
# Setup script for Personal Automation Platform on Ubuntu/Debian

set -e

echo "================================================"
echo "  Personal Automation Platform - Setup"
echo "================================================"
echo

# Check if running as root
if [ "$EUID" -ne 0 ]; then
   echo "❌ Please run as root (use sudo)"
   exit 1
fi

# Update system
echo "📦 Updating system packages..."
apt update
apt install -y python3-pip python3-venv sqlite3 git

# Create installation directory
INSTALL_DIR="/opt/personal-automation-platform"
echo "📁 Creating installation directory: $INSTALL_DIR"
mkdir -p $INSTALL_DIR
cd $INSTALL_DIR

# Clone repository (or copy files)
echo "📥 Cloning repository..."
if [ -d ".git" ]; then
    echo "   Repository already exists, pulling latest..."
    git pull
else
    # Prompt for repository URL
    read -p "Enter repository URL (or press Enter to skip): " REPO_URL
    if [ ! -z "$REPO_URL" ]; then
        git clone $REPO_URL .
    else
        echo "   Skipping clone - please copy files manually to $INSTALL_DIR"
    fi
fi

# Create virtual environment
echo "🐍 Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "📚 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Setup environment file
if [ ! -f ".env" ]; then
    echo "⚙️  Creating .env file..."
    cp .env.example .env
    echo
    echo "❗ IMPORTANT: Edit .env file with your API keys:"
    echo "   nano $INSTALL_DIR/.env"
    echo
else
    echo "✅ .env file already exists"
fi

# Install systemd service
echo "🔧 Installing systemd service..."
cp deployment/systemd.service /etc/systemd/system/personal-automation.service

# Update WorkingDirectory in service file
sed -i "s|WorkingDirectory=.*|WorkingDirectory=$INSTALL_DIR|g" /etc/systemd/system/personal-automation.service
sed -i "s|ExecStart=.*|ExecStart=$INSTALL_DIR/venv/bin/python main.py|g" /etc/systemd/system/personal-automation.service

# Reload systemd
systemctl daemon-reload

echo
echo "================================================"
echo "  ✅ Setup Complete!"
echo "================================================"
echo
echo "Next steps:"
echo "1. Edit configuration: nano $INSTALL_DIR/.env"
echo "2. Add your API keys (Limitless, OpenAI, Discord)"
echo "3. Customize modules: nano $INSTALL_DIR/config.yaml"
echo "4. Start service: systemctl start personal-automation"
echo "5. Enable auto-start: systemctl enable personal-automation"
echo
echo "Useful commands:"
echo "• View logs: journalctl -u personal-automation -f"
echo "• Check status: systemctl status personal-automation"
echo "• Restart: systemctl restart personal-automation"
echo "• Stop: systemctl stop personal-automation"
echo
