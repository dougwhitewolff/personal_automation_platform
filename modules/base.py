"""
Base class for all automation modules.

All modules must inherit from BaseModule and implement its abstract methods.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
from datetime import date, datetime
import re
import pytz
from utils.logger import get_logger


class BaseModule(ABC):
    """
    Abstract base class for automation modules.
    
    Modules are self-contained units that handle:
    - Keyword detection ("log that", "track this")
    - Data logging and storage
    - Image processing
    - Scheduled tasks
    
    Note: Question answering is now handled by the RAG service via the orchestrator.
    Modules focus solely on data ingestion and storage.
    
    Each module maintains its own database collections and logic.
    """
    
    def __init__(self, db, openai_client, limitless_client, config=None, timezone: str = "America/Los_Angeles", rag_service=None):
        """
        Initialize module.
        
        Args:
            db: MongoDB database instance
            openai_client: OpenAI client instance
            limitless_client: Limitless API client instance
            config: Module-specific configuration from config.yaml
            timezone: Timezone string (e.g., "America/Los_Angeles") for date calculations
            rag_service: Optional RAGService instance for automatic vectorization
        """
        self.db = db
        self.openai_client = openai_client
        self.limitless_client = limitless_client
        self.config = config or {}
        self.timezone = pytz.timezone(timezone)
        self.rag_service = rag_service
        
        # Setup database collections
        self.setup_database()
        
        # Initialize logger after setup (so we can use get_name() if needed)
        try:
            module_name = self.get_name()
        except:
            module_name = self.__class__.__name__.lower()
        self.logger = get_logger(f"module.{module_name}")
    
    @abstractmethod
    def get_name(self) -> str:
        """
        Return unique module identifier.
        
        Returns:
            Module name (e.g., 'nutrition', 'workout', 'expenses')
        """
        pass
    
    @abstractmethod
    def get_keywords(self) -> List[str]:
        """
        Return keywords that trigger this module.
        
        Keywords are checked against user messages to determine if this
        module should process the message.
        
        Returns:
            List of trigger keywords (e.g., ['log that', 'track food'])
        """
        pass
    
    @abstractmethod
    def get_question_patterns(self) -> List[str]:
        """
        Return regex patterns for questions this module can answer.
        
        Returns:
            List of regex patterns (e.g., [r'how much.*protein', r'calories.*today'])
        """
        pass
    
    @abstractmethod
    def setup_database(self):
        """
        Create database tables needed by this module.
        
        Called during module initialization. Should create all tables
        using CREATE TABLE IF NOT EXISTS to be idempotent.
        """
        pass
    
    @abstractmethod
    async def handle_log(self, message_content: str, lifelog_id: str, 
                        analysis: Dict) -> Optional[Dict]:
        """
        Process a 'log that' command.
        
        Args:
            message_content: Full message text from user
            lifelog_id: Unique ID for this lifelog entry
            analysis: Pre-analyzed data from OpenAI (may be empty dict)
            
        Returns:
            Dict with 'embed' key containing Discord embed data, or None
        """
        pass
    
    @abstractmethod
    async def handle_image(self, image_bytes: bytes, context: str) -> Dict:
        """
        Process an uploaded image.
        
        Args:
            image_bytes: Raw image data
            context: Message text accompanying the image
            
        Returns:
            Dict with:
                - 'needs_confirmation': bool (whether to ask user to confirm)
                - 'embed': Discord embed for display
                - 'data': Extracted data (if needs_confirmation=True)
        """
        pass
    
    @abstractmethod
    def get_scheduled_tasks(self) -> List[Dict]:
        """
        Return scheduled tasks this module needs.
        
        Returns:
            List of task dicts with keys:
                - 'time': str in HH:MM format
                - 'function': callable (async or sync)
        """
        pass
    
    @abstractmethod
    async def get_daily_summary(self, date_obj) -> Dict:
        """
        Return daily summary data for this module.
        
        Args:
            date_obj: datetime.date object
            
        Returns:
            Dict with summary data (format varies by module)
        """
        pass
    
    # Helper methods (don't need to override)
    
    def get_today_in_timezone(self) -> date:
        """
        Get today's date in the configured timezone.
        
        Returns:
            date object representing today in the configured timezone
        """
        now_tz = datetime.now(self.timezone)
        return now_tz.date()
    
    def get_now_in_timezone(self) -> datetime:
        """
        Get current datetime in the configured timezone.
        
        Returns:
            datetime object representing now in the configured timezone
        """
        return datetime.now(self.timezone)
    
    def matches_keyword(self, text: str) -> bool:
        """
        Check if text contains any of this module's keywords.
        
        Args:
            text: Text to check
            
        Returns:
            True if any keyword matches
        """
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in self.get_keywords())
    
    import re

    def matches_question(self, text: str) -> bool:
        """Return True if text matches any question pattern (case-insensitive)."""
        for pattern in self.get_question_patterns():
            if re.search(pattern, text, re.IGNORECASE):
                self.logger.debug(f"Regex matched pattern: {pattern!r} in text: {repr(text[:100])}")
                return True
        self.logger.debug(f"No regex match for text: {repr(text[:100])}")
        return False
    
    def _vectorize_record(self, record: Dict, collection_name: str, delete_existing: bool = False) -> bool:
        """
        Helper method to vectorize a record after storing it.
        
        Args:
            record: MongoDB document that was just stored
            collection_name: Name of the collection the record belongs to
            delete_existing: If True, delete existing vectors for this record first (for upserts)
            
        Returns:
            True if vectorization succeeded, False otherwise
        """
        if not self.rag_service:
            self.logger.debug(f"RAG service not available, skipping vectorization for {collection_name}")
            return False
        
        try:
            record_id = str(record.get("_id", "unknown"))
            
            # For upsert operations, delete existing vectors first to avoid duplicates
            if delete_existing and record.get("_id"):
                source_id = str(record["_id"])
                self.logger.debug(f"Deleting existing vectors for {collection_name} record {source_id}")
                self.rag_service.delete_documents_by_source_id(source_id, collection_name)
            
            self.logger.info(f"Vectorizing {collection_name} record {record_id}")
            result = self.rag_service.vectorize_record(record, collection_name)
            if result:
                self.logger.info(f"✓ Successfully vectorized {collection_name} record {record_id}")
            else:
                self.logger.warning(f"Vectorization returned False for {collection_name} record {record_id}")
            return result
        except Exception as e:
            # Don't fail logging if vectorization fails
            self.logger.error(f"Failed to vectorize record from {collection_name}: {e}", exc_info=True)
            return False
