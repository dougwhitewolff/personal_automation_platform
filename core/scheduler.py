"""
Task scheduler for automated notifications and summaries.

Collects scheduled tasks from all modules and runs them at specified times.
"""

import schedule
import time
from datetime import datetime
import pytz
from typing import Dict, List


class Scheduler:
    """Manages scheduled tasks from all modules"""
    
    def __init__(self, timezone: str = 'America/Los_Angeles'):
        self.timezone = pytz.timezone(timezone)
        self.tasks = []
    
    def add_task(self, time_str: str, function, module_name: str):
        """
        Add a scheduled task.
        
        Args:
            time_str: Time in HH:MM format (24-hour)
            function: Async or sync function to call
            module_name: Name of module adding the task
        """
        self.tasks.append({
            'time': time_str,
            'function': function,
            'module': module_name
        })
        
        schedule.every().day.at(time_str).do(self._run_task, function, module_name)
        print(f"  ⏰ Scheduled: {module_name} at {time_str}")
    
    def _run_task(self, function, module_name: str):
        """Execute a scheduled task"""
        try:
            # Check if function is async
            import asyncio
            import inspect
            
            if inspect.iscoroutinefunction(function):
                # Async function
                asyncio.create_task(function())
            else:
                # Sync function
                function()
                
            print(f"✅ Executed scheduled task: {module_name}")
            
        except Exception as e:
            print(f"❌ Scheduled task failed ({module_name}): {e}")
    
    def load_from_registry(self, registry):
        """
        Load scheduled tasks from all modules in registry.
        
        Args:
            registry: ModuleRegistry instance
        """
        all_tasks = registry.get_all_scheduled_tasks()
        
        for task in all_tasks:
            self.add_task(
                task['time'],
                task['function'],
                task['module']
            )
    
    def run(self):
        """Start the scheduler loop (blocking)"""
        print("✅ Scheduler started")
        
        while True:
            # Get current time in configured timezone
            now = datetime.now(self.timezone)
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    def get_next_run_times(self) -> List[Dict]:
        """Get next run times for all scheduled tasks"""
        jobs = schedule.get_jobs()
        return [
            {
                'task': job.job_func.__name__,
                'next_run': job.next_run.strftime('%Y-%m-%d %H:%M:%S') if job.next_run else 'Not scheduled'
            }
            for job in jobs
        ]
