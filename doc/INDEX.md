# 📚 Start Here - Documentation Guide

Welcome! This is your navigation hub for the Personal Automation Platform.

## 🚀 Quick Start (Choose Your Path)

**Just want it working?**
1. Read: PROJECT_SUMMARY.md (5 min overview)
2. Follow: QUICKSTART.md (10 min setup)
3. Deploy and test!

**Want to understand it first?**
1. Read: PROJECT_SUMMARY.md (complete overview)
2. Read: README.md (full architecture)
3. Then: QUICKSTART.md (deploy)

## 📖 All Documentation

### Getting Started
- **PROJECT_SUMMARY.md** ⭐ - Complete overview, what's included, costs
- **QUICKSTART.md** ⚡ - Deploy in 10 minutes
- **DEPLOYMENT.md** 🚀 - Detailed deployment for Railway/DigitalOcean/Local

### Understanding the System
- **README.md** 📚 - Full documentation (703 lines)
  - Architecture explanation
  - How modules work
  - LLM expansion guide
  - All features documented

### Building & Extending
- **CONTRIBUTING.md** 🔧 - How to add new modules
  - Step-by-step guide
  - Code templates
  - Best practices
  - Example modules

## 📂 Configuration Files

- **config.yaml** - Module settings (targets, recipes, schedules)
- **.env.example** - Environment variables template (copy to .env)
- **requirements.txt** - Python dependencies

## 🗂️ Source Code

**Main Application:**
- main.py - Entry point

**Core Infrastructure (core/):**
- database.py - SQLite management
- limitless_client.py - Limitless API
- openai_client.py - AI processing
- discord_bot.py - Discord integration
- scheduler.py - Task scheduling

**Modules (modules/):**
- base.py - Base class (all modules inherit)
- registry.py - Auto-discovery system
- nutrition.py ✅ - Complete nutrition tracking
- workout.py ✅ - Complete workout tracking

**Utilities (utils/):**
- helpers.py - Helper functions

**Deployment (deployment/):**
- railway.json - Railway config
- systemd.service - Linux service
- setup.sh - Automated VPS setup

## 🎯 Common Tasks

**Deploy the platform:**
→ Follow QUICKSTART.md

**Customize your settings:**
→ Edit config.yaml (nutrition targets, custom foods)

**Add a new module:**
→ Read CONTRIBUTING.md, use nutrition.py as template

**Troubleshoot issues:**
→ See DEPLOYMENT.md "Troubleshooting" section

## 💡 What You Have

**24 files total:**
- 5 documentation files
- 4 configuration files  
- 12 Python source files
- 3 deployment configs

**Features working out of the box:**
- ✅ Voice-activated logging
- ✅ Nutrition tracking (food, macros, hydration, sleep)
- ✅ Workout tracking (Peloton OCR, intensity)
- ✅ Image analysis
- ✅ Discord bot (two-way)
- ✅ Automated summaries
- ✅ Natural language Q&A

**Cost:** ~$7/month for unlimited modules

## 🆘 Need Help?

**Setup questions:** QUICKSTART.md or DEPLOYMENT.md
**How it works:** README.md or PROJECT_SUMMARY.md  
**Adding modules:** CONTRIBUTING.md
**Configuration:** config.yaml has inline comments

---

**Ready?** Start with PROJECT_SUMMARY.md! 🎉
