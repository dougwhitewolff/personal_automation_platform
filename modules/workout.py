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
        """Create exercise tracking tables"""
        cursor = self.conn.cursor()
        
        # Exercise logs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS exercise_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE NOT NULL,
                timestamp DATETIME NOT NULL,
                exercise_type TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                calories_burned INTEGER,
                peloton_strive_score INTEGER,
                peloton_output INTEGER,
                peloton_avg_hr INTEGER,
                training_zones TEXT,
                notes TEXT,
                lifelog_id TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Training days calendar
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS training_days (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE UNIQUE NOT NULL,
                intensity TEXT NOT NULL,
                exercise_calories INTEGER DEFAULT 0,
                primary_exercise_id INTEGER,
                notes TEXT,
                FOREIGN KEY (primary_exercise_id) REFERENCES exercise_logs(id)
            )
        """)
        
        self.conn.commit()
    
    async def handle_log(self, message_content: str, lifelog_id: str, analysis: Dict) -> Dict:
        """Process workout logging"""
        
        # message_content now contains the context transcript (last 5 entries from polling batch)
        # No need to fetch full day's transcript
        
        # Escaped JSON braces to avoid KeyError during .format()
        prompt = """Extract exercise information from the transcript.

TRANSCRIPT:
{transcript}

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
            transcript=message_content,
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
        # Handle None values from OpenAI (null in JSON becomes None in Python)
        duration_minutes = exercise.get("duration_minutes") or 0
        needs_electrolytes = (
            duration_minutes >= self.config.get("electrolyte_threshold_minutes", 45)
        )
        
        # Create confirmation embed
        embed = self._create_exercise_embed(exercise, needs_electrolytes)
        return {"embed": embed}
    
    async def handle_query(self, query: str, context: Dict) -> str:
        """Answer workout questions"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT date, exercise_type, duration_minutes, calories_burned
            FROM exercise_logs
            WHERE date >= date('now', '-7 days')
            ORDER BY date DESC
        """)
        
        exercises = [
            {
                "date": row[0],
                "type": row[1],
                "duration": row[2],
                "calories": row[3]
            }
            for row in cursor.fetchall()
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
        # Handle None values from OpenAI (null in JSON becomes None in Python)
        duration_minutes = analysis.get("duration_minutes") or 0
        calories = analysis.get("calories")
        
        exercise_data = {
            "exercise": {
                "detected": True,
                "type": "cycling",
                "duration_minutes": duration_minutes,
                "calories_burned": calories,
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
        
        # Handle None values from OpenAI (null in JSON becomes None in Python)
        # duration_minutes already extracted above
        needs_electrolytes = (
            duration_minutes >= self.config.get("electrolyte_threshold_minutes", 45)
        )
        
        embed = self._create_peloton_embed(analysis, needs_electrolytes)
        return {"needs_confirmation": False, "embed": embed}
    
    def get_scheduled_tasks(self) -> List[Dict]:
        """Workout module does not schedule reminders directly."""
        return []
    
    async def get_daily_summary(self, date_obj: date) -> Dict:
        """Get workout summary for a specific date."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT exercise_type, duration_minutes, calories_burned
            FROM exercise_logs
            WHERE date = ?
        """, (date_obj,))
        
        exercises = cursor.fetchall()
        if not exercises:
            return {"summary": "Rest day"}
        
        total_minutes = sum(e[1] for e in exercises)
        total_calories = sum(e[2] or 0 for e in exercises)
        
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
    def _store_exercise(self, exercise: Dict, lifelog_id: str) -> int:
        """Store exercise log and return record ID."""
        cursor = self.conn.cursor()
        peloton = exercise.get("peloton_data", {})
        today = date.today()
        now = datetime.now()
        
        # Handle None values from OpenAI (null in JSON becomes None in Python)
        duration_minutes = exercise.get("duration_minutes") or 0
        calories_burned = exercise.get("calories_burned")
        
        document = {
            "date": today.isoformat(),
            "timestamp": now.isoformat(),
            "exercise_type": exercise["type"],
            "duration_minutes": duration_minutes,
            "calories_burned": calories_burned,
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
    
    def _update_training_day(self, date_obj: date, exercise: Dict, exercise_id: int):
        """Update training day intensity based on workout duration."""
        training_days_collection = self.conn["training_days"]
        # Handle None values from OpenAI (null in JSON becomes None in Python)
        duration = exercise.get("duration_minutes") or 0
        calories = exercise.get("calories_burned") or 0
        
        thresholds = self.config.get("intensity_thresholds", {})
        
        if duration < thresholds.get("light_max_minutes", 20):
            intensity = "light"
        elif duration < thresholds.get("moderate_max_minutes", 45):
            intensity = "moderate"
        else:
            intensity = "high"
        
        cursor.execute("""
            INSERT OR REPLACE INTO training_days
            (date, intensity, exercise_calories, primary_exercise_id, notes)
            VALUES (?, ?, ?, ?, ?)
        """, (
            date_obj,
            intensity,
            calories,
            exercise_id,
            f"Auto: {exercise['type']} ({duration}min)"
        ))
        self.conn.commit()
    
    def _create_exercise_embed(self, exercise: Dict, needs_electrolytes: bool):
        """Generate embed confirmation for standard workout logs."""
        import discord  # Local import to avoid audioop issues on Python 3.13
        
        # Handle None values from OpenAI (null in JSON becomes None in Python)
        duration_minutes = exercise.get("duration_minutes") or 0
        calories_burned = exercise.get("calories_burned")
        
        embed = discord.Embed(
            title="🏋️ Workout Logged!",
            description=f"**{exercise['type'].title()}** - {duration_minutes} minutes",
            color=0x00FF00
        )
        embed.add_field(
            name="📊 Stats",
            value=(
                f"**Calories:** {calories_burned if calories_burned is not None else 'N/A'}\n"
                f"**Duration:** {duration_minutes} min"
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
        
        # Handle None values from OpenAI (null in JSON becomes None in Python)
        duration_minutes = analysis.get("duration_minutes") or 0
        
        embed = discord.Embed(
            title="🚴 Peloton Workout Logged!",
            description=f"**{analysis.get('ride_name', 'Ride')}** - {duration_minutes} min",
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
