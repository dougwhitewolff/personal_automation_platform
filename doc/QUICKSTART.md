# Quick Start Guide - Deploy in 10 Minutes

Get your Personal Automation Platform running fast!

## What You're Building

Voice-activated automation that:
- Logs food/exercise when you say "log that"
- Answers questions about your day
- Analyzes photos (Peloton screens, food plates)
- Sends automated summaries
- Runs 24/7 for ~$7/month

## Step 1: Get API Keys (5 minutes)

### Limitless API Key
1. Go to https://limitless.ai
2. Settings → Developer
3. Create API Key → Copy it

### OpenAI API Key
1. Go to https://platform.openai.com
2. API Keys → Create new key → Copy it
3. Add payment method (pay-as-you-go)

### Discord Bot
1. Go to https://discord.com/developers/applications
2. New Application → Create bot
3. Enable "Message Content Intent" (Bot settings)
4. Copy Bot Token
5. OAuth2 → URL Generator → Select "bot" + permissions
6. Invite bot to your server
7. Right-click your channel → Copy ID

## Step 2: Deploy (5 minutes)

### Option A: Railway (Recommended - Easiest)

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Deploy
cd personal-automation-platform
railway init
railway up
```

Then in Railway dashboard, add environment variables:
- LIMITLESS_API_KEY=your_key
- OPENAI_API_KEY=your_key
- DISCORD_BOT_TOKEN=your_token
- DISCORD_CHANNEL_ID=your_channel_id
- TIMEZONE=America/Los_Angeles

Done! Auto-deploys on every git push.

### Option B: Local Testing

```bash
cd personal-automation-platform

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
nano .env  # Add your API keys

# Run
python main.py
```

## Step 3: Test It! (2 minutes)

In Discord:

**Test 1 - Basic logging:**
```
You: "I had eggs for breakfast. Log that."
Bot: ✅ Logged! 140 cal, 13g protein...
```

**Test 2 - Ask a question:**
```
You: "How much protein have I eaten today?"
Bot: "You've consumed 13g of protein so far..."
```

**Test 3 - Upload an image:**
```
You: [upload Peloton screenshot] "just finished this ride"
Bot: 🚴 Peloton Workout Logged! [stats shown]
```

**Test 4 - Commands:**
```
You: !summary
Bot: [Shows daily summary from all modules]
```

## Customize Your Settings

Edit `config.yaml`:

```yaml
modules:
  nutrition:
    enabled: true
    daily_targets:
      protein_g: 150  # ← Change to your target
      fat_g: 60
      carbs:
        rest:
          min: 150
          max: 180
    
    custom_foods:  # ← Add your recipes
      - name: my_smoothie
        aliases:
          - morning smoothie
        calories: 300
        protein_g: 25
        carbs_g: 35
        fat_g: 5
```

## Troubleshooting

**Bot not responding?**
- Check Discord token is correct
- Verify channel ID is right
- Check bot has "Read Messages" permission

**"Rate limited" errors?**
- Edit .env: `POLL_INTERVAL=5` (increase from 2)

**Module not loading?**
- Check config.yaml syntax
- Verify module is `enabled: true`

## What's Next?

1. **Use it daily** - Talk to your Limitless Pendant
2. **Upload images** - Peloton stats, food plates
3. **Ask questions** - Natural language queries
4. **Customize** - Edit config.yaml for your needs
5. **Extend** - Add new modules (see CONTRIBUTING.md)

## File Structure Quick Reference

```
personal-automation-platform/
├── main.py              # Run this to start
├── config.yaml          # Your settings here
├── .env                 # API keys here (create from .env.example)
├── requirements.txt     # Dependencies
│
├── core/                # Infrastructure (don't modify)
├── modules/             # Automation modules
│   ├── nutrition.py     # Food tracking
│   └── workout.py       # Exercise tracking
└── deployment/          # Deploy configs
```

## Commands Reference

**Local development:**
```bash
python main.py              # Start platform
```

**Railway:**
```bash
railway logs               # View logs
railway up                 # Deploy updates
```

**Discord commands:**
```
!summary    # Daily summary
!help       # Show commands
```

## Success! 🎉

You now have:
- ✅ 24/7 voice automation
- ✅ Food & workout tracking  
- ✅ Image analysis
- ✅ Natural language Q&A
- ✅ Automated summaries
- ✅ Expandable platform

**Start talking to your Limitless Pendant!**

---

**Need more details?**
- Full documentation: README.md
- Deployment guide: DEPLOYMENT.md
- Adding modules: CONTRIBUTING.md
