"""
Nutrition Module - Food and macro tracking.

Features:
- Food logging with custom recipe database
- Macro tracking with dynamic targets
- Hydration/water logging (stored in hydration_logs collection)
- Daily summaries
- Image analysis for restaurant meals
"""

from modules.base import BaseModule
from datetime import date, datetime, timedelta
from typing import Dict, List
import json
# discord imported locally in methods to avoid audioop issues on Python 3.13


class NutritionModule(BaseModule):
    """Food and macro tracking with hydration logging"""
    
    def get_name(self) -> str:
        return "nutrition"
    
    def get_keywords(self) -> List[str]:
        return [
            'log that', 'log this', 'track this', 'track that',
            'check macros', 'macro check', 'nutrition summary',
            'what should i eat', 'meal ideas', 'dinner ideas',
            'drank', 'water', 'hydration'
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
                            "created_at": self.get_now_in_timezone()
                        }
                    },
                    upsert=True
                )
            except Exception as e:
                print(f"⚠️  Failed to load custom food {food.get('name')}: {e}")
    
    async def handle_log(self, message_content: str, lifelog_id: str, 
                        analysis: Dict) -> Dict:
        """Process food/health logging"""
        
        self.logger.info(f"Processing nutrition log for lifelog_id: {lifelog_id}")
        
        # message_content now contains the context transcript (last 5 entries from polling batch)
        # No need to fetch full day's transcript
        
        # Get custom foods for context
        custom_foods_context = self._get_custom_foods_context()
        
        # Analyze with OpenAI
        self.logger.debug(f"Analyzing transcript with OpenAI (length: {len(message_content)} chars)")
        prompt = self._build_analysis_prompt(custom_foods_context)
        
        analysis = self.openai_client.analyze_text(
            transcript=message_content,
            module_name=self.get_name(),
            prompt_template=prompt
        )
        
        if not analysis:
            self.logger.error("No response from OpenAI")
            return {"embed": self._create_error_embed("No response from OpenAI")}

        if 'error' in analysis:
            self.logger.error(f"OpenAI analysis error: {analysis['error']}")
            return {'embed': self._create_error_embed(analysis['error'])}
        
        # Store all detected data
        foods = analysis.get('foods_consumed', [])
        hydration = analysis.get('hydration', {})
        
        self.logger.info(f"Detected: {len(foods)} foods, hydration={hydration.get('detected', False)}")
        
        self._store_foods(foods, lifelog_id)
        self._store_hydration(hydration, lifelog_id)
        
        # Get updated summary
        summary = self._get_daily_summary_internal(self.get_today_in_timezone())
        
        # Create confirmation embed
        embed = self._create_log_confirmation_embed(summary)
        
        # Build what was logged for notifications
        logged_items = []
        if foods:
            food_names = [f.get('item', 'Unknown') for f in foods]
            logged_items.append(f"Food: {', '.join(food_names)}")
        if hydration.get('detected') and hydration.get('entries'):
            total_oz = sum(e.get('amount_oz', 0) for e in hydration.get('entries', []))
            logged_items.append(f"Hydration: {total_oz}oz")
        
        self.logger.info(f"✓ Successfully processed nutrition log for lifelog_id: {lifelog_id}")
        return {
            'embed': embed,
            'logged_items': logged_items,
            'logged_data': {
                'foods': foods,
                'hydration': hydration
            }
        }
    
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
        return f"""Extract food and hydration data from this transcript.

        {custom_context}

        IMPORTANT INSTRUCTIONS:
        - If a food is in the CUSTOM FOODS DATABASE above, use those exact values and set is_custom_food=true
        - If a food is NOT in the custom foods database, you MUST estimate nutrition values using standard nutrition knowledge
        - NEVER leave calories, protein, carbs, fat, or fiber as 0 unless the food truly has none
        - For common foods (banana, apple, chicken, etc.), use standard serving size estimates
        - Always provide realistic nutrition estimates for any food item
        - WATER/HYDRATION: If the user mentions drinking water, water bottles, hydration, or any liquid that is plain water (not juice, coffee, etc.), 
          set hydration.detected=true and include the amount in ounces. Do NOT include water as a food item.
        - Only include actual food items in foods_consumed. Water, plain water, hydration drinks (if just water), etc. should go in hydration, not foods_consumed.

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
        "hydration": {{{{"detected": true/false, "entries": [{{{{"amount_oz": 16}}}}]}}}}
        }}}}"""
    
    def _store_foods(self, foods: List[Dict], lifelog_id: str):
        """Store food logs"""
        if not foods:
            self.logger.debug("No foods to store")
            return
        
        self.logger.info(f"Storing {len(foods)} food item(s)")
        food_logs_collection = self.db["food_logs"]
        today = self.get_today_in_timezone()
        now = self.get_now_in_timezone()
        
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
            self.logger.debug(f"  - {food['item']}: {food.get('calories', 0)} cal, "
                            f"{food.get('protein_g', 0)}g protein")
        
        if documents:
            result = food_logs_collection.insert_many(documents)
            self.logger.info(f"✓ Stored {len(documents)} food log(s) in MongoDB")
            # Vectorize each inserted document
            for i, doc in enumerate(documents):
                doc["_id"] = result.inserted_ids[i]
                self._vectorize_record(doc, "food_logs")
    
    def _store_hydration(self, hydration: Dict, lifelog_id: str):
        """Store hydration logs"""
        if not hydration.get('detected'):
            self.logger.debug("No hydration detected")
            return
        
        entries = hydration.get('entries', [])
        total_oz = sum(entry.get('amount_oz', 0) for entry in entries)
        self.logger.info(f"Storing hydration: {len(entries)} entry/entries, {total_oz} oz total")
        
        hydration_logs_collection = self.db["hydration_logs"]
        today = self.get_today_in_timezone()
        now = self.get_now_in_timezone()
        
        documents = []
        for entry in entries:
            documents.append({
                "date": today.isoformat(),
                "timestamp": now.isoformat(),
                "amount_oz": entry['amount_oz'],
                "lifelog_id": lifelog_id,
                "created_at": now
            })
            self.logger.debug(f"  - {entry['amount_oz']} oz")
        
        if documents:
            result = hydration_logs_collection.insert_many(documents)
            self.logger.info(f"✓ Stored {len(documents)} hydration log(s) in MongoDB")
            # Vectorize each inserted document
            for i, doc in enumerate(documents):
                doc["_id"] = result.inserted_ids[i]
                self._vectorize_record(doc, "hydration_logs")
    
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
        
        embed.set_footer(text=f"Last updated: {self.get_now_in_timezone().strftime('%I:%M %p')}")
        
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