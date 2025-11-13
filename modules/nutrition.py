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
        """Create all nutrition-related collections and indexes"""
        # Collections are created automatically on first insert
        # Create indexes for performance
        
        # Food logs collection
        food_logs = self.conn["food_logs"]
        food_logs.create_index("date")
        food_logs.create_index("lifelog_id")
        
        # Custom foods collection
        custom_foods = self.conn["custom_foods"]
        custom_foods.create_index("name", unique=True)
        
        # Hydration logs collection
        hydration_logs = self.conn["hydration_logs"]
        hydration_logs.create_index("date")
        hydration_logs.create_index("lifelog_id")
        
        # Sleep logs collection
        sleep_logs = self.conn["sleep_logs"]
        sleep_logs.create_index("date", unique=True)
        
        # Daily health collection
        daily_health = self.conn["daily_health"]
        daily_health.create_index("date", unique=True)
        
        # Wellness scores collection
        wellness_scores = self.conn["wellness_scores"]
        wellness_scores.create_index("date")
        wellness_scores.create_index("lifelog_id")
        
        # Load custom foods from config
        self._load_custom_foods()
    
    def _load_custom_foods(self):
        """Load custom foods from configuration"""
        custom_foods_config = self.config.get('custom_foods', [])
        custom_foods_collection = self.conn["custom_foods"]
        
        for food in custom_foods_config:
            try:
                custom_foods_collection.replace_one(
                    {"name": food['name']},
                    {
                        "name": food['name'],
                        "aliases": json.dumps(food.get('aliases', [])),
                        "calories": food['calories'],
                        "protein_g": food['protein_g'],
                        "carbs_g": food['carbs_g'],
                        "fat_g": food['fat_g'],
                        "fiber_g": food.get('fiber_g', 0),
                        "notes": food.get('notes', ''),
                        "created_at": datetime.now().isoformat()
                    },
                    upsert=True
                )
            except Exception as e:
                print(f"⚠️  Failed to load custom food {food.get('name')}: {e}")
    
    async def handle_log(self, message_content: str, lifelog_id: str, 
                        analysis: Dict) -> Dict:
        """Process food/health logging"""
        
        # Get today's transcript for context
        # ensure API uses correct boolean + timezone parameters
        transcript = self.limitless_client.get_todays_transcript(timezone="America/Los_Angeles")
        
        # Get custom foods for context
        custom_foods_context = self._get_custom_foods_context()
        
        # Analyze with OpenAI
        prompt = self._build_analysis_prompt(custom_foods_context)
        
        analysis = self.openai_client.analyze_text(
            transcript=f"{transcript}\n\nMOST RECENT: {message_content}",
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

        # Get relevant data
        today_summary = self._get_daily_summary_internal(date.today())
        transcript = self.limitless_client.get_todays_transcript()

        context_data = {
            'today_summary': today_summary,
            'recent_transcript': transcript[:2000]  # Limit size
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

        print(f"🧠 OpenAI answer: {answer}")
        return answer

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
        custom_foods_collection = self.conn["custom_foods"]
        foods = custom_foods_collection.find({}, {"name": 1, "aliases": 1, "calories": 1, "protein_g": 1, "carbs_g": 1, "fat_g": 1, "fiber_g": 1})
        
        context = "CUSTOM FOODS DATABASE (check these first):\n"
        for food in foods:
            name = food.get("name")
            aliases_json = food.get("aliases", "[]")
            cal = food.get("calories", 0)
            protein = food.get("protein_g", 0)
            carbs = food.get("carbs_g", 0)
            fat = food.get("fat_g", 0)
            fiber = food.get("fiber_g", 0)
            aliases = json.loads(aliases_json) if isinstance(aliases_json, str) else aliases_json
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
        
        food_logs_collection = self.conn["food_logs"]
        today = date.today()
        now = datetime.now()
        
        documents = []
        for food in foods:
            documents.append({
                "date": today.isoformat(),
                "timestamp": now.isoformat(),
                "item": food['item'],
                "calories": food.get('calories', 0),
                "protein_g": food.get('protein_g', 0),
                "carbs_g": food.get('carbs_g', 0),
                "fat_g": food.get('fat_g', 0),
                "fiber_g": food.get('fiber_g', 0),
                "is_custom_food": food.get('is_custom_food', False),
                "custom_food_name": food.get('custom_food_name'),
                "lifelog_id": lifelog_id,
                "created_at": now.isoformat()
            })
        
        if documents:
            food_logs_collection.insert_many(documents)
    
    def _store_hydration(self, hydration: Dict, lifelog_id: str):
        """Store hydration logs"""
        if not hydration.get('detected'):
            return
        
        hydration_logs_collection = self.conn["hydration_logs"]
        today = date.today()
        now = datetime.now()
        
        documents = []
        for entry in hydration.get('entries', []):
            documents.append({
                "date": today.isoformat(),
                "timestamp": now.isoformat(),
                "amount_oz": entry['amount_oz'],
                "lifelog_id": lifelog_id,
                "created_at": now.isoformat()
            })
        
        if documents:
            hydration_logs_collection.insert_many(documents)
    
    def _store_sleep(self, sleep: Dict, lifelog_id: str):
        """Store sleep logs"""
        if not sleep.get('detected'):
            return
        
        sleep_logs_collection = self.conn["sleep_logs"]
        today = date.today()
        now = datetime.now()
        
        sleep_logs_collection.replace_one(
            {"date": today.isoformat()},
            {
                "date": today.isoformat(),
                "hours": sleep['hours'],
                "sleep_score": sleep.get('sleep_score'),
                "quality_notes": sleep.get('quality'),
                "lifelog_id": lifelog_id,
                "created_at": now.isoformat()
            },
            upsert=True
        )
    
    def _store_health_markers(self, health: Dict, lifelog_id: str):
        """Store health markers"""
        if not any(health.values()):
            return
        
        daily_health_collection = self.conn["daily_health"]
        today = date.today()
        now = datetime.now()
        
        # Get existing document if it exists
        existing = daily_health_collection.find_one({"date": today.isoformat()})
        
        if existing:
            # Update existing document
            update_data = {}
            if health.get('weight_lbs') is not None:
                update_data["weight_lbs"] = health.get('weight_lbs')
            if health.get('bowel_movements', 0) > 0:
                update_data["bowel_movements"] = existing.get("bowel_movements", 0) + health.get('bowel_movements', 0)
            if health.get('electrolytes_taken'):
                update_data["electrolytes_taken"] = True
            update_data["lifelog_id"] = lifelog_id
            
            daily_health_collection.update_one(
                {"date": today.isoformat()},
                {"$set": update_data}
            )
        else:
            # Insert new document
            daily_health_collection.insert_one({
                "date": today.isoformat(),
                "weight_lbs": health.get('weight_lbs'),
                "bowel_movements": health.get('bowel_movements', 0),
                "electrolytes_taken": health.get('electrolytes_taken', False),
                "lifelog_id": lifelog_id,
                "created_at": now.isoformat()
            })
    
    def _store_wellness(self, wellness: Dict, lifelog_id: str):
        """Store wellness scores"""
        if not any(v is not None for v in wellness.values()):
            return
        
        wellness_scores_collection = self.conn["wellness_scores"]
        today = date.today()
        now = datetime.now()
        
        wellness_scores_collection.insert_one({
            "date": today.isoformat(),
            "timestamp": now.isoformat(),
            "mood": wellness.get('mood'),
            "stress_level": wellness.get('stress_level'),
            "hunger_score": wellness.get('hunger_score'),
            "energy_score": wellness.get('energy_score'),
            "soreness_score": wellness.get('soreness_score'),
            "notes": wellness.get('notes'),
            "lifelog_id": lifelog_id,
            "created_at": now.isoformat()
        })
    
    def _get_daily_summary_internal(self, date_obj: date) -> Dict:
        """Calculate daily totals and progress"""
        date_str = date_obj.isoformat()
        
        # Food totals using aggregation
        food_logs_collection = self.conn["food_logs"]
        food_pipeline = [
            {"$match": {"date": date_str}},
            {"$group": {
                "_id": None,
                "calories": {"$sum": "$calories"},
                "protein_g": {"$sum": "$protein_g"},
                "carbs_g": {"$sum": "$carbs_g"},
                "fat_g": {"$sum": "$fat_g"},
                "fiber_g": {"$sum": "$fiber_g"}
            }}
        ]
        food_result = list(food_logs_collection.aggregate(food_pipeline))
        if food_result:
            totals = [
                food_result[0].get("calories", 0) or 0,
                food_result[0].get("protein_g", 0) or 0,
                food_result[0].get("carbs_g", 0) or 0,
                food_result[0].get("fat_g", 0) or 0,
                food_result[0].get("fiber_g", 0) or 0
            ]
        else:
            totals = [0, 0, 0, 0, 0]
        
        # Hydration
        hydration_logs_collection = self.conn["hydration_logs"]
        hydration_pipeline = [
            {"$match": {"date": date_str}},
            {"$group": {
                "_id": None,
                "total_oz": {"$sum": "$amount_oz"}
            }}
        ]
        hydration_result = list(hydration_logs_collection.aggregate(hydration_pipeline))
        water = hydration_result[0].get("total_oz", 0) if hydration_result else 0
        
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
        date_str = date_obj.isoformat()
        exercise_logs_collection = self.conn["exercise_logs"]
        exercise_pipeline = [
            {"$match": {"date": date_str}},
            {"$group": {
                "_id": None,
                "calories_burned": {"$sum": "$calories_burned"},
                "duration_minutes": {"$sum": "$duration_minutes"}
            }}
        ]
        exercise_result = list(exercise_logs_collection.aggregate(exercise_pipeline))
        if exercise_result:
            exercise_calories = exercise_result[0].get("calories_burned", 0) or 0
            exercise_minutes = exercise_result[0].get("duration_minutes", 0) or 0
        else:
            exercise_calories = 0
            exercise_minutes = 0
        
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