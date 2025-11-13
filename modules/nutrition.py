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
        # Food logs collection
        food_logs = self.db["food_logs"]
        food_logs.create_index([("date", 1), ("timestamp", 1)])
        food_logs.create_index("lifelog_id")
        
        # Custom foods database
        custom_foods = self.db["custom_foods"]
        custom_foods.create_index("name", unique=True)
        
        # Hydration logs
        hydration_logs = self.db["hydration_logs"]
        hydration_logs.create_index([("date", 1), ("timestamp", 1)])
        hydration_logs.create_index("lifelog_id")
        
        # Sleep logs
        sleep_logs = self.db["sleep_logs"]
        sleep_logs.create_index("date", unique=True)
        sleep_logs.create_index("lifelog_id")
        
        # Daily health markers
        daily_health = self.db["daily_health"]
        daily_health.create_index("date", unique=True)
        daily_health.create_index("lifelog_id")
        
        # Wellness scores
        wellness_scores = self.db["wellness_scores"]
        wellness_scores.create_index([("date", 1), ("timestamp", 1)])
        wellness_scores.create_index("lifelog_id")
        
        # Load custom foods from config
        self._load_custom_foods()
    
    def _load_custom_foods(self):
        """Load custom foods from configuration"""
        custom_foods_collection = self.db["custom_foods"]
        custom_foods = self.config.get('custom_foods', [])
        
        for food in custom_foods:
            try:
                custom_foods_collection.update_one(
                    {"name": food['name']},
                    {
                        "$set": {
                            "name": food['name'],
                            "aliases": food.get('aliases', []),
                            "calories": food['calories'],
                            "protein_g": food['protein_g'],
                            "carbs_g": food['carbs_g'],
                            "fat_g": food['fat_g'],
                            "fiber_g": food.get('fiber_g', 0),
                            "notes": food.get('notes', ''),
                            "created_at": datetime.now()
                        }
                    },
                    upsert=True
                )
            except Exception as e:
                print(f"⚠️  Failed to load custom food {food.get('name')}: {e}")
    
    async def handle_log(self, message_content: str, lifelog_id: str, 
                        analysis: Dict) -> Dict:
        """Process food/health logging"""
        
        # message_content now contains the context transcript (last 5 entries from polling batch)
        # No need to fetch full day's transcript
        
        # Get custom foods for context
        custom_foods_context = self._get_custom_foods_context()
        
        # Analyze with OpenAI
        prompt = self._build_analysis_prompt(custom_foods_context)
        
        analysis = self.openai_client.analyze_text(
            transcript=message_content,
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

        # Get relevant data from MongoDB (no need for raw transcripts)
        today_summary = self._get_daily_summary_internal(date.today())

        context_data = {
            'today_summary': today_summary
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
        custom_foods_collection = self.db["custom_foods"]
        foods = custom_foods_collection.find({})
        
        context = "CUSTOM FOODS DATABASE (check these first):\n"
        for food in foods:
            name = food.get('name')
            aliases = food.get('aliases', [])
            cal = food.get('calories', 0)
            protein = food.get('protein_g', 0)
            carbs = food.get('carbs_g', 0)
            fat = food.get('fat_g', 0)
            fiber = food.get('fiber_g', 0)
            context += f"- {name}: {aliases} → {cal} cal, {protein}g protein, {carbs}g carbs, {fat}g fat, {fiber}g fiber\n"
        
        return context
    
    def _build_analysis_prompt(self, custom_context: str) -> str:
        """Build comprehensive analysis prompt"""
        return f"""Extract ALL relevant health and nutrition data from this transcript.

        {custom_context}

        IMPORTANT INSTRUCTIONS:
        - If a food is in the CUSTOM FOODS DATABASE above, use those exact values and set is_custom_food=true
        - If a food is NOT in the custom foods database, you MUST estimate nutrition values using standard nutrition knowledge
        - NEVER leave calories, protein, carbs, fat, or fiber as 0 unless the food truly has none
        - For common foods (banana, apple, chicken, etc.), use standard serving size estimates
        - Always provide realistic nutrition estimates for any food item

        TRANSCRIPT:
        {{transcript}}

        Respond with ONLY valid JSON:
        {{{{
        "foods_consumed": [
            {{{{
            "item": "food name",
            "time": "HH:MM",
            "calories": <estimate if not custom, use custom value if custom>,
            "protein_g": <estimate if not custom, use custom value if custom>,
            "carbs_g": <estimate if not custom, use custom value if custom>,
            "fat_g": <estimate if not custom, use custom value if custom>,
            "fiber_g": <estimate if not custom, use custom value if custom>,
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
        
        food_logs_collection = self.db["food_logs"]
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
                "created_at": now
            })
        
        if documents:
            food_logs_collection.insert_many(documents)
    
    def _store_hydration(self, hydration: Dict, lifelog_id: str):
        """Store hydration logs"""
        if not hydration.get('detected'):
            return
        
        hydration_logs_collection = self.db["hydration_logs"]
        today = date.today()
        now = datetime.now()
        
        documents = []
        for entry in hydration.get('entries', []):
            documents.append({
                "date": today.isoformat(),
                "timestamp": now.isoformat(),
                "amount_oz": entry['amount_oz'],
                "lifelog_id": lifelog_id,
                "created_at": now
            })
        
        if documents:
            hydration_logs_collection.insert_many(documents)
    
    def _store_sleep(self, sleep: Dict, lifelog_id: str):
        """Store sleep logs"""
        if not sleep.get('detected'):
            return
        
        sleep_logs_collection = self.db["sleep_logs"]
        today = date.today()
        
        sleep_logs_collection.update_one(
            {"date": today.isoformat()},
            {
                "$set": {
                    "date": today.isoformat(),
                    "hours": sleep['hours'],
                    "sleep_score": sleep.get('sleep_score'),
                    "quality_notes": sleep.get('quality'),
                    "lifelog_id": lifelog_id,
                    "created_at": datetime.now()
                }
            },
            upsert=True
        )
    
    def _store_health_markers(self, health: Dict, lifelog_id: str):
        """Store health markers"""
        if not any(health.values()):
            return
        
        daily_health_collection = self.db["daily_health"]
        today = date.today()
        
        # Get existing document if it exists
        existing = daily_health_collection.find_one({"date": today.isoformat()})
        
        update_data = {
            "date": today.isoformat(),
            "lifelog_id": lifelog_id,
            "created_at": datetime.now()
        }
        
        # Update weight if provided
        if health.get('weight_lbs') is not None:
            update_data["weight_lbs"] = health.get('weight_lbs')
        elif existing:
            update_data["weight_lbs"] = existing.get('weight_lbs')
        
        # Increment bowel movements
        if health.get('bowel_movements', 0) > 0:
            update_data["bowel_movements"] = (existing.get('bowel_movements', 0) if existing else 0) + health.get('bowel_movements', 0)
        elif existing:
            update_data["bowel_movements"] = existing.get('bowel_movements', 0)
        else:
            update_data["bowel_movements"] = 0
        
        # Update electrolytes
        if health.get('electrolytes_taken') is not None:
            update_data["electrolytes_taken"] = health.get('electrolytes_taken') or (existing.get('electrolytes_taken', False) if existing else False)
        elif existing:
            update_data["electrolytes_taken"] = existing.get('electrolytes_taken', False)
        else:
            update_data["electrolytes_taken"] = False
        
        daily_health_collection.update_one(
            {"date": today.isoformat()},
            {"$set": update_data},
            upsert=True
        )
    
    def _store_wellness(self, wellness: Dict, lifelog_id: str):
        """Store wellness scores"""
        if not any(v is not None for v in wellness.values()):
            return
        
        wellness_scores_collection = self.db["wellness_scores"]
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
            "lifelog_id": lifelog_id,
            "created_at": now
        })
    
    def _get_daily_summary_internal(self, date_obj: date) -> Dict:
        """Calculate daily totals and progress"""
        date_str = date_obj.isoformat()
        
        # Food totals
        food_logs_collection = self.db["food_logs"]
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
            totals = (
                food_result[0].get("calories", 0),
                food_result[0].get("protein_g", 0),
                food_result[0].get("carbs_g", 0),
                food_result[0].get("fat_g", 0),
                food_result[0].get("fiber_g", 0)
            )
        else:
            totals = (0, 0, 0, 0, 0)
        
        # Hydration
        hydration_logs_collection = self.db["hydration_logs"]
        hydration_pipeline = [
            {"$match": {"date": date_str}},
            {"$group": {"_id": None, "total_oz": {"$sum": "$amount_oz"}}}
        ]
        hydration_result = list(hydration_logs_collection.aggregate(hydration_pipeline))
        water = hydration_result[0].get("total_oz", 0) if hydration_result else 0
        
        # Sleep data
        sleep_logs_collection = self.db["sleep_logs"]
        sleep_data = sleep_logs_collection.find_one({"date": date_str})
        sleep_hours = sleep_data.get("hours") if sleep_data else None
        sleep_score = sleep_data.get("sleep_score") if sleep_data else None
        sleep_quality = sleep_data.get("quality_notes") if sleep_data else None
        
        # Health markers (bowel movements, weight)
        daily_health_collection = self.db["daily_health"]
        health_data = daily_health_collection.find_one({"date": date_str})
        bowel_movements = health_data.get("bowel_movements", 0) if health_data else 0
        weight_lbs = health_data.get("weight_lbs") if health_data else None
        
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
        
        # Build summary text
        summary_parts = [f"{totals[0]:.0f} cal, {totals[1]:.0f}g protein, {totals[2]:.0f}g carbs"]
        if sleep_hours is not None:
            summary_parts.append(f"{sleep_hours:.1f}h sleep")
        if bowel_movements > 0:
            summary_parts.append(f"{bowel_movements} BM")
        
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
            'sleep': {
                'hours': sleep_hours,
                'score': sleep_score,
                'quality': sleep_quality
            },
            'health': {
                'bowel_movements': bowel_movements,
                'weight_lbs': weight_lbs
            },
            'summary': ", ".join(summary_parts)
        }
    
    def _calculate_targets(self, date_obj: date) -> Dict:
        """Calculate daily macro targets based on training"""
        # Get exercise data from workout module
        date_str = date_obj.isoformat()
        exercise_logs_collection = self.db["exercise_logs"]
        exercise_pipeline = [
            {"$match": {"date": date_str}},
            {"$group": {
                "_id": None,
                "total_calories": {"$sum": "$calories_burned"},
                "total_minutes": {"$sum": "$duration_minutes"}
            }}
        ]
        exercise_result = list(exercise_logs_collection.aggregate(exercise_pipeline))
        if exercise_result:
            exercise_calories = exercise_result[0].get("total_calories", 0) or 0
            exercise_minutes = exercise_result[0].get("total_minutes", 0) or 0
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