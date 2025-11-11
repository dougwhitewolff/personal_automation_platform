"""
Workout Module - Exercise and training tracking.

Features:
- Exercise logging (duration, type, calories)
- Peloton screenshot OCR (strive score, output, zones)
- Automatic training intensity calculation
- Electrolyte reminders for long cardio
- Auto-update macro targets based on exercise
"""

from modules.base import BaseModule
from datetime import date, datetime
from typing import Dict, List
import json
# discord imported locally in methods to avoid audioop issues on Python 3.13


class WorkoutModule(BaseModule):
    """Exercise and training tracking"""
    
    def get_name(self) -> str:
        return "workout"
    
    def get_keywords(self) -> List[str]:
        return [
            "workout", "exercise", "trained", "worked out",
            "peloton", "ride", "run", "ran",
            "cycling", "biking", "strength",
            "log workout", "finished workout"
        ]
    
    def get_question_patterns(self) -> List[str]:
        return [
            r"how (much|many|long).*work",
            r"what.*exercise",
            r"did i.*workout",
            r"(workout|exercise) (summary|stats|totals)"
        ]
    
    def setup_database(self):
        """Create exercise tracking collections and indexes"""
        # Collections are created automatically on first insert
        # Create indexes for performance
        
        # Exercise logs collection
        exercise_logs = self.conn["exercise_logs"]
        exercise_logs.create_index("date")
        exercise_logs.create_index("lifelog_id")
        
        # Training days collection
        training_days = self.conn["training_days"]
        training_days.create_index("date", unique=True)
        training_days.create_index("primary_exercise_id")
    
    async def handle_log(self, message_content: str, lifelog_id: str, analysis: Dict) -> Dict:
        """Process workout logging"""
        
        # Get transcript from Limitless (for context)
        transcript = self.limitless_client.get_todays_transcript()
        
        # Escaped JSON braces to avoid KeyError during .format()
        prompt = """Extract exercise information from the transcript.

TRANSCRIPT:
{transcript}

RECENT MESSAGE:
""" + message_content + """

Respond with ONLY valid JSON:
{{
  "exercise": {{
    "detected": true/false,
    "type": "cycling/running/strength/yoga",
    "duration_minutes": 0,
    "calories_burned": 0,
    "notes": "any relevant details"
  }}
}}"""
        
        # Perform OpenAI text analysis
        analysis = self.openai_client.analyze_text(
            transcript=transcript,
            module_name=self.get_name(),
            prompt_template=prompt
        )
        
        # Handle invalid or missing detection
        if "error" in analysis or not analysis.get("exercise", {}).get("detected"):
            return {"embed": self._create_error_embed("No exercise detected")}
        
        # Store exercise data
        exercise = analysis["exercise"]
        exercise_id = self._store_exercise(exercise, lifelog_id)
        
        # Update training day intensity
        self._update_training_day(date.today(), exercise, exercise_id)
        
        # Determine electrolyte recommendation
        needs_electrolytes = (
            exercise.get("duration_minutes", 0)
            >= self.config.get("electrolyte_threshold_minutes", 45)
        )
        
        # Create confirmation embed
        embed = self._create_exercise_embed(exercise, needs_electrolytes)
        return {"embed": embed}
    
    async def handle_query(self, query: str, context: Dict) -> str:
        """Answer workout questions"""
        from datetime import timedelta
        
        exercise_logs_collection = self.conn["exercise_logs"]
        # Get exercises from last 7 days
        seven_days_ago = (date.today() - timedelta(days=7)).isoformat()
        
        exercises_cursor = exercise_logs_collection.find(
            {"date": {"$gte": seven_days_ago}},
            {"date": 1, "exercise_type": 1, "duration_minutes": 1, "calories_burned": 1}
        ).sort("date", -1)
        
        exercises = [
            {
                "date": ex.get("date"),
                "type": ex.get("exercise_type"),
                "duration": ex.get("duration_minutes"),
                "calories": ex.get("calories_burned")
            }
            for ex in exercises_cursor
        ]
        
        return self.openai_client.answer_query(
            query=query,
            context={"recent_exercises": exercises},
            system_prompt="You are a fitness tracking assistant with access to the user's workout history."
        )
    
    async def handle_image(self, image_bytes: bytes, context: str) -> Dict:
        """Extract Peloton stats from screenshot"""
        
        # Escaped JSON braces
        prompt = """Extract Peloton workout statistics from this image.

Look for:
- Duration (minutes)
- Strive Score
- Total Output
- Average Heart Rate (Avg HR)
- Training zones (Zone 1-5 minutes)
- Calories burned

Respond with ONLY valid JSON:
{{
  "duration_minutes": 45,
  "strive_score": 48,
  "output": 532,
  "avg_hr": 145,
  "calories": 450,
  "training_zones": {{
    "zone1": 5,
    "zone2": 12,
    "zone3": 18,
    "zone4": 8,
    "zone5": 2
  }},
  "ride_name": "30 min Pop Ride" or null,
  "instructor": "name" or null
}}

If any field is not visible, use null."""
        
        analysis = self.openai_client.analyze_image(image_bytes, prompt, model="gpt-5-nano")
        
        if "error" in analysis:
            return {
                "needs_confirmation": False,
                "embed": self._create_error_embed(analysis["error"])
            }
        
        # Build exercise record
        exercise_data = {
            "exercise": {
                "detected": True,
                "type": "cycling",
                "duration_minutes": analysis["duration_minutes"],
                "calories_burned": analysis.get("calories"),
                "peloton_data": {
                    "strive_score": analysis.get("strive_score"),
                    "output": analysis.get("output"),
                    "avg_hr": analysis.get("avg_hr"),
                    "training_zones": analysis.get("training_zones")
                },
                "notes": f"Peloton: {analysis.get('ride_name', 'Ride')}"
            }
        }
        
        # Store immediately (auto-confirmed)
        exercise_id = self._store_exercise(exercise_data["exercise"], "peloton_img")
        self._update_training_day(date.today(), exercise_data["exercise"], exercise_id)
        
        needs_electrolytes = (
            analysis["duration_minutes"]
            >= self.config.get("electrolyte_threshold_minutes", 45)
        )
        
        embed = self._create_peloton_embed(analysis, needs_electrolytes)
        return {"needs_confirmation": False, "embed": embed}
    
    def get_scheduled_tasks(self) -> List[Dict]:
        """Workout module does not schedule reminders directly."""
        return []
    
    async def get_daily_summary(self, date_obj: date) -> Dict:
        """Get workout summary for a specific date."""
        exercise_logs_collection = self.conn["exercise_logs"]
        date_str = date_obj.isoformat()
        
        exercises_cursor = exercise_logs_collection.find(
            {"date": date_str},
            {"exercise_type": 1, "duration_minutes": 1, "calories_burned": 1}
        )
        
        exercises = list(exercises_cursor)
        if not exercises:
            return {"summary": "Rest day"}
        
        total_minutes = sum(e.get("duration_minutes", 0) for e in exercises)
        total_calories = sum(e.get("calories_burned", 0) or 0 for e in exercises)
        
        summary = f"{len(exercises)} workout(s), {total_minutes} min, {total_calories} cal"
        return {
            "count": len(exercises),
            "total_minutes": total_minutes,
            "total_calories": total_calories,
            "summary": summary
        }
    
    # ---------------------------------------------------------------------
    # Helper methods
    # ---------------------------------------------------------------------
    def _store_exercise(self, exercise: Dict, lifelog_id: str) -> str:
        """Store exercise log and return record ID."""
        exercise_logs_collection = self.conn["exercise_logs"]
        peloton = exercise.get("peloton_data", {})
        today = date.today()
        now = datetime.now()
        
        document = {
            "date": today.isoformat(),
            "timestamp": now.isoformat(),
            "exercise_type": exercise["type"],
            "duration_minutes": exercise["duration_minutes"],
            "calories_burned": exercise.get("calories_burned"),
            "peloton_strive_score": peloton.get("strive_score"),
            "peloton_output": peloton.get("output"),
            "peloton_avg_hr": peloton.get("avg_hr"),
            "training_zones": json.dumps(peloton.get("training_zones")) if peloton.get("training_zones") else None,
            "notes": exercise.get("notes"),
            "lifelog_id": lifelog_id,
            "created_at": now.isoformat()
        }
        
        result = exercise_logs_collection.insert_one(document)
        return str(result.inserted_id)
    
    def _update_training_day(self, date_obj: date, exercise: Dict, exercise_id: str):
        """Update training day intensity based on workout duration."""
        training_days_collection = self.conn["training_days"]
        duration = exercise.get("duration_minutes", 0)
        calories = exercise.get("calories_burned", 0)
        
        thresholds = self.config.get("intensity_thresholds", {})
        
        if duration < thresholds.get("light_max_minutes", 20):
            intensity = "light"
        elif duration < thresholds.get("moderate_max_minutes", 45):
            intensity = "moderate"
        else:
            intensity = "high"
        
        training_days_collection.replace_one(
            {"date": date_obj.isoformat()},
            {
                "date": date_obj.isoformat(),
                "intensity": intensity,
                "exercise_calories": calories,
                "primary_exercise_id": exercise_id,
                "notes": f"Auto: {exercise['type']} ({duration}min)"
            },
            upsert=True
        )
    
    def _create_exercise_embed(self, exercise: Dict, needs_electrolytes: bool):
        """Generate embed confirmation for standard workout logs."""
        import discord  # Local import to avoid audioop issues on Python 3.13
        
        embed = discord.Embed(
            title="🏋️ Workout Logged!",
            description=f"**{exercise['type'].title()}** - {exercise['duration_minutes']} minutes",
            color=0x00FF00
        )
        embed.add_field(
            name="📊 Stats",
            value=(
                f"**Calories:** {exercise.get('calories_burned', 'N/A')}\n"
                f"**Duration:** {exercise['duration_minutes']} min"
            ),
            inline=True
        )
        if needs_electrolytes:
            embed.add_field(
                name="⚡ Recommendation",
                value="**Take electrolytes!** (45+ min cardio)",
                inline=False
            )
        return embed
    
    def _create_peloton_embed(self, analysis: Dict, needs_electrolytes: bool):
        """Generate embed confirmation for Peloton logs."""
        import discord  # Local import to avoid audioop issues on Python 3.13
        
        embed = discord.Embed(
            title="🚴 Peloton Workout Logged!",
            description=f"**{analysis.get('ride_name', 'Ride')}** - {analysis['duration_minutes']} min",
            color=0xFF6900
        )
        embed.add_field(
            name="📊 Stats",
            value=(
                f"**Strive Score:** {analysis.get('strive_score', 'N/A')}\n"
                f"**Output:** {analysis.get('output', 'N/A')}\n"
                f"**Avg HR:** {analysis.get('avg_hr', 'N/A')} bpm\n"
                f"**Calories:** {analysis.get('calories', 'N/A')}"
            ),
            inline=True
        )
        if analysis.get("training_zones"):
            zones = analysis["training_zones"]
            embed.add_field(
                name="🎯 Training Zones",
                value=(
                    f"Z1: {zones.get('zone1', 0)}m | "
                    f"Z2: {zones.get('zone2', 0)}m | "
                    f"Z3: {zones.get('zone3', 0)}m\n"
                    f"Z4: {zones.get('zone4', 0)}m | "
                    f"Z5: {zones.get('zone5', 0)}m"
                ),
                inline=False
            )
        if needs_electrolytes:
            embed.add_field(
                name="⚡ Recommendation",
                value="**Take electrolytes!** (45+ min cardio)",
                inline=False
            )
        return embed
    
    def _create_error_embed(self, error_msg: str):
        """Return a standardized error embed."""
        import discord  # Local import to avoid audioop issues on Python 3.13
        
        return discord.Embed(
            title="❌ Error",
            description=f"Failed to process: {error_msg}",
            color=0xFF0000
        )
