"""
Nutrition Module - Food, macro, and hydration tracking.

Features:
- Food logging with custom recipe database
- Macro tracking with dynamic targets
- Hydration logging
- Sleep tracking
- Health markers (weight, bowel movements, supplements)
- Wellness scores (mood, energy, stress)
- Daily summaries
- Image analysis for restaurant meals
"""

from modules.base import BaseModule
from datetime import date, datetime, timedelta
from typing import Dict, List
import json
# discord imported locally in methods to avoid audioop issues on Python 3.13


class NutritionModule(BaseModule):
    """Comprehensive nutrition and health tracking"""
    
    def get_name(self) -> str:
        return "nutrition"
    
    def get_keywords(self) -> List[str]:
        return [
            'log that', 'log this', 'track this', 'track that',
            'check macros', 'macro check', 'nutrition summary',
            'what should i eat', 'meal ideas', 'dinner ideas',
            'drank', 'water', 'hydration',
            'slept', 'sleep', 'woke up',
            'weighed', 'weight',
            'took supplements', 'took electrolytes',
            'feeling', 'mood', 'energy', 'stress',
            'bowel movement'
        ]
    
    def get_question_patterns(self) -> List[str]:
            """Regex patterns for detecting nutrition-related questions."""
            return [
                r'how much (protein|calories|carbs|fat|fiber)',
                r'what (should|can|would|do) (i|you) (eat|have|suggest|recommend)',
                r'(eat|have) for (breakfast|lunch|dinner)',
                r'what.*(nutrition|macro|food).*today',
                r'(today|current).*nutrition',
                r'did i (hit|reach|meet)',
                r'(macro|nutrition|food) (summary|totals|check)',
                r'how (much|many).*water',
                r'did i.*sleep',
                r'suggest.*lunch',
                r'recommend.*dinner'
            ]
    
    def setup_database(self):
        """Create all nutrition-related tables"""
        cursor = self.conn.cursor()
        
        # Food logs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS food_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL,
                timestamp DATETIME NOT NULL,
                item TEXT NOT NULL,
                calories REAL,
                protein_g REAL,
                carbs_g REAL,
                fat_g REAL,
                fiber_g REAL,
                is_custom_food BOOLEAN DEFAULT 0,
                custom_food_name TEXT,
                lifelog_id TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Custom foods database
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS custom_foods (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                aliases TEXT,
                calories REAL NOT NULL,
                protein_g REAL NOT NULL,
                carbs_g REAL NOT NULL,
                fat_g REAL NOT NULL,
                fiber_g REAL DEFAULT 0,
                notes TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Hydration logs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS hydration_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL,
                timestamp DATETIME NOT NULL,
                amount_oz REAL NOT NULL,
                lifelog_id TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Sleep logs
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sleep_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE UNIQUE NOT NULL,
                hours REAL NOT NULL,
                sleep_score INTEGER,
                quality_notes TEXT,
                lifelog_id TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Daily health markers
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_health (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE UNIQUE NOT NULL,
                weight_lbs REAL,
                bowel_movements INTEGER DEFAULT 0,
                electrolytes_taken BOOLEAN DEFAULT 0,
                lifelog_id TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Wellness scores
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS wellness_scores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL,
                timestamp DATETIME NOT NULL,
                mood TEXT,
                stress_level INTEGER,
                hunger_score INTEGER,
                energy_score INTEGER,
                soreness_score INTEGER,
                notes TEXT,
                lifelog_id TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        self.conn.commit()
        
        # Load custom foods from config
        self._load_custom_foods()
    
    def _load_custom_foods(self):
        """Load custom foods from configuration"""
        custom_foods = self.config.get('custom_foods', [])
        cursor = self.conn.cursor()
        
        for food in custom_foods:
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO custom_foods 
                    (name, aliases, calories, protein_g, carbs_g, fat_g, fiber_g, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    food['name'],
                    json.dumps(food.get('aliases', [])),
                    food['calories'],
                    food['protein_g'],
                    food['carbs_g'],
                    food['fat_g'],
                    food.get('fiber_g', 0),
                    food.get('notes', '')
                ))
            except Exception as e:
                print(f"⚠️  Failed to load custom food {food.get('name')}: {e}")
        
        self.conn.commit()
    
    async def handle_log(self, message_content: str, lifelog_id: str,
                        analysis: Dict) -> Dict:
        """Process food/health logging"""

        # Use targeted search instead of full transcript (96% cost reduction)
        # Search for recent food/health related entries from today
        search_results = self.limitless_client.search_lifelogs(
            query="food eat meal drink water sleep weight supplements health",
            date_filter=date.today().isoformat(),
            limit=5,  # Only get most relevant entries
            include_contents=False,  # Don't need detailed segments for this use case
            timezone="America/Los_Angeles"
        )

        # Build context from search results
        context_text = "\n\n".join([
            f"[{entry.get('startTime', 'N/A')}] {entry.get('markdown', '')[:500]}"
            for entry in search_results
        ])

        # Get custom foods for context
        custom_foods_context = self._get_custom_foods_context()

        # Analyze with OpenAI
        prompt = self._build_analysis_prompt(custom_foods_context)

        analysis = self.openai_client.analyze_text(
            transcript=f"{context_text}\n\nMOST RECENT: {message_content}",
            module_name=self.get_name(),
            prompt_template=prompt
        )
        
        if not analysis:
            return {"embed": self._create_error_embed("No response from OpenAI")}

        if 'error' in analysis:
            return {'embed': self._create_error_embed(analysis['error'])}
        
        # Store all detected data
        self._store_foods(analysis.get('foods_consumed', []), lifelog_id)
        self._store_hydration(analysis.get('hydration', {}), lifelog_id)
        self._store_sleep(analysis.get('sleep', {}), lifelog_id)
        self._store_health_markers(analysis.get('health_markers', {}), lifelog_id)
        self._store_wellness(analysis.get('wellness', {}), lifelog_id)
        
        # Get updated summary
        summary = self._get_daily_summary_internal(date.today())
        
        # Create confirmation embed
        embed = self._create_log_confirmation_embed(summary)
        
        return {'embed': embed}
    
    async def handle_query(self, query: str, context: Dict) -> str:
        """Answer nutrition questions"""

        # Diagnostic print – confirm that this function is being called
        print(f"🧩 Nutrition.handle_query() triggered with query: {query!r}")

        # Use targeted search instead of full transcript (96% cost reduction)
        # Search using the actual query for semantic matching
        search_results = self.limitless_client.search_lifelogs(
            query=f"{query} food nutrition meal",  # Enhance with nutrition keywords
            date_filter=date.today().isoformat(),
            limit=5,  # Only most relevant entries
            include_contents=False,
            timezone="America/Los_Angeles"
        )

        # Build context from search results
        relevant_context = "\n\n".join([
            f"[{entry.get('startTime', 'N/A')}] {entry.get('markdown', '')[:500]}"
            for entry in search_results
        ])

        # Get relevant data
        today_summary = self._get_daily_summary_internal(date.today())

        context_data = {
            'today_summary': today_summary,
            'relevant_entries': relevant_context  # Targeted entries instead of full transcript
        }

        # Make the OpenAI call
        try:
            answer = self.openai_client.answer_query(
                query=query,
                context=context_data,
                system_prompt=(
                    "You are a nutrition and wellness assistant with access to the "
                    "user's food logs, health data, and daily activities."
                )
            )
            # Diagnostic print – confirm what was returned
            print(f"🧩 Nutrition.handle_query() returning: {answer!r}")
            return answer

        except Exception as e:
            print(f"❌ Nutrition.handle_query() error: {e}")
            return f"Error while processing your nutrition query: {e}"

    async def handle_image(self, image_bytes: bytes, context: str) -> Dict:
        """Analyze food plate images"""
        
        prompt = """Analyze this food image and estimate nutritional content.

Instructions:
1. Identify all visible food items
2. Estimate portion sizes (use common references like "palm-sized", "cup", "handful")
3. Provide macro estimates for EACH item
4. Sum totals

Be conservative with estimates - better to slightly underestimate calories/fat.

Respond with ONLY valid JSON:
{
  "meal_description": "Brief description of the meal",
  "items": [
    {
      "name": "grilled chicken breast",
      "portion": "palm-sized (~6 oz)",
      "calories": 280,
      "protein_g": 52,
      "carbs_g": 0,
      "fat_g": 6,
      "fiber_g": 0
    }
  ],
  "totals": {
    "calories": 0,
    "protein_g": 0,
    "carbs_g": 0,
    "fat_g": 0,
    "fiber_g": 0
  },
  "confidence": "high/medium/low",
  "notes": "Any relevant observations"
}"""
        
        analysis = self.openai_client.analyze_image(image_bytes, prompt)
        
        if 'error' in analysis:
            return {
                'needs_confirmation': False,
                'embed': self._create_error_embed(analysis['error'])
            }
        
        # Create confirmation embed
        embed = self._create_food_image_embed(analysis)
        
        return {
            'needs_confirmation': True,
            'embed': embed,
            'data': {'foods_consumed': analysis['items']}
        }
    
    def get_scheduled_tasks(self) -> List[Dict]:
        """Return scheduled nutrition tasks"""
        tasks = []
        
        # Morning supplements
        morning_time = self.config.get('supplements', {}).get('morning', {}).get('time', '07:00')
        tasks.append({
            'time': morning_time,
            'function': self._send_morning_supplements
        })
        
        # Evening supplements
        evening_time = self.config.get('supplements', {}).get('evening', {}).get('time', '21:00')
        tasks.append({
            'time': evening_time,
            'function': self._send_evening_supplements
        })
        
        # Daily summary
        summary_time = self.config.get('daily_summary_time', '20:00')
        tasks.append({
            'time': summary_time,
            'function': self._send_daily_summary
        })
        
        return tasks
    
    async def get_daily_summary(self, date_obj: date) -> Dict:
        """Get daily summary data"""
        return self._get_daily_summary_internal(date_obj)
    
    # Helper methods
    
    def _get_custom_foods_context(self) -> str:
        """Get custom foods as context for AI"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT name, aliases, calories, protein_g, carbs_g, fat_g, fiber_g FROM custom_foods')
        foods = cursor.fetchall()
        
        context = "CUSTOM FOODS DATABASE (check these first):\n"
        for name, aliases_json, cal, protein, carbs, fat, fiber in foods:
            aliases = json.loads(aliases_json)
            context += f"- {name}: {aliases} → {cal} cal, {protein}g protein, {carbs}g carbs, {fat}g fat, {fiber}g fiber\n"
        
        return context
    
    def _build_analysis_prompt(self, custom_context: str) -> str:
        """Build comprehensive analysis prompt"""
        return f"""Extract ALL relevant health and nutrition data from this transcript.

        {custom_context}

        TRANSCRIPT:
        {{transcript}}

        Respond with ONLY valid JSON:
        {{{{
        "foods_consumed": [
            {{{{
            "item": "food name",
            "time": "HH:MM",
            "calories": 0,
            "protein_g": 0,
            "carbs_g": 0,
            "fat_g": 0,
            "fiber_g": 0,
            "is_custom_food": true/false,
            "custom_food_name": "smoothie_small" or null
            }}}}
        ],
        "hydration": {{{{"detected": true/false, "entries": [{{{{"amount_oz": 16}}}}]}}}},
        "sleep": {{{{"detected": true/false, "hours": 7.5, "sleep_score": 85, "quality": "good/poor/restless"}}}},
        "health_markers": {{{{"weight_lbs": null, "bowel_movements": 0, "electrolytes_taken": true/false}}}},
        "wellness": {{{{"mood": "good", "stress_level": 0-5, "energy_score": 0-10}}}}
        }}}}"""
    
    def _store_foods(self, foods: List[Dict], lifelog_id: str):
        """Store food logs"""
        if not foods:
            return
        
        cursor = self.conn.cursor()
        today = date.today()
        now = datetime.now()
        
        for food in foods:
            cursor.execute('''
                INSERT INTO food_logs 
                (date, timestamp, item, calories, protein_g, carbs_g, fat_g, fiber_g,
                 is_custom_food, custom_food_name, lifelog_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                today, now, food['item'],
                food.get('calories', 0),
                food.get('protein_g', 0),
                food.get('carbs_g', 0),
                food.get('fat_g', 0),
                food.get('fiber_g', 0),
                food.get('is_custom_food', False),
                food.get('custom_food_name'),
                lifelog_id
            ))
        
        self.conn.commit()
    
    def _store_hydration(self, hydration: Dict, lifelog_id: str):
        """Store hydration logs"""
        if not hydration.get('detected'):
            return
        
        cursor = self.conn.cursor()
        today = date.today()
        now = datetime.now()
        
        for entry in hydration.get('entries', []):
            cursor.execute('''
                INSERT INTO hydration_logs (date, timestamp, amount_oz, lifelog_id)
                VALUES (?, ?, ?, ?)
            ''', (today, now, entry['amount_oz'], lifelog_id))
        
        self.conn.commit()
    
    def _store_sleep(self, sleep: Dict, lifelog_id: str):
        """Store sleep logs"""
        if not sleep.get('detected'):
            return
        
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO sleep_logs 
            (date, hours, sleep_score, quality_notes, lifelog_id)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            date.today(),
            sleep['hours'],
            sleep.get('sleep_score'),
            sleep.get('quality'),
            lifelog_id
        ))
        
        self.conn.commit()
    
    def _store_health_markers(self, health: Dict, lifelog_id: str):
        """Store health markers"""
        if not any(health.values()):
            return
        
        cursor = self.conn.cursor()
        today = date.today()
        
        cursor.execute('''
            INSERT INTO daily_health (date, weight_lbs, bowel_movements, electrolytes_taken, lifelog_id)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                weight_lbs = COALESCE(excluded.weight_lbs, weight_lbs),
                bowel_movements = bowel_movements + excluded.bowel_movements,
                electrolytes_taken = excluded.electrolytes_taken OR electrolytes_taken,
                lifelog_id = excluded.lifelog_id
        ''', (
            today,
            health.get('weight_lbs'),
            health.get('bowel_movements', 0),
            health.get('electrolytes_taken', False),
            lifelog_id
        ))
        
        self.conn.commit()
    
    def _store_wellness(self, wellness: Dict, lifelog_id: str):
        """Store wellness scores"""
        if not any(v is not None for v in wellness.values()):
            return
        
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO wellness_scores 
            (date, timestamp, mood, stress_level, hunger_score, energy_score, soreness_score, lifelog_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            date.today(), datetime.now(),
            wellness.get('mood'),
            wellness.get('stress_level'),
            wellness.get('hunger_score'),
            wellness.get('energy_score'),
            wellness.get('soreness_score'),
            lifelog_id
        ))
        
        self.conn.commit()
    
    def _get_daily_summary_internal(self, date_obj: date) -> Dict:
        """Calculate daily totals and progress"""
        cursor = self.conn.cursor()
        
        # Food totals
        cursor.execute('''
            SELECT 
                COALESCE(SUM(calories), 0),
                COALESCE(SUM(protein_g), 0),
                COALESCE(SUM(carbs_g), 0),
                COALESCE(SUM(fat_g), 0),
                COALESCE(SUM(fiber_g), 0)
            FROM food_logs WHERE date = ?
        ''', (date_obj,))
        
        totals = cursor.fetchone()
        
        # Hydration
        cursor.execute('SELECT COALESCE(SUM(amount_oz), 0) FROM hydration_logs WHERE date = ?', (date_obj,))
        water = cursor.fetchone()[0]
        
        # Get targets (need to calculate based on training day)
        targets = self._calculate_targets(date_obj)
        
        # Calculate remaining
        remaining = {
            'calories': targets['calories'] - totals[0],
            'protein_g': targets['protein_g'] - totals[1],
            'carbs_g': targets['carbs_max_g'] - totals[2],
            'fat_g': targets['fat_g'] - totals[3],
            'fiber_g': targets['fiber_g'] - totals[4],
            'hydration_oz': targets['hydration_oz'] - water
        }
        
        return {
            'totals': {
                'calories': totals[0],
                'protein_g': totals[1],
                'carbs_g': totals[2],
                'fat_g': totals[3],
                'fiber_g': totals[4],
                'hydration_oz': water
            },
            'targets': targets,
            'remaining': remaining,
            'summary': f"{totals[0]:.0f} cal, {totals[1]:.0f}g protein, {totals[2]:.0f}g carbs"
        }
    
    def _calculate_targets(self, date_obj: date) -> Dict:
        """Calculate daily macro targets based on training"""
        # Get exercise data from workout module
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT COALESCE(SUM(calories_burned), 0), COALESCE(SUM(duration_minutes), 0)
            FROM exercise_logs WHERE date = ?
        ''', (date_obj,))
        
        exercise_data = cursor.fetchone()
        exercise_calories = exercise_data[0] or 0
        exercise_minutes = exercise_data[1] or 0
        
        # Get base targets from config
        daily_targets = self.config.get('daily_targets', {})
        rest_baseline = daily_targets.get('rest_day_baseline', 2150)
        deficit = daily_targets.get('deficit', 500)
        
        # Calculate calories
        if exercise_calories == 0:
            calories = rest_baseline
            carbs_config = daily_targets.get('carbs', {}).get('rest', {})
        else:
            calories = rest_baseline + exercise_calories - deficit
            
            if exercise_calories >= 600:
                carbs_config = daily_targets.get('carbs', {}).get('high', {})
            elif exercise_calories >= 200:
                carbs_config = daily_targets.get('carbs', {}).get('moderate', {})
            else:
                carbs_config = daily_targets.get('carbs', {}).get('rest', {})
        
        return {
            'calories': calories,
            'protein_g': daily_targets.get('protein_g', 150),
            'carbs_min_g': carbs_config.get('min', 150),
            'carbs_max_g': carbs_config.get('max', 180),
            'fat_g': daily_targets.get('fat_g', 60),
            'fiber_g': daily_targets.get('fiber_g', 25),
            'hydration_oz': daily_targets.get('hydration_oz', 95)
        }
    
    def _create_log_confirmation_embed(self, summary: Dict):
        """Create Discord embed for log confirmation"""
        import discord  # Local import to avoid audioop issues on Python 3.13
        
        import discord  # Local import to avoid audioop issues on Python 3.13
        
        totals = summary['totals']
        targets = summary['targets']
        remaining = summary['remaining']
        
        cal_pct = (totals['calories'] / targets['calories']) * 100
        
        # Color based on progress
        if cal_pct < 80:
            color = 0x00FF00  # Green
        elif cal_pct < 100:
            color = 0xFFFF00  # Yellow
        else:
            color = 0xFF0000  # Red
        
        embed = discord.Embed(
            title="✅ Logged!",
            description=f"**Daily Progress** ({cal_pct:.0f}% of calorie target)",
            color=color
        )
        
        embed.add_field(
            name="📊 Current Totals",
            value=(
                f"**Calories:** {totals['calories']:.0f} / {targets['calories']}\n"
                f"**Protein:** {totals['protein_g']:.0f}g / {targets['protein_g']}g\n"
                f"**Carbs:** {totals['carbs_g']:.0f}g / {targets['carbs_min_g']}-{targets['carbs_max_g']}g\n"
                f"**Fat:** {totals['fat_g']:.0f}g / {targets['fat_g']}g\n"
                f"**Fiber:** {totals['fiber_g']:.0f}g / {targets['fiber_g']}g\n"
                f"**Water:** {totals['hydration_oz']:.0f}oz / {targets['hydration_oz']}oz"
            ),
            inline=True
        )
        
        embed.add_field(
            name="🎯 Remaining",
            value=(
                f"**Calories:** {remaining['calories']:.0f}\n"
                f"**Protein:** {remaining['protein_g']:.0f}g\n"
                f"**Carbs:** {remaining['carbs_g']:.0f}g\n"
                f"**Fat:** {remaining['fat_g']:.0f}g\n"
                f"**Fiber:** {remaining['fiber_g']:.0f}g\n"
                f"**Water:** {remaining['hydration_oz']:.0f}oz"
            ),
            inline=True
        )
        
        embed.set_footer(text=f"Last updated: {datetime.now().strftime('%I:%M %p')}")
        
        return embed
    
    def _create_food_image_embed(self, analysis: Dict):
        """Create embed for food image analysis"""
        import discord  # Local import to avoid audioop issues on Python 3.13
        
        import discord  # Local import to avoid audioop issues on Python 3.13
        
        totals = analysis['totals']
        
        color = 0x00FF00 if analysis['confidence'] == 'high' else 0xFFFF00
        
        embed = discord.Embed(
            title="🍽️ Food Analysis",
            description=analysis['meal_description'],
            color=color
        )
        
        items_text = "\n".join([
            f"• **{item['name']}** ({item['portion']})\n"
            f"  └─ {item['calories']} cal | {item['protein_g']}p | {item['carbs_g']}c | {item['fat_g']}f"
            for item in analysis['items']
        ])
        
        embed.add_field(name="📋 Detected Items", value=items_text, inline=False)
        
        embed.add_field(
            name="🔢 Estimated Totals",
            value=(
                f"**Calories:** {totals['calories']}\n"
                f"**Protein:** {totals['protein_g']}g\n"
                f"**Carbs:** {totals['carbs_g']}g\n"
                f"**Fat:** {totals['fat_g']}g"
            ),
            inline=True
        )
        
        if analysis.get('notes'):
            embed.add_field(name="ℹ️ Notes", value=analysis['notes'], inline=False)
        
        embed.set_footer(text=f"Confidence: {analysis['confidence'].upper()} | React ✅ to log or ❌ to cancel")
        
        return embed
    
    def _create_error_embed(self, error_msg: str):
        """Create error embed"""
        import discord  # Local import to avoid audioop issues on Python 3.13
        
        return discord.Embed(
            title="❌ Error",
            description=f"Failed to process: {error_msg}",
            color=0xFF0000
        )
    
    async def _send_morning_supplements(self):
        """Send morning supplement reminder"""
        # Check if already sent today
        # (Implementation would check reminders_sent table)
        pass
    
    async def _send_evening_supplements(self):
        """Send evening supplement reminder"""
        pass
    
    async def _send_daily_summary(self):
        """Send daily nutrition summary"""
        pass