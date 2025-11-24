# Deployment Guide

Complete guide for deploying the Personal Automation Platform.

## Prerequisites

Before deploying, you need:

1. **Limitless Pendant** with API access
   - Sign up at https://limitless.ai
   - Pair your pendant
   - Get API key from Developer settings

2. **OpenAI API Key**
   - Sign up at https://platform.openai.com
   - Create API key
   - Add payment method (usage-based billing)

3. **Discord Bot**
   - Create application at https://discord.com/developers
   - Create bot and get token
   - Invite bot to your server
   - Get channel ID

## Quick Start (Railway - Recommended)

**Time:** 5 minutes  
**Cost:** ~$5/month

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Initialize project
railway init

# Deploy
railway up

# Set environment variables via Railway dashboard
# Add: LIMITLESS_API_KEY, OPENAI_API_KEY, DISCORD_BOT_TOKEN, DISCORD_CHANNEL_ID
```

**That's it!** Railway will auto-deploy on every git push.

## DigitalOcean Droplet

**Time:** 15 minutes  
**Cost:** $6/month

### 1. Create Droplet

- Go to https://digitalocean.com
- Create Droplet: Ubuntu 24.04, Basic ($6/mo)
- Choose region close to you
- Add SSH key
- Create

### 2. SSH and Setup

```bash
# SSH into server
ssh root@your_droplet_ip

# Download and run setup script
wget https://raw.githubusercontent.com/your-repo/setup.sh
chmod +x setup.sh
sudo ./setup.sh

# Edit environment variables
nano /opt/personal-automation-platform/.env
# Add your API keys

# Start service
systemctl start personal-automation
systemctl enable personal-automation  # Auto-start on boot

# Check status
systemctl status personal-automation

# View logs
journalctl -u personal-automation -f
```

### 3. Configure Firewall (Optional)

```bash
# Allow SSH
ufw allow 22/tcp

# Enable firewall
ufw enable
```

## Local Development

**For testing and development:**

```bash
# Clone repository
git clone your-repo-url
cd personal-automation-platform

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
nano .env  # Add your API keys

# Run
python main.py
```

## Raspberry Pi

**One-time cost:** ~$75  
**Requires:** Always-on internet connection

Same steps as DigitalOcean, but install on Raspberry Pi OS:

```bash
# On Raspberry Pi
sudo apt update
sudo apt install python3-pip python3-venv git

# Follow same setup as DigitalOcean
cd /home/pi
git clone your-repo-url
cd personal-automation-platform

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Setup as systemd service
sudo cp deployment/systemd.service /etc/systemd/system/personal-automation.service
# Edit paths to /home/pi/personal-automation-platform
sudo nano /etc/systemd/system/personal-automation.service

sudo systemctl start personal-automation
sudo systemctl enable personal-automation
```

## Environment Variables

All deployment methods require these environment variables:

```bash
# Required
LIMITLESS_API_KEY=your_limitless_key
OPENAI_API_KEY=your_openai_key
DISCORD_BOT_TOKEN=your_discord_token
DISCORD_CHANNEL_ID=your_channel_id

# Optional
DISCORD_WEBHOOK_URL=your_webhook_url  # For one-way notifications
TIMEZONE=America/Los_Angeles
POLL_INTERVAL=2  # Seconds between Limitless polls
MONGODB_URL=mongodb://localhost:27017/automation_platform  # MongoDB connection URL
```

## Discord Setup

### Create Bot

1. Go to https://discord.com/developers/applications
2. Click "New Application"
3. Go to "Bot" tab → "Add Bot"
4. Enable "Message Content Intent" under Privileged Gateway Intents
5. Copy Bot Token → Add to `DISCORD_BOT_TOKEN`

### Create Webhook (Optional)

1. In Discord, go to Server Settings → Integrations → Webhooks
2. Create webhook for your channel
3. Copy URL → Add to `DISCORD_WEBHOOK_URL`

### Invite Bot to Server

1. Go to OAuth2 → URL Generator
2. Select scopes: `bot`
3. Select permissions:
   - Read Messages/View Channels
   - Send Messages
   - Add Reactions
   - Attach Files
   - Read Message History
4. Copy generated URL, open in browser
5. Select your server and authorize

### Get Channel ID

1. Enable Developer Mode in Discord (Settings → Advanced)
2. Right-click your channel → Copy ID
3. Add to `DISCORD_CHANNEL_ID`

## Configuration

### Customize Modules

Edit `config.yaml` to customize module behavior:

```yaml
modules:
  nutrition:
    enabled: true
    daily_targets:
      protein_g: 150
      # ... customize targets
    
  workout:
    enabled: true
    electrolyte_threshold_minutes: 45
```

### Add Custom Foods

```yaml
modules:
  nutrition:
    custom_foods:
      - name: my_recipe
        aliases:
          - my smoothie
          - custom meal
        calories: 300
        protein_g: 25
        carbs_g: 30
        fat_g: 10
```

## Monitoring

### Railway

- View logs in Railway dashboard
- Automatic restarts on failure

### DigitalOcean/Self-Hosted

```bash
# View live logs
journalctl -u personal-automation -f

# Check status
systemctl status personal-automation

# Restart service
systemctl restart personal-automation

# View recent errors
journalctl -u personal-automation -p err -n 50
```

## Backup

### Database Backup

The SQLite database contains all your data:

```bash
# Local backup
cp nutrition_tracker.db nutrition_tracker.backup.db

# Automated daily backup (cron)
0 2 * * * cp /opt/personal-automation-platform/nutrition_tracker.db /opt/backups/nutrition_$(date +\%Y\%m\%d).db

# Railway backup
railway run 'cat nutrition_tracker.db' > local_backup.db
```

## Updating

### Railway

```bash
git pull
git push
# Railway auto-deploys
```

### DigitalOcean/Self-Hosted

```bash
cd /opt/personal-automation-platform
git pull
systemctl restart personal-automation
```

## Troubleshooting

### Bot Won't Start

```bash
# Check logs
journalctl -u personal-automation -f

# Common issues:
# - Missing .env variables
# - Invalid API keys
# - Discord token expired
```

### Rate Limited

```
⚠️  Rate limited - backing off for 60s
```

**Solution:** Increase `POLL_INTERVAL` in `.env` (default: 2 seconds)

### Module Not Loading

```
❌ Failed to load module nutrition
```

**Solution:**
- Check syntax in module file
- Verify module is enabled in `config.yaml`
- Check dependencies are installed

### Discord Bot Offline

**Check:**
1. Bot token is correct
2. Bot has proper permissions
3. Bot is invited to server
4. Channel ID is correct

## Security

### API Keys

- ❌ Never commit `.env` file to git
- ❌ Never share API keys publicly
- ✅ Use environment variables only
- ✅ Regenerate keys if exposed

### Database

- Contains personal health data
- Stored locally (not sent to any service)
- Backup regularly
- Keep access restricted

## Cost Breakdown

| Service | Monthly Cost |
|---------|--------------|
| Railway/DO hosting | $5-6 |
| OpenAI API (text) | ~$0.05 |
| OpenAI API (vision) | ~$0.50-1 |
| Discord | Free |
| Limitless API | Free |
| **Total** | **~$6-7/month** |

## Support

For issues:
1. Check logs first
2. Verify environment variables
3. Test modules individually
4. Check API quotas/limits

## Next Steps

After deployment:
1. Test with "log that" command
2. Upload test images
3. Check scheduled tasks run
4. Customize config for your needs
5. Add new modules as needed
