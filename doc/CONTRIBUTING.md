# Contributing Guide - Adding New Modules

This guide explains how to add new automation modules to the platform.

## Module Development Checklist

When adding a new module, you need to:

- [ ] Create module file in `modules/`
- [ ] Inherit from `BaseModule`
- [ ] Implement all abstract methods
- [ ] Define database schema
- [ ] Register in `modules/registry.py`
- [ ] Add configuration to `config.yaml`
- [ ] Document in README.md
- [ ] Test locally
- [ ] Deploy

## Step-by-Step Guide

### 1. Create Module File

Create `modules/your_module.py`:

```python
from modules.base import BaseModule
from datetime import date, datetime
from typing import Dict, List
import discord

class YourModule(BaseModule):
    """Brief description"""
    
    def get_name(self) -> str:
        return "your_module"
    
    def get_keywords(self) -> List[str]:
        return ['trigger', 'keywords', 'here']
    
    def get_question_patterns(self) -> List[str]:
        return [r'regex.*pattern', r'another.*pattern']
    
    def setup_database(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS your_table (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL,
                data TEXT NOT NULL,
                lifelog_id TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()
    
    async def handle_log(self, message_content: str, lifelog_id: str, 
                        analysis: Dict) -> Dict:
        # 1. Get context (today's transcript or specific time range)
        transcript = self.limitless_client.get_todays_transcript()
        
        # 2. Analyze with OpenAI
        prompt = """Extract [data type] from transcript.
        
TRANSCRIPT:
{transcript}

Respond with JSON:
{
  "extracted_field": "value"
}"""
        
        analysis = self.openai_client.analyze_text(
            transcript=transcript,
            module_name=self.get_name(),
            prompt_template=prompt
        )
        
        # 3. Store in database
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO your_table (date, data, lifelog_id)
            VALUES (?, ?, ?)
        ''', (date.today(), analysis['extracted_field'], lifelog_id))
        self.conn.commit()
        
        # 4. Create confirmation embed
        embed = discord.Embed(
            title="✅ Logged!",
            description="Your data was logged",
            color=0x00FF00
        )
        
        return {'embed': embed}
    
    async def handle_query(self, query: str, context: Dict) -> str:
        # Query database
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM your_table WHERE date = ?', (date.today(),))
        data = cursor.fetchall()
        
        # Use OpenAI to answer
        return self.openai_client.answer_query(
            query=query,
            context={'data': data},
            system_prompt="You are an assistant for [domain]"
        )
    
    async def handle_image(self, image_bytes: bytes, context: str) -> Dict:
        # Analyze image with OpenAI vision
        prompt = """Extract information from this image.

Respond with JSON:
{
  "field": "value"
}"""
        
        analysis = self.openai_client.analyze_image(
            image_bytes,
            prompt,
            model="gpt-5-nano"
        )
        
        # Return for confirmation
        embed = discord.Embed(
            title="🖼️ Image Analyzed",
            description=f"Detected: {analysis['field']}",
            color=0x0099ff
        )
        
        return {
            'needs_confirmation': True,
            'embed': embed,
            'data': analysis
        }
    
    def get_scheduled_tasks(self) -> List[Dict]:
        return [
            {
                'time': '09:00',
                'function': self._morning_task
            }
        ]
    
    async def _morning_task(self):
        """Send morning notification"""
        # Query data and send Discord notification
        pass
    
    async def get_daily_summary(self, date_obj: date) -> Dict:
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM your_table WHERE date = ?', (date_obj,))
        count = cursor.fetchone()[0]
        
        return {
            'count': count,
            'summary': f"{count} items tracked"
        }
```

### 2. Register Module

Edit `modules/registry.py`:

```python
# Add import
from .your_module import YourModule

class ModuleRegistry:
    def load_modules(self):
        available_modules = {
            'nutrition': NutritionModule,
            'workout': WorkoutModule,
            'your_module': YourModule,  # ← Add this
        }
        # ...
```

### 3. Add Configuration

Edit `config.yaml`:

```yaml
modules:
  your_module:
    enabled: true
    custom_setting: value
    another_setting: 123
```

### 4. Document Module

Add to README.md:

```markdown
### X. Your Module

**Tracks:** Brief description

**Keywords:**
- `trigger word` - What it does
- `another keyword` - What it does

**Features:**
- Feature 1
- Feature 2

**Example Usage:**
```
You: "trigger word. Log that."
Bot: ✅ Logged! [summary]
```
```

### 5. Test Locally

```bash
# Run locally
python main.py

# Test in Discord
"your trigger word. log that"

# Check database
sqlite3 nutrition_tracker.db "SELECT * FROM your_table;"
```

### 6. Deploy

```bash
git add modules/your_module.py
git add modules/registry.py
git add config.yaml
git add README.md
git commit -m "Add [module name] module"
git push

# Railway auto-deploys
# Or restart service: systemctl restart personal-automation
```

## Module Examples

### Example 1: Simple Counter

Track how many times something happens:

```python
class CounterModule(BaseModule):
    def get_name(self):
        return "counter"
    
    def get_keywords(self):
        return ['count this', 'tally']
    
    def setup_database(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS counter_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL,
                event TEXT NOT NULL,
                count INTEGER DEFAULT 1
            )
        ''')
        self.conn.commit()
    
    async def handle_log(self, content, lifelog_id, analysis):
        # Extract what to count
        prompt = f"Extract what to count from: {content}\nRespond with JSON: {{\"event\": \"description\"}}"
        analysis = self.openai_client.analyze_text(content, self.get_name(), prompt_template=prompt)
        
        # Store
        cursor = self.conn.cursor()
        cursor.execute('INSERT INTO counter_logs (date, event) VALUES (?, ?)',
                      (date.today(), analysis['event']))
        self.conn.commit()
        
        # Get total
        cursor.execute('SELECT COUNT(*) FROM counter_logs WHERE event = ? AND date = ?',
                      (analysis['event'], date.today()))
        count = cursor.fetchone()[0]
        
        embed = discord.Embed(
            title="✅ Counted!",
            description=f"{analysis['event']}: {count} times today",
            color=0x00FF00
        )
        
        return {'embed': embed}
```

### Example 2: Meeting Notes

Extract action items from meetings:

```python
class MeetingModule(BaseModule):
    def get_name(self):
        return "meetings"
    
    def get_keywords(self):
        return ['meeting summary', 'action items', 'meeting notes']
    
    async def handle_log(self, content, lifelog_id, analysis):
        # Get recent transcript (meeting likely just ended)
        transcript = self.limitless_client.get_todays_transcript()
        
        prompt = """Extract meeting information:

TRANSCRIPT:
{transcript}

Respond with JSON:
{
  "title": "meeting title",
  "participants": ["name1", "name2"],
  "action_items": [
    {"task": "description", "owner": "name", "due": "date"}
  ],
  "decisions": ["decision 1", "decision 2"],
  "summary": "brief summary"
}"""
        
        analysis = self.openai_client.analyze_text(
            transcript=transcript,
            module_name=self.get_name(),
            prompt_template=prompt
        )
        
        # Store in database
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO meetings (date, title, participants, action_items, summary)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            date.today(),
            analysis['title'],
            json.dumps(analysis['participants']),
            json.dumps(analysis['action_items']),
            analysis['summary']
        ))
        self.conn.commit()
        
        # Create rich embed
        embed = discord.Embed(
            title="📝 Meeting Logged",
            description=analysis['title'],
            color=0x0099ff
        )
        
        embed.add_field(
            name="Participants",
            value=", ".join(analysis['participants']),
            inline=False
        )
        
        embed.add_field(
            name="Action Items",
            value="\n".join([
                f"• {item['task']} (@{item['owner']})"
                for item in analysis['action_items']
            ]),
            inline=False
        )
        
        return {'embed': embed}
```

## Best Practices

### Database Design

```python
# ✅ Good: Separate tables for different entities
CREATE TABLE expenses (...)
CREATE TABLE expense_budgets (...)

# ❌ Bad: Everything in one table
CREATE TABLE data (type TEXT, value TEXT, ...)
```

### OpenAI Prompts

```python
# ✅ Good: Structured with examples
prompt = """Extract food items.

EXAMPLES:
- "I had eggs" → {"item": "eggs", "calories": 140}
- "chicken breast" → {"item": "chicken breast", "calories": 280}

TRANSCRIPT:
{transcript}

Respond with JSON only."""

# ❌ Bad: Vague
prompt = "Tell me what foods are in this text"
```

### Error Handling

```python
# ✅ Good: Graceful degradation
try:
    analysis = self.openai_client.analyze_text(...)
    if 'error' in analysis:
        return {'embed': self._create_error_embed(analysis['error'])}
except Exception as e:
    print(f"❌ Error: {e}")
    return {'embed': self._create_error_embed(str(e))}

# ❌ Bad: Let it crash
analysis = self.openai_client.analyze_text(...)
# No error handling
```

### Discord Embeds

```python
# ✅ Good: Rich, informative
embed = discord.Embed(
    title="✅ Clear Title",
    description="What happened",
    color=0x00FF00
)
embed.add_field(name="Data", value="123", inline=True)
embed.set_footer(text="Context or tips")

# ❌ Bad: Plain text
return "Logged successfully"
```

## Testing

### Unit Test Template

Create `tests/test_your_module.py`:

```python
import unittest
from modules.your_module import YourModule
from core import init_database, OpenAIClient, LimitlessClient

class TestYourModule(unittest.TestCase):
    def setUp(self):
        self.conn = init_database(':memory:')  # In-memory DB
        self.module = YourModule(self.conn, None, None, {})
    
    def test_database_setup(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        self.assertIn('your_table', tables)
    
    def test_keyword_matching(self):
        self.assertTrue(self.module.matches_keyword("trigger word"))
        self.assertFalse(self.module.matches_keyword("random text"))
```

Run tests:
```bash
python -m pytest tests/
```

## Common Patterns

### Pattern 1: Daily Aggregation

```python
def _get_daily_total(self, date_obj):
    cursor = self.conn.cursor()
    cursor.execute('''
        SELECT SUM(amount) FROM your_table WHERE date = ?
    ''', (date_obj,))
    return cursor.fetchone()[0] or 0
```

### Pattern 2: Time-Range Queries

```python
def _get_range(self, start_date, end_date):
    cursor = self.conn.cursor()
    cursor.execute('''
        SELECT * FROM your_table 
        WHERE date BETWEEN ? AND ?
        ORDER BY date
    ''', (start_date, end_date))
    return cursor.fetchall()
```

### Pattern 3: Running Averages

```python
def _get_7day_average(self):
    cursor = self.conn.cursor()
    cursor.execute('''
        SELECT AVG(value) FROM your_table
        WHERE date >= date('now', '-7 days')
    ''')
    return cursor.fetchone()[0] or 0
```

## Debugging

### Enable Verbose Logging

```python
# In your module
import logging
logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)

async def handle_log(self, ...):
    logger.debug(f"Processing: {message_content}")
    logger.debug(f"Analysis result: {analysis}")
```

### Test OpenAI Prompts

```python
# Test prompt separately
from core import OpenAIClient

client = OpenAIClient(os.getenv('OPENAI_API_KEY'))

result = client.analyze_text(
    transcript="I ate pizza",
    module_name="test",
    prompt_template="Extract food: {transcript}"
)

print(result)
```

## Checklist Before Deploying

- [ ] All abstract methods implemented
- [ ] Database schema uses IF NOT EXISTS
- [ ] Error handling for all OpenAI calls
- [ ] Discord embeds are informative
- [ ] Configuration added to config.yaml
- [ ] Module registered in registry.py
- [ ] Tested locally with real data
- [ ] README.md updated with examples
- [ ] Git committed with clear message

## Need Help?

Common issues:
1. **"Module not loading"** - Check syntax, verify enabled in config
2. **"Database locked"** - Using transactions correctly?
3. **"OpenAI timeout"** - Prompt too long? Network issue?
4. **"Discord embed not showing"** - Returning correct dict format?

## Example: Complete Expense Module

See `examples/expense_module.py` for a full working example with:
- Receipt OCR
- Budget tracking
- Monthly summaries
- Category breakdowns
- Alert system
