"""
Automated fix for discord import issues in nutrition.py and workout.py
This script removes top-level discord imports and adds them locally in methods.
"""

import re

def fix_nutrition_file():
    """Fix modules/nutrition.py"""
    
    with open('modules/nutrition.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove 'import discord' from imports section
    content = re.sub(
        r'(from typing import Dict, List\nimport json)\nimport discord',
        r'\1\n# discord imported locally in methods to avoid audioop issues on Python 3.13',
        content
    )
    
    # Add local import to _create_log_confirmation_embed if not present
    if 'def _create_log_confirmation_embed' in content and \
       'def _create_log_confirmation_embed' in content and \
       'import discord  # Local import' not in content[content.find('_create_log_confirmation_embed'):content.find('_create_log_confirmation_embed')+500]:
        content = re.sub(
            r'(def _create_log_confirmation_embed\(self, summary: Dict\):\n        """Create Discord embed for log confirmation"""\n        )',
            r'\1import discord  # Local import to avoid audioop issues on Python 3.13\n        \n        ',
            content
        )
    
    # Add local import to _create_food_image_embed if not present
    if 'def _create_food_image_embed' in content:
        content = re.sub(
            r'(def _create_food_image_embed\(self, analysis: Dict\):\n        """Create embed for food image analysis"""\n        )',
            r'\1import discord  # Local import to avoid audioop issues on Python 3.13\n        \n        ',
            content
        )
    
    # Add local import to _create_error_embed
    if '_create_error_embed' in content and 'nutrition.py' in str(content[:100]):
        content = re.sub(
            r'(def _create_error_embed\(self, error_msg: str\):\n        """Create error embed"""\n        )(return discord\.Embed\()',
            r'\1import discord  # Local import to avoid audioop issues on Python 3.13\n        \n        \2',
            content
        )
    
    with open('modules/nutrition.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Fixed modules/nutrition.py")


def fix_workout_file():
    """Fix modules/workout.py"""
    
    with open('modules/workout.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Remove 'import discord' from imports section
    content = re.sub(
        r'(from typing import Dict, List\nimport json)\nimport discord',
        r'\1\n# discord imported locally in methods to avoid audioop issues on Python 3.13',
        content
    )
    
    # Add local import to _create_exercise_embed
    if 'def _create_exercise_embed' in content:
        content = re.sub(
            r'(def _create_exercise_embed\(self, exercise: Dict, needs_electrolytes: bool\):\n        """Generate embed confirmation for standard workout logs\."""\n        )',
            r'\1import discord  # Local import to avoid audioop issues on Python 3.13\n        \n        ',
            content
        )
    
    # Add local import to _create_peloton_embed
    if 'def _create_peloton_embed' in content:
        content = re.sub(
            r'(def _create_peloton_embed\(self, analysis: Dict, needs_electrolytes: bool\):\n        """Generate embed confirmation for Peloton logs\."""\n        )',
            r'\1import discord  # Local import to avoid audioop issues on Python 3.13\n        \n        ',
            content
        )
    
    # Add local import to _create_error_embed
    if '_create_error_embed' in content:
        content = re.sub(
            r'(def _create_error_embed\(self, error_msg: str\):\n        """Return a standardized error embed\."""\n        )(return discord\.Embed\()',
            r'\1import discord  # Local import to avoid audioop issues on Python 3.13\n        \n        \2',
            content
        )
    
    with open('modules/workout.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ Fixed modules/workout.py")


if __name__ == "__main__":
    print("=" * 60)
    print("  Discord Import Fix Script")
    print("=" * 60)
    print()
    
    try:
        fix_nutrition_file()
        fix_workout_file()
        print()
        print("=" * 60)
        print("  ✅ SUCCESS! Both files fixed.")
        print("=" * 60)
        print()
        print("Now run:")
        print("  1. Remove-Item -Recurse -Force modules\\__pycache__")
        print("  2. python main.py")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()