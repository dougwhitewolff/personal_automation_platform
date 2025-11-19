"""
Health Module - Health markers tracking.

Features:
- Bowel movement tracking
- Weight tracking
- Electrolyte tracking
- Daily health summaries
"""

from modules.base import BaseModule
from datetime import date, datetime
from typing import Dict, List
# discord imported locally in methods to avoid audioop issues on Python 3.13


class HealthModule(BaseModule):
    """Health markers tracking"""
    
    def get_name(self) -> str:
        return "health"
    
    def get_keywords(self) -> List[str]:
        return [
            "bowel movement", "bm", "poop", "went to bathroom",
            "weighed", "weight", "weigh myself", "current weight",
            "took electrolytes", "electrolytes", "took supplements"
        ]
    
    def get_question_patterns(self) -> List[str]:
        return [
            r"how (much|many).*(weight|bowel)",
            r"what.*weight",
            r"did i.*(weight|bowel|electrolyte)",
            r"(weight|bowel|health).*(summary|stats|totals)"
        ]
    
    def setup_database(self):
        """Create health tracking collections and indexes"""
        daily_health = self.db["daily_health"]
        daily_health.create_index("date", unique=True)
        daily_health.create_index("lifelog_id")
    
    async def handle_log(self, message_content: str, lifelog_id: str, analysis: Dict) -> Dict:
        """Process health marker logging"""
        
        self.logger.info(f"Processing health log for lifelog_id: {lifelog_id}")
        
        # Escaped JSON braces to avoid KeyError during .format()
        prompt = """Extract health marker information from the transcript.

TRANSCRIPT:
{transcript}

Respond with ONLY valid JSON:
{{
  "health_markers": {{
    "weight_lbs": null,
    "bowel_movements": 0,
    "electrolytes_taken": true/false
  }}
}}

Note:
- weight_lbs: numeric value if weight is mentioned, null otherwise
- bowel_movements: number of bowel movements (usually 1, can be more if explicitly stated)
- electrolytes_taken: true if electrolytes/supplements were taken, false if explicitly not taken, null if not mentioned
"""
        
        # Perform OpenAI text analysis
        self.logger.debug(f"Analyzing transcript with OpenAI (length: {len(message_content)} chars)")
        analysis = self.openai_client.analyze_text(
            transcript=message_content,
            module_name=self.get_name(),
            prompt_template=prompt
        )
        
        # Handle errors
        if "error" in analysis:
            self.logger.error(f"OpenAI analysis error: {analysis['error']}")
            return {'embed': self._create_error_embed(analysis['error'])}
        
        # Get health markers
        health = analysis.get("health_markers", {})
        
        # Check if any health markers were detected
        weight = health.get('weight_lbs')
        bm = health.get('bowel_movements', 0)
        electrolytes = health.get('electrolytes_taken')
        
        if weight is None and bm == 0 and electrolytes is None:
            self.logger.warning("No health markers detected in transcript")
            return {"embed": self._create_error_embed("No health markers detected")}
        
        self.logger.info(f"Detected health markers: weight={weight} lbs, "
                        f"bowel_movements={bm}, electrolytes={electrolytes}")
        
        self._store_health_markers(health, lifelog_id)
        
        # Create confirmation embed
        embed = self._create_health_embed(health)
        
        # Build what was logged for notifications
        logged_items = []
        if weight is not None:
            logged_items.append(f"Weight: {weight} lbs")
        if bm > 0:
            logged_items.append(f"Bowel movements: {bm}")
        if electrolytes is not None and electrolytes:
            logged_items.append("Electrolytes taken")
        
        self.logger.info(f"✓ Successfully processed health log for lifelog_id: {lifelog_id}")
        return {
            "embed": embed,
            "logged_items": logged_items,
            "logged_data": {
                "health": health
            }
        }
    
    async def handle_image(self, image_bytes: bytes, context: str) -> Dict:
        """Health module does not process images"""
        return {
            "needs_confirmation": False,
            "embed": self._create_error_embed("Health module does not support image processing")
        }
    
    def get_scheduled_tasks(self) -> List[Dict]:
        """Health module does not schedule reminders directly."""
        return []
    
    async def get_daily_summary(self, date_obj: date) -> Dict:
        """Get daily health summary data"""
        date_str = date_obj.isoformat()
        daily_health_collection = self.db["daily_health"]
        health_data = daily_health_collection.find_one({"date": date_str})
        
        if not health_data:
            return {
                'summary': 'No health data',
                'bowel_movements': 0,
                'weight_lbs': None,
                'electrolytes_taken': False
            }
        
        bowel_movements = health_data.get("bowel_movements", 0)
        weight_lbs = health_data.get("weight_lbs")
        electrolytes_taken = health_data.get("electrolytes_taken", False)
        
        summary_parts = []
        if bowel_movements > 0:
            summary_parts.append(f"{bowel_movements} BM")
        if weight_lbs:
            summary_parts.append(f"Weight: {weight_lbs} lbs")
        if electrolytes_taken:
            summary_parts.append("Electrolytes taken")
        
        return {
            'summary': ", ".join(summary_parts) if summary_parts else 'No health data',
            'bowel_movements': bowel_movements,
            'weight_lbs': weight_lbs,
            'electrolytes_taken': electrolytes_taken
        }
    
    # Helper methods
    
    def _store_health_markers(self, health: Dict, lifelog_id: str):
        """Store health markers"""
        if not any(health.values()):
            self.logger.debug("No health markers to store")
            return
        
        weight = health.get('weight_lbs')
        bm = health.get('bowel_movements', 0)
        electrolytes = health.get('electrolytes_taken')
        self.logger.info(f"Storing health markers: weight={weight} lbs, "
                        f"bowel_movements={bm}, electrolytes={electrolytes}")
        
        daily_health_collection = self.db["daily_health"]
        today = self.get_today_in_timezone()
        now = self.get_now_in_timezone()
        
        # Get existing document if it exists
        existing = daily_health_collection.find_one({"date": today.isoformat()})
        
        update_data = {
            "date": today.isoformat(),
            "lifelog_id": lifelog_id,
            "created_at": now
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
        self.logger.info(f"✓ Stored health markers in MongoDB (date: {today.isoformat()})")
        # Vectorize the health record (fetch it after upsert)
        # Delete existing vectors first since this is an upsert operation
        health_record = daily_health_collection.find_one({"date": today.isoformat()})
        if health_record:
            self._vectorize_record(health_record, "daily_health", delete_existing=True)
    
    def _create_health_embed(self, health: Dict):
        """Generate embed confirmation for health marker logs."""
        import discord  # Local import to avoid audioop issues on Python 3.13
        
        weight = health.get('weight_lbs')
        bm = health.get('bowel_movements', 0)
        electrolytes = health.get('electrolytes_taken')
        
        # Determine what was logged
        items_logged = []
        if weight is not None:
            items_logged.append(f"Weight: {weight} lbs")
        if bm > 0:
            items_logged.append(f"Bowel movements: {bm}")
        if electrolytes is not None and electrolytes:
            items_logged.append("Electrolytes taken")
        
        embed = discord.Embed(
            title="🏥 Health Logged!",
            description="\n".join(items_logged) if items_logged else "Health markers updated",
            color=0x3498DB  # Blue color for health
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

