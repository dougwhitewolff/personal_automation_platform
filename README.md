# Personal Automation Platform

A modular, extensible platform for automating personal tracking and insights using Limitless Pendant, OpenAI, and Discord.

## 🎯 What This Does

This platform connects your Limitless Pendant's voice recordings to intelligent automations:
- **Say it once, track it automatically** - Speak naturally, data gets logged
- **Ask questions about your day** - Natural language queries against your data
- **Upload images** - OCR and vision analysis (receipts, workout stats, food plates)
- **Scheduled summaries** - Daily/weekly reports sent to Discord
- **Unlimited modules** - Add new tracking capabilities without deploying new apps

## 🏗️ Architecture

### Core Concept: One Platform, Unlimited Automations

```
┌─────────────────────────────────────────────────────────┐
│     Personal Automation Platform (Single Instance)       │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  CORE SERVICES (Shared Infrastructure):                  │
│  • Limitless API Poller  → Monitors your lifelogs       │
│  • Discord Bot           → Two-way communication         │
│  • OpenAI Client         → AI processing                 │
│  • SQLite Database       → Persistent storage            │
│  • Scheduler             → Timed tasks                   │
│                                                           │
├─────────────────────────────────────────────────────────┤
│                                                           │
│  MODULES (Pluggable, Independent):                       │
│  ✅ nutrition.py    → Food/macro tracking                │
│  ✅ workout.py      → Exercise logging                   │
│  ⬜ meetings.py     → Meeting summaries (YOU ADD)        │
│  ⬜ expenses.py     → Spending tracker (YOU ADD)         │
│  ⬜ [any module]    → Custom automation (YOU ADD)        │
│                                                           │
└─────────────────────────────────────────────────────────┘
```

### Key Design Principles

1. **Modular**: Each automation is a self-contained module
2. **Shared Infrastructure**: One database, one bot, one deployment
3. **Zero Marginal Cost**: Adding modules doesn't increase hosting cost
4. **LLM-Friendly**: Designed for AI-assisted expansion

### Data Flow

```
1. You speak → Limitless Pendant records
2. Platform polls → Detects "log that" keyword
3. Router analyzes → Determines which module(s) to activate
4. Module processes → Extracts data, stores in database
5. Confirmation sent → Discord notification with summary
6. You query → Natural language questions answered
```

## 📁 File Structure

```
personal-automation-platform/
├── README.md                    # This file
├── requirements.txt             # Python dependencies
├── .env.example                # Environment variables template
├── config.yaml                 # Module configuration
├── main.py                     # Application entry point
│
├── core/                       # Shared infrastructure
│   ├── __init__.py
│   ├── database.py             # SQLite initialization
│   ├── limitless_client.py     # Limitless API wrapper
│   ├── openai_client.py        # OpenAI interaction
│   ├── discord_bot.py          # Discord bot setup
│   └── scheduler.py            # Task scheduling
│
├── modules/                    # Pluggable modules
│   ├── __init__.py
│   ├── base.py                 # Abstract base class (ALL modules inherit)
│   ├── registry.py             # Module discovery and routing
│   ├── nutrition.py            # ✅ Food/macro tracking
│   └── workout.py              # ✅ Exercise logging
│
├── utils/                      # Helper functions
│   ├── __init__.py
│   └── helpers.py
│
└── deployment/                 # Deployment configs
    ├── railway.json
    ├── systemd.service
    └── setup.sh
```

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.9+
- Limitless Pendant with API access
- Discord account
- OpenAI API key

### 2. Installation

```bash
# Clone repository
git clone <your-repo>
cd personal-automation-platform

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys
```

### 3. Configuration

Edit `.env`:
```bash
LIMITLESS_API_KEY=your_limitless_key_here
OPENAI_API_KEY=your_openai_key_here
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_CHANNEL_ID=your_channel_id
DISCORD_WEBHOOK_URL=your_webhook_url  # For one-way notifications
TIMEZONE=America/Los_Angeles
```

Edit `config.yaml` to customize module settings:
```yaml
modules:
  nutrition:
    enabled: true
    daily_targets:
      protein: 150
      fat: 60
  
  workout:
    enabled: true
    electrolyte_threshold_minutes: 45
```

### 4. Run

```bash
python main.py
```

You should see:
```
✅ Database initialized
✅ Loaded module: nutrition
✅ Loaded module: workout
✅ Scheduler started
✅ Limitless polling started (every 2s)
✅ Discord bot connected
```

## 📚 How Modules Work

### Module Lifecycle

Every module inherits from `BaseModule` and implements these methods:

```python
class YourModule(BaseModule):
    def get_name(self) -> str:
        """Unique identifier: 'nutrition', 'workout', 'expenses'"""
    
    def get_keywords(self) -> List[str]:
        """Keywords that trigger this module: ['log that', 'track this']"""
    
    def get_question_patterns(self) -> List[str]:
        """Regex patterns for questions: [r'how much.*spent']"""
    
    def setup_database(self):
        """Create tables this module needs"""
    
    async def handle_log(self, content, lifelog_id, analysis):
        """Process "log that" command"""
    
    async def handle_query(self, query, context):
        """Answer questions"""
    
    async def handle_image(self, image_bytes, context):
        """Process uploaded images"""
    
    def get_scheduled_tasks(self):
        """Return scheduled tasks: [{'time': '20:00', 'function': self.daily_summary}]"""
    
    async def get_daily_summary(self, date_obj):
        """Return summary data for this module"""
```

### Module Registry (Automatic Discovery)

The `ModuleRegistry` automatically:
1. Loads all enabled modules
2. Routes keywords to appropriate modules
3. Collects scheduled tasks from all modules
4. Aggregates daily summaries

**You never manually wire up modules** - just add to the registry list.

## 🔧 How to Add a New Module

### Step 1: Create Module File

Create `modules/your_module.py`:

```python
from modules.base import BaseModule
from datetime import date, datetime
import json

class YourModule(BaseModule):
    """Brief description of what this module does"""
    
    def get_name(self) -> str:
        return "your_module"
    
    def get_keywords(self) -> List[str]:
        return [
            'trigger word',
            'another trigger',
            'log this thing'
        ]
    
    def get_question_patterns(self) -> List[str]:
        return [
            r'how many.*thing',
            r'what is my.*status'
        ]
    
    def setup_database(self):
        """Create your tables"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS your_table (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL,
                your_field TEXT NOT NULL,
                lifelog_id TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
    
    async def handle_log(self, content, lifelog_id, analysis):
        """Called when user says 'log that' with your keywords"""
        # Extract data from analysis
        # Store in database
        # Return confirmation
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO your_table (date, your_field, lifelog_id)
            VALUES (?, ?, ?)
        ''', (date.today(), analysis['extracted_data'], lifelog_id))
        self.conn.commit()
        
        return {"success": True, "message": "Logged!"}
    
    async def handle_query(self, query, context):
        """Answer questions about your data"""
        # Query database
        # Format response
        return "Your answer here"
    
    async def handle_image(self, image_bytes, context):
        """Process images (optional)"""
        # Use OpenAI vision
        # Extract data
        return {"extracted": "data"}
    
    def get_scheduled_tasks(self):
        """Define scheduled notifications"""
        return [
            {'time': '09:00', 'function': self.morning_reminder}
        ]
    
    async def morning_reminder(self):
        """Send morning notification"""
        # Query data
        # Send Discord message
        pass
    
    async def get_daily_summary(self, date_obj):
        """Return summary for daily digest"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM your_table WHERE date = ?', (date_obj,))
        count = cursor.fetchone()[0]
        
        return {
            'count': count,
            'summary': f"You did {count} things today"
        }
```

### Step 2: Register Module

Edit `modules/registry.py`:

```python
from modules.your_module import YourModule  # Add import

class ModuleRegistry:
    def load_modules(self):
        enabled_modules = [
            NutritionModule,
            WorkoutModule,
            YourModule,  # ← Add this line
        ]
        # ...
```

### Step 3: Add Configuration (Optional)

Edit `config.yaml`:

```yaml
modules:
  your_module:
    enabled: true
    custom_setting: value
```

### Step 4: Deploy

```bash
git add modules/your_module.py
git commit -m "Add your module"
git push

# Railway auto-deploys, or restart your instance
```

**That's it!** No changes to core infrastructure needed.

## 🤖 Guide for LLM-Assisted Development

This section is specifically designed to help AI models understand how to expand this platform.

### When a User Says: "Add expense tracking"

**LLM should output:**

1. **New file: `modules/expenses.py`**
   - Copy structure from `modules/nutrition.py` or `modules/workout.py`
   - Implement all required abstract methods
   - Create appropriate database tables in `setup_database()`
   - Define keywords: `['spent', 'paid', 'bought', 'purchased']`
   - Define question patterns: `[r'how much.*spent', r'total expenses']`

2. **Updated file: `modules/registry.py`**
   - Add import: `from modules.expenses import ExpenseModule`
   - Add to enabled_modules list: `ExpenseModule,`

3. **Updated file: `config.yaml`**
   - Add configuration section:
     ```yaml
     modules:
       expenses:
         enabled: true
         categories:
           - food
           - transport
         monthly_budget: 3000
     ```

4. **Updated file: `README.md`**
   - Add to "Current Modules" section
   - Document new keywords and commands
   - Add example usage

### Files That Almost Never Change

- ✅ `main.py` - Entry point (stable)
- ✅ `core/*.py` - Infrastructure (stable)
- ✅ `modules/base.py` - Abstract base class (stable)
- ✅ `modules/registry.py` - Only changes when adding modules
- ✅ `requirements.txt` - Only if new dependencies needed

### Files That Change Per Module

- 🔄 `modules/your_new_module.py` - NEW FILE
- 🔄 `modules/registry.py` - Add 2 lines (import + list entry)
- 🔄 `config.yaml` - Add configuration section
- 🔄 `README.md` - Document new module

### LLM Decision Tree for New Modules

```
User requests: "Add [feature] tracking"
    ↓
1. Identify data model
   - What needs to be stored?
   - What are the fields?
   - What are the relationships?
    ↓
2. Design database schema
   - CREATE TABLE statement(s)
   - Indexes if needed
    ↓
3. Identify triggers
   - What keywords activate this?
   - What questions does it answer?
   - Does it process images?
    ↓
4. Create OpenAI prompts
   - Extraction prompt (for handle_log)
   - Query prompt (for handle_query)
   - Vision prompt (for handle_image, if applicable)
    ↓
5. Design Discord output
   - Confirmation message format
   - Summary embed format
   - Scheduled notification format
    ↓
6. Implement module
   - Inherit from BaseModule
   - Implement all abstract methods
   - Add to registry
```

### Example LLM Prompts for Expansion

**Good prompt:**
> "Add a meeting notes module that extracts action items, attendees, and decisions from conversations. It should respond to 'summarize meeting' and answer questions like 'what did we decide about X?'"

**LLM outputs:**
- `modules/meetings.py` (complete implementation)
- Updated `modules/registry.py` (2-line change)
- Updated `config.yaml` (new section)
- Updated `README.md` (documentation)

**Another good prompt:**
> "Add expense tracking that detects when I say 'I spent $X on Y' and can OCR receipt images. Monthly budget alerts."

**LLM outputs:**
- `modules/expenses.py` (complete implementation)
- Updated `modules/registry.py`
- Updated `config.yaml`
- Updated `README.md`

### Template for LLM Output

When expanding the system, LLMs should respond in this format:

```markdown
## New Module: [Module Name]

### Files to Create

**modules/[module_name].py**
```python
[complete implementation]
```

### Files to Update

**modules/registry.py**
```python
# Add after other imports:
from modules.[module_name] import [ModuleName]

# In load_modules(), add to list:
enabled_modules = [
    NutritionModule,
    WorkoutModule,
    [ModuleName],  # ← NEW
]
```

**config.yaml**
```yaml
modules:
  [module_name]:
    enabled: true
    # module-specific config
```

**README.md**
[Add documentation for new module]

### Usage Examples

[Show how to use the new module]
```

## 📊 Current Modules

### 1. Nutrition Module

**Tracks:** Food intake, macros, hydration, custom recipes

**Keywords:**
- `log that` - Log food
- `check macros` - View daily totals
- `what should i eat` - Get meal recommendations

**Features:**
- Custom food database (smoothie portions)
- Image analysis for restaurant meals
- Dynamic macro targets based on training
- Real-time running totals

**Example Usage:**
```
You: "I had a large smoothie for breakfast. Log that."
Bot: ✅ Logged! 
     Today: 294 cal, 32g protein, 36g carbs
     Remaining: 1856 cal, 118g protein...

You: [uploads food photo] "ate this at dinner"
Bot: [analyzes image]
     Detected: Grilled chicken (280 cal, 52g protein)...
     React ✅ to log
```

### 2. Workout Module

**Tracks:** Exercise duration, type, calories, Peloton metrics

**Keywords:**
- `log workout` - Manual logging
- `peloton ride` - OCR stats from screenshot

**Features:**
- Peloton screenshot OCR (strive score, output, zones)
- Auto-updates daily macro targets
- Electrolyte reminders for 45+ min cardio
- Training intensity calculation

**Example Usage:**
```
You: [uploads Peloton screenshot] "just finished this ride"
Bot: 🚴 Peloton Workout Logged!
     45 min ride - Strive: 48, Output: 532
     
     🎯 Updated Targets:
     Calories: 2350 (was 2150)
     Carbs: 230-260g (was 200-220g)
     
     ⚡ Take electrolytes! (45+ min cardio)
```

## 🎨 Discord Commands

The bot responds to natural language and has these commands:

```
!summary          # Get today's complete summary (all modules)
!targets          # Show today's macro targets
!water [amount]   # Log water (or check status)
!help             # Show all commands
```

**Natural Language Examples:**
```
"How much protein have I eaten?"
"What should I have for dinner?"
"Show me my workout stats from yesterday"
"Did I hit my calorie goal?"
```

## 🔐 Security Notes

- **Never commit `.env` file** - Contains API keys
- **API keys in environment variables only**
- **SQLite database** - Stored locally, backed up separately
- **Discord bot token** - Keep secret, regenerate if exposed

## 📈 Costs

| Service | Monthly Cost |
|---------|--------------|
| Railway/DigitalOcean | $6 |
| OpenAI API (text) | ~$0.05 |
| OpenAI API (vision) | ~$0.50-1 |
| Discord | Free |
| Limitless API | Free |
| **Total** | **~$7/month** |

**Cost does NOT increase per module** - shared infrastructure.

## 🚀 Deployment

### Option 1: Railway (Easiest)

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login and deploy
railway login
railway init
railway up

# Add environment variables in dashboard
```

### Option 2: DigitalOcean

See `deployment/setup.sh` for automated setup.

### Option 3: Local (Development)

```bash
python main.py
```

## 🐛 Debugging

**Check logs:**
```bash
# Local
python main.py

# Railway
railway logs

# DigitalOcean
journalctl -u personal-automation -f
```

**Common issues:**
- `429 Error` - Rate limited, reduce polling frequency
- `Discord login failed` - Check bot token
- `Module not loading` - Check syntax in module file

## 📝 Development Workflow

1. **Local development:**
   ```bash
   python main.py  # Test locally
   ```

2. **Add/modify module:**
   ```bash
   # Edit modules/your_module.py
   # Test locally
   git add .
   git commit -m "Update module"
   ```

3. **Deploy:**
   ```bash
   git push
   # Railway auto-deploys
   ```

## 🤝 Contributing

This is a personal platform, but the architecture is designed to be:
- Modular
- Extensible
- LLM-friendly

Feel free to use this as a template for your own automation platform.

## 📄 License

MIT License - Use freely for personal projects

## 🙏 Credits

- [Limitless](https://limitless.ai) - Wearable AI pendant
- [OpenAI](https://openai.com) - AI processing
- [Discord](https://discord.com) - Communication platform

---

## 🎯 Quick Reference for LLMs

When asked to expand this system:

1. **Analyze the request** - What data needs tracking? What questions should it answer?
2. **Create new module** - Copy structure from existing modules
3. **Define data model** - CREATE TABLE statements
4. **Define triggers** - Keywords and question patterns
5. **Implement methods** - All abstract methods from BaseModule
6. **Update registry** - Add 2 lines to `modules/registry.py`
7. **Add config** - New section in `config.yaml`
8. **Document** - Update this README

**Output format:**
- Complete file contents for new modules
- Exact line changes for updated files
- Clear explanations for the user

**Remember:**
- Core infrastructure (`core/*.py`) rarely changes
- Each module is self-contained
- Database schema is defined per-module
- Modules don't interact directly (registry handles routing)
