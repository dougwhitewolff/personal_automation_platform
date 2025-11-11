"""
Base class for all automation modules.

All modules must inherit from BaseModule and implement its abstract methods.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional
import re


class BaseModule(ABC):
    """
    Abstract base class for automation modules.
    
    Modules are self-contained units that handle:
    - Keyword detection ("log that", "track this")
    - Question pattern matching ("how much protein?")
    - Data logging and storage
    - Question answering
    - Image processing
    - Scheduled tasks
    
    Each module maintains its own database collections and logic.
    """
    
    def __init__(self, conn, openai_client, limitless_client, config=None):
        """
        Initialize module.
        
        Args:
            conn: MongoDB database object
            openai_client: OpenAI client instance
            limitless_client: Limitless API client instance
            config: Module-specific configuration from config.yaml
        """
        self.conn = conn
        self.openai_client = openai_client
        self.limitless_client = limitless_client
        self.config = config or {}
        
        # Setup database collections
        self.setup_database()
    
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
        Create database collections and indexes needed by this module.
        
        Called during module initialization. Should create all collections
        and indexes. Collections are created automatically on first insert,
        but indexes should be created here for performance.
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
    async def handle_query(self, query: str, context: Dict) -> str:
        """
        Answer a question about module data.
        
        Args:
            query: User's question
            context: Additional context (lifelogs, etc.)
            
        Returns:
            Natural language answer
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
                print(f"🔍 Regex matched pattern: {pattern!r} in text: {repr(text)}")
                return True
        print(f"🚫 No regex match for text: {repr(text)}")
        return False
