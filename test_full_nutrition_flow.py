#!/usr/bin/env python3
"""
Test the FULL nutrition module flow with mock transcript.
Tests: OpenAI parsing, database storage, daily summary, embed creation.
"""

import sys
import os
from datetime import date
import asyncio

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.env_loader import get_env
from core import init_database, OpenAIClient
from modules import ModuleRegistry
import yaml

# Mock transcript - customize this to test different scenarios
MOCK_TRANSCRIPT = """So far today, I've eaten a large portion of smoothie and I've taken my morning supplements including D3, K2, fish oil, 5 milligrams of creatine.

I've also had two cups of hyacinth tea and one cup of coffee.

Log that."""

async def test_full_flow():
    """Test complete nutrition module flow"""
    
    print("=" * 70)
    print("  Full Nutrition Module Flow Test")
    print("=" * 70)
    print()
    
    # 1. Setup
    print("1. Initializing database and clients...")
    conn = init_database()  # Uses MONGODB_URL from environment
    openai_client = OpenAIClient(get_env("OPENAI_API_KEY"))
    
    # Mock LimitlessClient
    class MockLimitlessClient:
        def get_todays_transcript(self, timezone="America/Los_Angeles"):
            return MOCK_TRANSCRIPT
        def poll_recent_entries(self, *args, **kwargs):
            return []
    
    limitless_client = MockLimitlessClient()
    
    # Load config
    try:
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        print("⚠️  config.yaml not found, using defaults")
        config = {"modules": {"nutrition": {"enabled": True, "daily_targets": {}}}}
    
    # Initialize registry
    registry = ModuleRegistry(conn, openai_client, limitless_client, config)
    nutrition_module = None
    for module in registry.modules:
        if module.get_name() == "nutrition":
            nutrition_module = module
            break
    
    if not nutrition_module:
        print("❌ Nutrition module not found!")
        return
    
    print("✅ Setup complete")
    print()
    
    # 2. Show mock transcript
    print("2. Mock Transcript:")
    print("-" * 70)
    print(MOCK_TRANSCRIPT)
    print("-" * 70)
    print()
    
    # 3. Test handle_log (full flow)
    print("3. Testing handle_log() - Full flow...")
    print("   (This will: parse transcript, store in DB, calculate summary, create embed)")
    print()
    
    try:
        result = await nutrition_module.handle_log(
            message_content="Log that.",
            lifelog_id="test_mock_001",
            analysis={}
        )
        
        print("✅ handle_log() completed")
        print()
        
        # 4. Check database
        print("4. Checking database storage...")
        food_logs_collection = conn["food_logs"]
        date_str = date.today().isoformat()
        
        # Count food entries
        food_count = food_logs_collection.count_documents({"date": date_str})
        
        # Get totals using aggregation
        totals_pipeline = [
            {"$match": {"date": date_str}},
            {"$group": {
                "_id": None,
                "total_calories": {"$sum": "$calories"},
                "total_protein": {"$sum": "$protein_g"}
            }}
        ]
        totals_result = list(food_logs_collection.aggregate(totals_pipeline))
        
        print(f"   Food entries stored: {food_count}")
        if totals_result and totals_result[0].get("total_calories"):
            total_calories = totals_result[0].get("total_calories", 0) or 0
            total_protein = totals_result[0].get("total_protein", 0) or 0
            print(f"   Total calories: {total_calories:.0f}")
            print(f"   Total protein: {total_protein:.0f}g")
        else:
            print("   No food data stored yet")
        print()
        
        # 5. Check daily summary
        print("5. Daily summary:")
        summary = nutrition_module._get_daily_summary_internal(date.today())
        print(f"   {summary['summary']}")
        print(f"   Totals: {summary['totals']}")
        print()
        
        # 6. Check embed
        print("6. Discord embed created:")
        if result.get('embed'):
            embed = result['embed']
            print(f"   Title: {embed.title}")
            print(f"   Description: {embed.description}")
            print(f"   Fields: {len(embed.fields)}")
            for field in embed.fields:
                print(f"     - {field.name}: {field.value[:50]}...")
        else:
            print("   ❌ No embed returned")
        print()
        
        # 7. Test query
        print("7. Testing handle_query()...")
        answer = await nutrition_module.handle_query(
            query="How much protein have I eaten today?",
            context={}
        )
        print(f"   Answer: {answer[:150]}...")
        print()
        
        print("=" * 70)
        print("✅ Full flow test complete!")
        print("=" * 70)
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_full_flow())


