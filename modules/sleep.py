"""
Sleep Module - Sleep tracking and analysis.

Features:
- Sleep duration logging
- Sleep quality tracking
- Sleep score tracking
- Daily sleep summaries
"""

from modules.base import BaseModule
from datetime import date, datetime
from typing import Dict, List
# discord imported locally in methods to avoid audioop issues on Python 3.13


class SleepModule(BaseModule):
    """Sleep tracking and analysis"""
    
    def get_name(self) -> str:
        return "sleep"
    
    def get_keywords(self) -> List[str]:
        return [
            "slept", "sleep", "woke up", "wake up",
            "went to bed", "bedtime", "sleep hours",
            "sleep quality", "sleep score", "how long did i sleep"
        ]
    
    def get_question_patterns(self) -> List[str]:
        return [
            r"how (much|long).*sleep",
            r"did i.*sleep",
            r"sleep (hours|duration|time)",
            r"what.*sleep.*(score|quality)"
        ]
    
    def setup_database(self):
        """Create sleep tracking collections and indexes"""
        sleep_logs = self.db["sleep_logs"]
        sleep_logs.create_index("date", unique=True)
        sleep_logs.create_index("lifelog_id")
    
    async def handle_log(self, message_content: str, lifelog_id: str, analysis: Dict) -> Dict:
        """Process sleep logging"""
        
        self.logger.info(f"Processing sleep log for lifelog_id: {lifelog_id}")
        
        # Escaped JSON braces to avoid KeyError during .format()
        prompt = """Extract sleep information from the transcript.

TRANSCRIPT:
{transcript}

Respond with ONLY valid JSON:
{{
  "sleep": {{
    "detected": true/false,
    "hours": 7.5,
    "sleep_score": 85,
    "quality": "good/poor/restless/excellent"
  }}
}}"""
        
        # Perform OpenAI text analysis
        self.logger.debug(f"Analyzing transcript with OpenAI (length: {len(message_content)} chars)")
        analysis = self.openai_client.analyze_text(
            transcript=message_content,
            module_name=self.get_name(),
            prompt_template=prompt
        )
        
        # Handle invalid or missing detection
        if "error" in analysis or not analysis.get("sleep", {}).get("detected"):
            self.logger.warning("No sleep detected in transcript")
            return {"embed": self._create_error_embed("No sleep detected")}
        
        # Store sleep data
        sleep = analysis["sleep"]
        hours = sleep.get("hours", 0)
        score = sleep.get("sleep_score")
        quality = sleep.get("quality")
        self.logger.info(f"Detected sleep: {hours:.1f} hours, score={score}, quality={quality}")
        
        self._store_sleep(sleep, lifelog_id)
        
        # Create confirmation embed
        embed = self._create_sleep_embed(sleep)
        
        # Build what was logged for notifications
        logged_items = []
        logged_items.append(f"Sleep: {hours:.1f} hours")
        if score:
            logged_items.append(f"Score: {score}")
        if quality:
            logged_items.append(f"Quality: {quality}")
        
        self.logger.info(f"✓ Successfully processed sleep log for lifelog_id: {lifelog_id}")
        return {
            "embed": embed,
            "logged_items": logged_items,
            "logged_data": {
                "sleep": sleep
            }
        }
    
    async def handle_image(self, image_bytes: bytes, context: str) -> Dict:
        """Sleep module does not process images"""
        return {
            "needs_confirmation": False,
            "embed": self._create_error_embed("Sleep module does not support image processing")
        }
    
    def get_scheduled_tasks(self) -> List[Dict]:
        """Sleep module does not schedule reminders directly."""
        return []
    
    async def get_daily_summary(self, date_obj: date) -> Dict:
        """Get daily sleep summary data"""
        date_str = date_obj.isoformat()
        sleep_logs_collection = self.db["sleep_logs"]
        sleep_data = sleep_logs_collection.find_one({"date": date_str})
        
        if not sleep_data:
            return {
                'summary': 'No sleep data',
                'hours': None,
                'score': None,
                'quality': None
            }
        
        hours = sleep_data.get("hours")
        score = sleep_data.get("sleep_score")
        quality = sleep_data.get("quality_notes")
        
        summary_parts = []
        if hours is not None:
            summary_parts.append(f"{hours:.1f}h sleep")
        if score:
            summary_parts.append(f"score: {score}")
        if quality:
            summary_parts.append(f"quality: {quality}")
        
        return {
            'summary': ", ".join(summary_parts) if summary_parts else 'No sleep data',
            'hours': hours,
            'score': score,
            'quality': quality
        }
    
    # Helper methods
    
    def _store_sleep(self, sleep: Dict, lifelog_id: str):
        """Store sleep logs"""
        if not sleep.get('detected'):
            self.logger.debug("No sleep detected")
            return
        
        hours = sleep.get('hours', 0)
        score = sleep.get('sleep_score')
        quality = sleep.get('quality')
        self.logger.info(f"Storing sleep: {hours:.1f} hours, score={score}, quality={quality}")
        
        sleep_logs_collection = self.db["sleep_logs"]
        today = self.get_today_in_timezone()
        now = self.get_now_in_timezone()
        
        sleep_logs_collection.update_one(
            {"date": today.isoformat()},
            {
                "$set": {
                    "date": today.isoformat(),
                    "hours": sleep['hours'],
                    "sleep_score": sleep.get('sleep_score'),
                    "quality_notes": sleep.get('quality'),
                    "lifelog_id": lifelog_id,
                    "created_at": now
                }
            },
            upsert=True
        )
        self.logger.info(f"✓ Stored sleep log in MongoDB (date: {today.isoformat()})")
        # Vectorize the sleep record (fetch it after upsert)
        # Delete existing vectors first since this is an upsert operation
        sleep_record = sleep_logs_collection.find_one({"date": today.isoformat()})
        if sleep_record:
            self._vectorize_record(sleep_record, "sleep_logs", delete_existing=True)
    
    def _create_sleep_embed(self, sleep: Dict):
        """Generate embed confirmation for sleep logs."""
        import discord  # Local import to avoid audioop issues on Python 3.13
        
        hours = sleep.get("hours", 0)
        score = sleep.get("sleep_score")
        quality = sleep.get("quality")
        
        embed = discord.Embed(
            title="💤 Sleep Logged!",
            description=f"**{hours:.1f} hours** of sleep",
            color=0x9B59B6  # Purple color for sleep
        )
        
        details = []
        if score:
            details.append(f"**Score:** {score}")
        if quality:
            details.append(f"**Quality:** {quality.title()}")
        
        if details:
            embed.add_field(
                name="📊 Details",
                value="\n".join(details),
                inline=True
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

