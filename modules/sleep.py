"""
Sleep Module - Sleep tracking and analysis.

Features:
- Sleep duration logging
- Sleep quality tracking
- Sleep score tracking
- Image processing for sleep tracking app screenshots
- Daily sleep summaries
"""

from modules.base import BaseModule
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional
import re
import asyncio

# Optional import for OCR - module will work without it, just falls back to LLM
try:
    from rapidocr import RapidOCR
    OCR_AVAILABLE = True
except ImportError:
    RapidOCR = None
    OCR_AVAILABLE = False

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
        """Extract sleep data from sleep tracking app screenshots or smartwatch screens"""
        
        self.logger.info("Processing sleep image")
        
        # Try OCR first
        self.logger.info("Attempting OCR extraction...")
        ocr_text = await self._extract_text_with_ocr(image_bytes)
        
        sleep_data = None
        method_used = None
        
        if ocr_text and len(ocr_text.strip()) >= 10:
            # Try to parse sleep data from OCR text
            self.logger.info("Parsing OCR text for sleep data...")
            sleep_data = self._parse_sleep_data_from_text(ocr_text)
            
            if sleep_data and sleep_data.get("hours") and (sleep_data.get("bedtime") or sleep_data.get("wake_time")):
                method_used = "OCR"
                self.logger.info("✓ Successfully extracted sleep data using OCR")
            else:
                self.logger.info("OCR parsing failed, falling back to LLM...")
                sleep_data = None
        
        # Fall back to LLM if OCR failed
        if not sleep_data:
            method_used = "LLM"
            self.logger.info("Using LLM vision processing...")
            
            # Escaped JSON braces
            prompt = """Extract sleep tracking data from this image.

Look for sleep tracking information from apps like:
- Oura Ring
- Whoop
- Fitbit
- Apple Watch
- Garmin
- Sleep Cycle
- AutoSleep
- Other sleep tracking apps/devices

Extract the following information:
- Sleep duration (hours, or hours and minutes)
- Sleep score (if available, typically 0-100)
- Sleep quality/rating (if available)
- Bedtime and wake time (if visible)
- Deep sleep duration (if available)
- REM sleep duration (if available)
- Light sleep duration (if available)
- Sleep stages breakdown (if available)

Respond with ONLY valid JSON:
{{
  "hours": 7.5,
  "sleep_score": 85,
  "quality": "good/poor/restless/excellent" or null,
  "bedtime": "22:30" or null,
  "wake_time": "06:00" or null,
  "deep_sleep_hours": 1.5 or null,
  "rem_sleep_hours": 1.8 or null,
  "light_sleep_hours": 4.2 or null,
  "source": "Oura/Whoop/Fitbit/etc" or null,
  "confidence": "high/medium/low"
}}

If any field is not visible, use null. If you cannot identify this as a sleep tracking image, set all fields to null and confidence to "low"."""
            
            analysis = self.openai_client.analyze_image(image_bytes, prompt, model="gpt-5-nano")
            
            if "error" in analysis:
                return {
                    "needs_confirmation": False,
                    "embed": self._create_error_embed(analysis["error"])
                }
            
            # Check if sleep data was detected
            confidence = analysis.get("confidence", "low")
            hours = analysis.get("hours")
            
            if confidence == "low" or hours is None:
                return {
                    "needs_confirmation": False,
                    "embed": self._create_error_embed("Could not extract sleep data from image. Please ensure the image contains sleep tracking information.")
                }
            
            # Build sleep record in the format expected by _store_sleep
            sleep_data = {
                "detected": True,
                "hours": hours,
                "sleep_score": analysis.get("sleep_score"),
                "quality": analysis.get("quality"),
                "bedtime": analysis.get("bedtime"),
                "wake_time": analysis.get("wake_time"),
                "deep_sleep_hours": analysis.get("deep_sleep_hours"),
                "rem_sleep_hours": analysis.get("rem_sleep_hours"),
                "light_sleep_hours": analysis.get("light_sleep_hours"),
                "source": analysis.get("source")
            }
            
            # Use analysis dict for embed creation (LLM format)
            analysis_for_embed = analysis
        else:
            # OCR succeeded - format data for embed creation
            # Convert OCR format to match LLM format for embed
            analysis_for_embed = {
                "hours": sleep_data.get("hours"),
                "sleep_score": sleep_data.get("sleep_score"),
                "quality": sleep_data.get("quality"),
                "bedtime": sleep_data.get("bedtime"),
                "wake_time": sleep_data.get("wake_time"),
                "source": sleep_data.get("source", "Sleep Cycle")
            }
            # Ensure detected flag is set
            sleep_data["detected"] = True
        
        # Store sleep data (use "image" as lifelog_id since this came from an image)
        self._store_sleep(sleep_data, "image")
        
        # Create confirmation embed
        embed = self._create_sleep_image_embed(analysis_for_embed)
        
        # Build what was logged for notifications
        hours = sleep_data.get("hours", 0)
        logged_items = []
        logged_items.append(f"Sleep: {hours:.1f} hours")
        if sleep_data.get("sleep_score"):
            logged_items.append(f"Score: {sleep_data.get('sleep_score')}")
        if sleep_data.get("quality"):
            logged_items.append(f"Quality: {sleep_data.get('quality')}")
        
        self.logger.info(f"✓ Successfully processed sleep image using {method_used}: {hours:.1f} hours")
        return {
            "needs_confirmation": False,  # Auto-confirm like workout module
            "embed": embed,
            "logged_items": logged_items,
            "logged_data": {
                "sleep": sleep_data
            }
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
    
    async def _extract_text_with_ocr(self, image_bytes: bytes) -> str:
        """Extract text from image using OCR (rapidocr)"""
        if not OCR_AVAILABLE:
            self.logger.debug("OCR not available (rapidocr not installed), skipping OCR extraction")
            return ""
        
        try:
            # Initialize RapidOCR
            # Run in a thread pool to avoid blocking (rapidocr is synchronous)
            loop = asyncio.get_event_loop()
            
            def run_ocr():
                ocr = RapidOCR()
                # RapidOCR can accept image bytes directly
                # Returns list of tuples: [(bbox, text, confidence), ...]
                result = ocr(image_bytes)
                return result
            
            # Run OCR in executor to avoid blocking
            result = await loop.run_in_executor(None, run_ocr)
            
            # Extract text from all detected text boxes
            # RapidOCR returns: [(bbox, text, confidence), ...]
            text_parts = []
            if result:
                for item in result:
                    if item and len(item) >= 2:
                        text = item[1]  # text is the second element
                        if text:
                            text_parts.append(text)
            
            ocr_text = " ".join(text_parts)
            self.logger.debug(f"OCR extracted {len(ocr_text)} characters")
            return ocr_text
            
        except Exception as e:
            self.logger.warning(f"OCR extraction failed: {e}")
            return ""
    
    def _parse_sleep_data_from_text(self, ocr_text: str) -> Optional[Dict]:
        """Parse sleep data from OCR text using regex patterns optimized for Sleep Cycle app format"""
        if not ocr_text or len(ocr_text.strip()) < 10:
            return None
        
        # Convert to lowercase for keyword matching, but keep original for time extraction
        text_lower = ocr_text.lower()
        
        # Extract bedtime - look for time pattern near "went to bed" or "bedtime"
        bedtime = None
        bedtime_patterns = [
            r'(?:went\s+to\s+bed|bedtime).*?(\d{1,2}:\d{2}\s*(?:AM|PM))',
            r'(\d{1,2}:\d{2}\s*(?:AM|PM)).*?(?:went\s+to\s+bed|bedtime)',
            r'bedtime.*?(\d{1,2}:\d{2}\s*(?:AM|PM))',
        ]
        for pattern in bedtime_patterns:
            match = re.search(pattern, ocr_text, re.IGNORECASE)
            if match:
                bedtime_str = match.group(1)
                bedtime = self._convert_to_24hour(bedtime_str)
                if bedtime:
                    break
        
        # Extract wake time - look for time pattern near "woke up" or "wake"
        wake_time = None
        wake_patterns = [
            r'(?:woke\s+up|wake\s+time|wake).*?(\d{1,2}:\d{2}\s*(?:AM|PM))',
            r'(\d{1,2}:\d{2}\s*(?:AM|PM)).*?(?:woke\s+up|wake)',
        ]
        for pattern in wake_patterns:
            match = re.search(pattern, ocr_text, re.IGNORECASE)
            if match:
                wake_str = match.group(1)
                wake_time = self._convert_to_24hour(wake_str)
                if wake_time:
                    break
        
        # If we don't have both bedtime and wake_time, try to find any two times that might be them
        if not bedtime or not wake_time:
            all_times = re.findall(r'(\d{1,2}:\d{2}\s*(?:AM|PM))', ocr_text, re.IGNORECASE)
            if len(all_times) >= 2:
                # Convert all times and try to identify bedtime/wake time
                converted_times = [self._convert_to_24hour(t) for t in all_times if self._convert_to_24hour(t)]
                if len(converted_times) >= 2:
                    # Assume first time is bedtime, second is wake time
                    # But check if they make sense (bedtime should be later in day, wake earlier)
                    for t1 in converted_times:
                        for t2 in converted_times:
                            if t1 != t2:
                                # Check if t1 is PM and t2 is AM (likely bedtime -> wake)
                                t1_hour = int(t1.split(':')[0])
                                t2_hour = int(t2.split(':')[0])
                                if t1_hour >= 18 or (t1_hour <= 6):  # PM or early AM
                                    if t2_hour <= 12:  # AM or early PM
                                        if not bedtime:
                                            bedtime = t1
                                        if not wake_time:
                                            wake_time = t2
                                        break
        
        # If we still don't have critical fields, return None
        if not bedtime or not wake_time:
            self.logger.debug("Could not extract bedtime and wake_time from OCR text")
            return None
        
        # Calculate sleep duration from bedtime to wake time
        hours = self._calculate_sleep_duration(bedtime, wake_time)
        if hours is None:
            return None
        
        # Extract regularity percentage
        regularity = None
        regularity_match = re.search(r'regularity.*?(\d+)%', text_lower, re.IGNORECASE)
        if regularity_match:
            try:
                regularity = int(regularity_match.group(1))
            except ValueError:
                pass
        
        # Extract time to fall asleep
        asleep_after_minutes = None
        asleep_match = re.search(r'asleep\s+after.*?(\d+)\s*min', text_lower, re.IGNORECASE)
        if asleep_match:
            try:
                asleep_after_minutes = int(asleep_match.group(1))
            except ValueError:
                pass
        
        # Derive quality from regularity if available
        quality = None
        if regularity:
            if regularity >= 85:
                quality = "excellent"
            elif regularity >= 70:
                quality = "good"
            elif regularity >= 50:
                quality = "fair"
            else:
                quality = "poor"
        
        # Build result dict
        result = {
            "hours": hours,
            "bedtime": bedtime,
            "wake_time": wake_time,
            "source": "Sleep Cycle",
            "quality": quality,
        }
        
        if regularity is not None:
            result["regularity"] = regularity
        if asleep_after_minutes is not None:
            result["asleep_after_minutes"] = asleep_after_minutes
        
        self.logger.info(f"Parsed sleep data from OCR: {hours:.2f}h, {bedtime} - {wake_time}")
        return result
    
    def _convert_to_24hour(self, time_str: str) -> Optional[str]:
        """Convert 12-hour time format (HH:MM AM/PM) to 24-hour format (HH:MM)"""
        try:
            # Remove extra spaces
            time_str = time_str.strip()
            # Match pattern like "8:09 PM" or "5:05 AM"
            match = re.match(r'(\d{1,2}):(\d{2})\s*(AM|PM)', time_str, re.IGNORECASE)
            if not match:
                return None
            
            hour = int(match.group(1))
            minute = int(match.group(2))
            period = match.group(3).upper()
            
            # Convert to 24-hour
            if period == "PM" and hour != 12:
                hour += 12
            elif period == "AM" and hour == 12:
                hour = 0
            
            return f"{hour:02d}:{minute:02d}"
        except Exception as e:
            self.logger.debug(f"Failed to convert time '{time_str}': {e}")
            return None
    
    def _calculate_sleep_duration(self, bedtime: str, wake_time: str) -> Optional[float]:
        """Calculate sleep duration in hours from bedtime to wake time, handling midnight crossing"""
        try:
            # Parse times (format: "HH:MM")
            bed_hour, bed_min = map(int, bedtime.split(':'))
            wake_hour, wake_min = map(int, wake_time.split(':'))
            
            # Convert to minutes since midnight
            bed_minutes = bed_hour * 60 + bed_min
            wake_minutes = wake_hour * 60 + wake_min
            
            # Handle midnight crossing
            if wake_minutes < bed_minutes:
                # Wake time is next day
                duration_minutes = (24 * 60 - bed_minutes) + wake_minutes
            else:
                duration_minutes = wake_minutes - bed_minutes
            
            # Convert to hours
            hours = duration_minutes / 60.0
            return hours
        except Exception as e:
            self.logger.debug(f"Failed to calculate sleep duration: {e}")
            return None
    
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
        
        # Build update document with all available sleep data
        update_doc = {
            "date": today.isoformat(),
            "hours": sleep['hours'],
            "sleep_score": sleep.get('sleep_score'),
            "quality_notes": sleep.get('quality'),
            "lifelog_id": lifelog_id,
            "created_at": now
        }
        
        # Add additional fields if available (from image processing)
        if sleep.get('bedtime'):
            update_doc['bedtime'] = sleep.get('bedtime')
        if sleep.get('wake_time'):
            update_doc['wake_time'] = sleep.get('wake_time')
        if sleep.get('deep_sleep_hours') is not None:
            update_doc['deep_sleep_hours'] = sleep.get('deep_sleep_hours')
        if sleep.get('rem_sleep_hours') is not None:
            update_doc['rem_sleep_hours'] = sleep.get('rem_sleep_hours')
        if sleep.get('light_sleep_hours') is not None:
            update_doc['light_sleep_hours'] = sleep.get('light_sleep_hours')
        if sleep.get('source'):
            update_doc['source'] = sleep.get('source')
        
        sleep_logs_collection.update_one(
            {"date": today.isoformat()},
            {"$set": update_doc},
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
    
    def _create_sleep_image_embed(self, analysis: Dict):
        """Generate embed confirmation for sleep image analysis."""
        import discord  # Local import to avoid audioop issues on Python 3.13
        
        hours = analysis.get("hours", 0)
        score = analysis.get("sleep_score")
        quality = analysis.get("quality")
        source = analysis.get("source")
        
        embed = discord.Embed(
            title="💤 Sleep Data Extracted!",
            description=f"**{hours:.1f} hours** of sleep",
            color=0x9B59B6  # Purple color for sleep
        )
        
        details = []
        if score:
            details.append(f"**Score:** {score}")
        if quality:
            details.append(f"**Quality:** {quality.title()}")
        if source:
            details.append(f"**Source:** {source}")
        
        # Add sleep stages if available
        stages = []
        if analysis.get("deep_sleep_hours"):
            stages.append(f"Deep: {analysis.get('deep_sleep_hours'):.1f}h")
        if analysis.get("rem_sleep_hours"):
            stages.append(f"REM: {analysis.get('rem_sleep_hours'):.1f}h")
        if analysis.get("light_sleep_hours"):
            stages.append(f"Light: {analysis.get('light_sleep_hours'):.1f}h")
        
        if stages:
            details.append(f"**Stages:** {', '.join(stages)}")
        
        # Add bedtime/wake time if available
        if analysis.get("bedtime") and analysis.get("wake_time"):
            details.append(f"**Time:** {analysis.get('bedtime')} - {analysis.get('wake_time')}")
        
        if details:
            embed.add_field(
                name="📊 Details",
                value="\n".join(details),
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

