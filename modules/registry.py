"""
Module registry for automatic discovery and routing.

The registry:
- Loads all enabled modules
- Routes keywords to appropriate modules
- Collects scheduled tasks
- Aggregates summaries
"""

from typing import Dict, List, Optional
from datetime import date


class ModuleRegistry:
    """Central registry for all automation modules"""
    
    def __init__(self, conn, openai_client, limitless_client, config: Dict):
        """
        Initialize registry and load modules.
        
        Args:
            conn: Database connection
            openai_client: OpenAI client instance
            limitless_client: Limitless client instance
            config: Configuration dict from config.yaml
        """
        self.conn = conn
        self.openai_client = openai_client
        self.limitless_client = limitless_client
        self.config = config
        self.modules = []
        
        self.load_modules()
    
    def load_modules(self):
        """Load all enabled modules from configuration"""
        # Import modules
        from .nutrition import NutritionModule
        from .workout import WorkoutModule
        # Add more imports as you create modules
        
        # Map of module names to classes
        available_modules = {
            'nutrition': NutritionModule,
            'workout': WorkoutModule,
            # Add more mappings here
        }
        
        # Load enabled modules
        for module_name, ModuleClass in available_modules.items():
            module_config = self.config.get('modules', {}).get(module_name, {})
            
            # Check if module is enabled
            if not module_config.get('enabled', False):
                print(f"⏭️  Skipping disabled module: {module_name}")
                continue
            
            try:
                # Instantiate module
                module = ModuleClass(
                    self.conn,
                    self.openai_client,
                    self.limitless_client,
                    module_config
                )
                
                self.modules.append(module)
                print(f"✅ Loaded module: {module.get_name()}")
                
            except Exception as e:
                print(f"❌ Failed to load module {module_name}: {e}")
                import traceback
                traceback.print_exc()
    
    def get_module_by_keyword(self, text: str) -> Optional[object]:
        """
        Find which module should handle this text based on keywords.
        
        Args:
            text: Text to check
            
        Returns:
            Module instance or None
        """
        for module in self.modules:
            if module.matches_keyword(text):
                return module
        return None
    
    def get_module_by_question(self, text: str) -> Optional[object]:
        """
        Find which module should answer this question.
        
        Args:
            text: Question text
            
        Returns:
            Module instance or None
        """
        for module in self.modules:
            if module.matches_question(text):
                return module
        return None
    
    def get_all_modules(self) -> List[object]:
        """
        Get all loaded modules.
        
        Returns:
            List of module instances
        """
        return self.modules
    
    def get_all_scheduled_tasks(self) -> List[Dict]:
        """
        Collect scheduled tasks from all modules.
        
        Returns:
            List of task dicts with 'time', 'function', and 'module' keys
        """
        tasks = []
        
        for module in self.modules:
            try:
                module_tasks = module.get_scheduled_tasks()
                
                for task in module_tasks:
                    task['module'] = module.get_name()
                    tasks.append(task)
                    
            except Exception as e:
                print(f"⚠️  Failed to get tasks from {module.get_name()}: {e}")
        
        return tasks
    
    async def get_daily_summary_all(self, date_obj: date) -> Dict:
        """
        Get daily summary from all modules.
        
        Args:
            date_obj: Date to summarize
            
        Returns:
            Dict mapping module names to their summary data
        """
        summary = {}
        
        for module in self.modules:
            try:
                module_summary = await module.get_daily_summary(date_obj)
                summary[module.get_name()] = module_summary
            except Exception as e:
                print(f"⚠️  Failed to get summary from {module.get_name()}: {e}")
                summary[module.get_name()] = {'error': str(e)}
        
        return summary
