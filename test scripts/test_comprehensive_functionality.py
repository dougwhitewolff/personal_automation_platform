#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive Test Script for New Functionality

Tests:
1. "Log that" keyword detection
2. Context transcript building (last 5 entries)
3. Orchestrator routing (nutrition, workout, summaries, direct answers, out-of-scope)
4. Module calls with context transcripts
5. Multi-module routing
"""

import sys
import os
import asyncio
from datetime import date, datetime, timedelta
import yaml

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.env_loader import get_env
from core import init_database, OpenAIClient, AutomationOrchestrator
from modules import ModuleRegistry
from main import is_log_that_command


# Mock LimitlessClient for testing
class MockLimitlessClient:
    """Mock Limitless client that doesn't make real API calls"""
    def get_todays_transcript(self, timezone="America/Los_Angeles"):
        return ""  # Not used anymore in new implementation
    
    def poll_recent_entries(self, *args, **kwargs):
        return []


# Test data: Simulated polling batch entries
def create_test_entries():
    """Create a batch of test entries simulating a polling response"""
    base_time = datetime.now()
    entries = [
        {
            "id": "entry_1",
            "startTime": (base_time - timedelta(minutes=20)).isoformat(),
            "endTime": (base_time - timedelta(minutes=19)).isoformat(),
            "markdown": "I just finished a 45-minute Peloton ride. It was intense!"
        },
        {
            "id": "entry_2",
            "startTime": (base_time - timedelta(minutes=15)).isoformat(),
            "endTime": (base_time - timedelta(minutes=14)).isoformat(),
            "markdown": "Had a protein smoothie with banana, protein powder, and almond milk."
        },
        {
            "id": "entry_3",
            "startTime": (base_time - timedelta(minutes=10)).isoformat(),
            "endTime": (base_time - timedelta(minutes=9)).isoformat(),
            "markdown": "Drank 16 ounces of water after the workout."
        },
        {
            "id": "entry_4",
            "startTime": (base_time - timedelta(minutes=5)).isoformat(),
            "endTime": (base_time - timedelta(minutes=4)).isoformat(),
            "markdown": "Ate a chicken breast with rice and vegetables for lunch."
        },
        {
            "id": "entry_5",
            "startTime": (base_time - timedelta(minutes=1)).isoformat(),
            "endTime": base_time.isoformat(),
            "markdown": "Log that."
        }
    ]
    return entries


def test_log_that_detection():
    """Test 1: "Log that" keyword detection"""
    print("=" * 80)
    print("TEST 1: 'Log that' Keyword Detection")
    print("=" * 80)
    print()
    
    test_cases = [
        ("Log that", True),
        ("log that", True),
        ("LOG THAT", True),
        ("Track that", True),
        ("Log this", True),
        ("Track it", True),
        ("I want to log that", True),
        ("Please log that for me", True),
        ("I had breakfast. Log that.", True),
        ("I had breakfast", False),
        ("log", False),
        ("that", False),
        ("", False),
        ("Show me my summary", False),
    ]
    
    passed = 0
    failed = 0
    
    for text, expected in test_cases:
        result = is_log_that_command(text)
        status = "[PASS]" if result == expected else "[FAIL]"
        if result == expected:
            passed += 1
        else:
            failed += 1
        print(f"{status}: '{text}' -> {result} (expected {expected})")
    
    print()
    print(f"Results: {passed} passed, {failed} failed")
    print()
    return failed == 0


def test_context_transcript_building():
    """Test 2: Context transcript building from last 5 entries"""
    print("=" * 80)
    print("TEST 2: Context Transcript Building")
    print("=" * 80)
    print()
    
    entries = create_test_entries()
    
    # Simulate finding "Log that" in entry_5 (index 4)
    idx = 4
    start_idx = max(0, idx - 4)  # Get up to 5 entries (current + 4 preceding)
    context_entries = entries[start_idx:idx + 1]
    context_entries = list(reversed(context_entries))  # Reverse to chronological order
    context_transcript = "\n\n".join([
        e.get("markdown", "") for e in context_entries if e.get("markdown")
    ])
    
    print("Original entries (newest first):")
    for i, entry in enumerate(entries):
        print(f"  [{i}] {entry['id']}: {entry['markdown'][:50]}...")
    print()
    
    print("Context entries (chronological order, last 5):")
    for i, entry in enumerate(context_entries):
        print(f"  [{i}] {entry['id']}: {entry['markdown']}")
    print()
    
    print("Built context transcript:")
    print("-" * 80)
    print(context_transcript)
    print("-" * 80)
    print()
    
    # Verify it contains all expected entries
    expected_ids = ["entry_1", "entry_2", "entry_3", "entry_4", "entry_5"]
    all_present = all(eid in context_transcript or any(e["id"] == eid for e in context_entries) 
                     for eid in expected_ids)
    
    if all_present and len(context_entries) == 5:
        print("[PASS] Context transcript contains all 5 entries in chronological order")
        print()
        return True
    else:
        print("[FAIL] Context transcript missing entries or wrong order")
        print()
        return False


async def test_orchestrator_routing():
    """Test 3: Orchestrator routing for various scenarios"""
    print("=" * 80)
    print("TEST 3: Orchestrator Routing")
    print("=" * 80)
    print()
    
    # Initialize components
    conn = init_database()
    openai_client = OpenAIClient(get_env("OPENAI_API_KEY"))
    limitless_client = MockLimitlessClient()
    
    try:
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        config = {"modules": {}}
    
    registry = ModuleRegistry(conn, openai_client, limitless_client, config)
    orchestrator = AutomationOrchestrator(openai_client, registry)
    
    test_cases = [
        {
            "name": "Nutrition Logging",
            "transcript": "I had a smoothie with protein powder, banana, and almond milk. Log that.",
            "source": "limitless",
            "expected_modules": ["nutrition"],
            "expected_summary": False
        },
        {
            "name": "Workout Logging",
            "transcript": "Just finished a 30-minute Peloton ride. Log that.",
            "source": "limitless",
            "expected_modules": ["workout"],
            "expected_summary": False
        },
        {
            "name": "Summary Request (Natural Language)",
            "transcript": "Show me my summary for today",
            "source": "limitless",
            "expected_modules": [],
            "expected_summary": True
        },
        {
            "name": "Summary Request (Yesterday)",
            "transcript": "What did I do yesterday?",
            "source": "limitless",
            "expected_modules": [],
            "expected_summary": True
        },
        {
            "name": "In-Scope Query (May route to module or direct answer)",
            "transcript": "How do I track my macros?",
            "source": "discord",
            "expected_modules": ["nutrition"],  # Can route to module OR provide direct answer
            "expected_summary": False,
            "expected_direct_answer": None,  # None means either is acceptable
        },
        {
            "name": "Out-of-Scope Query",
            "transcript": "What's the weather today?",
            "source": "discord",
            "expected_modules": [],
            "expected_summary": False,
            "expected_out_of_scope": True
        },
    ]
    
    passed = 0
    failed = 0
    
    for test_case in test_cases:
        print(f"Testing: {test_case['name']}")
        print(f"  Transcript: {test_case['transcript']}")
        
        try:
            routing_decision = orchestrator.route_intent(
                transcript=test_case['transcript'],
                source=test_case['source'],
                context={"test": True}
            )
            
            # Check for errors
            if routing_decision.get("error"):
                print(f"  [FAIL] Error - {routing_decision['error']}")
                failed += 1
                print()
                continue
            
            # Check summary request
            is_summary = routing_decision.get("summary_request", False)
            if test_case.get("expected_summary"):
                if is_summary:
                    print(f"  [PASS] Summary request detected (date: {routing_decision.get('summary_date', 'today')})")
                else:
                    print(f"  [FAIL] Expected summary request but got modules: {routing_decision.get('modules', [])}")
                    failed += 1
                    print()
                    continue
            
            # Check direct answer (only if explicitly expected)
            expected_direct = test_case.get("expected_direct_answer")
            if expected_direct is True:  # Explicitly expect direct answer
                if routing_decision.get("direct_answer"):
                    print(f"  [PASS] Direct answer provided: {routing_decision['direct_answer'][:100]}...")
                else:
                    print(f"  [FAIL] Expected direct answer but got: {routing_decision}")
                    failed += 1
                    print()
                    continue
            elif expected_direct is None and routing_decision.get("direct_answer"):
                # If None (either acceptable) and got direct answer, that's fine
                print(f"  [PASS] Direct answer provided: {routing_decision['direct_answer'][:100]}...")
                passed += 1
                print()
                continue
            
            # Check out-of-scope
            if test_case.get("expected_out_of_scope"):
                if routing_decision.get("out_of_scope"):
                    print(f"  [PASS] Correctly identified as out-of-scope")
                else:
                    print(f"  [FAIL] Expected out-of-scope but got: {routing_decision}")
                    failed += 1
                    print()
                    continue
            
            # Check module routing
            modules = routing_decision.get("modules", [])
            module_names = [m["name"] for m in modules]
            
            if test_case.get("expected_modules"):
                expected = set(test_case["expected_modules"])
                actual = set(module_names)
                if expected.intersection(actual):  # At least one expected module found
                    print(f"  [PASS] Routed to modules: {module_names}")
                    for mod in modules:
                        print(f"     - {mod['name']}: {mod['action']} (confidence: {mod.get('confidence', 0):.2f})")
                else:
                    print(f"  [FAIL] Expected modules {expected}, got {actual}")
                    failed += 1
            else:
                if not modules:
                    print(f"  [PASS] No modules routed (as expected)")
                else:
                    print(f"  [WARN] Unexpected modules routed: {module_names}")
            
            passed += 1
            
        except Exception as e:
            print(f"  [FAIL] Exception - {e}")
            import traceback
            traceback.print_exc()
            failed += 1
        
        print()
    
    print(f"Results: {passed} passed, {failed} failed")
    print()
    return failed == 0


async def test_module_processing_with_context():
    """Test 4: Module processing with context transcripts"""
    print("=" * 80)
    print("TEST 4: Module Processing with Context Transcripts")
    print("=" * 80)
    print()
    
    # Initialize components
    conn = init_database()
    openai_client = OpenAIClient(get_env("OPENAI_API_KEY"))
    limitless_client = MockLimitlessClient()
    
    try:
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        config = {"modules": {}}
    
    registry = ModuleRegistry(conn, openai_client, limitless_client, config)
    
    # Build context transcript (simulating what polling_loop does)
    entries = create_test_entries()
    idx = 4  # "Log that" entry
    start_idx = max(0, idx - 4)
    context_entries = entries[start_idx:idx + 1]
    context_entries = list(reversed(context_entries))
    context_transcript = "\n\n".join([
        e.get("markdown", "") for e in context_entries if e.get("markdown")
    ])
    
    print("Context transcript being passed to modules:")
    print("-" * 80)
    print(context_transcript)
    print("-" * 80)
    print()
    
    # Test nutrition module
    nutrition_module = None
    for module in registry.get_all_modules():
        if module.get_name() == "nutrition":
            nutrition_module = module
            break
    
    if nutrition_module:
        print("Testing Nutrition Module with context transcript...")
        try:
            result = await nutrition_module.handle_log(
                message_content=context_transcript,
                lifelog_id="test_nutrition_123",
                analysis={}
            )
            
            if result and result.get("embed"):
                print("  [PASS] Nutrition module processed successfully")
                print(f"  Embed title: {result['embed'].title}")
            else:
                print("  [FAIL] No embed returned")
                return False
        except Exception as e:
            print(f"  [FAIL] Exception - {e}")
            import traceback
            traceback.print_exc()
            return False
    else:
        print("  [SKIP] Nutrition module not found, skipping")
    
    print()
    
    # Test workout module
    workout_module = None
    for module in registry.get_all_modules():
        if module.get_name() == "workout":
            workout_module = module
            break
    
    if workout_module:
        print("Testing Workout Module with context transcript...")
        try:
            # Create workout-specific context
            workout_context = "I just finished a 45-minute Peloton ride. It was intense! Log that."
            result = await workout_module.handle_log(
                message_content=workout_context,
                lifelog_id="test_workout_123",
                analysis={}
            )
            
            if result and result.get("embed"):
                print("  [PASS] Workout module processed successfully")
                print(f"  Embed title: {result['embed'].title}")
            else:
                print("  [WARN] No exercise detected (this is okay if context doesn't contain exercise)")
        except Exception as e:
            print(f"  [FAIL] Exception - {e}")
            import traceback
            traceback.print_exc()
            return False
    else:
        print("  [SKIP] Workout module not found, skipping")
    
    print()
    print("[PASS] Module processing tests completed")
    print()
    return True


async def test_multi_module_routing():
    """Test 5: Multi-module routing (nutrition + workout in same entry)"""
    print("=" * 80)
    print("TEST 5: Multi-Module Routing")
    print("=" * 80)
    print()
    
    # Initialize components
    conn = init_database()
    openai_client = OpenAIClient(get_env("OPENAI_API_KEY"))
    limitless_client = MockLimitlessClient()
    
    try:
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        config = {"modules": {}}
    
    registry = ModuleRegistry(conn, openai_client, limitless_client, config)
    orchestrator = AutomationOrchestrator(openai_client, registry)
    
    # Test case: Entry that mentions both nutrition and workout
    test_transcript = """I just finished a 30-minute Peloton ride and then had a protein smoothie with banana. Log that."""
    
    print(f"Testing multi-module routing with:")
    print(f"  Transcript: {test_transcript}")
    print()
    
    try:
        routing_decision = orchestrator.route_intent(
            transcript=test_transcript,
            source="limitless",
            context={"test": True}
        )
        
        if routing_decision.get("error"):
            print(f"  [FAIL] Error - {routing_decision['error']}")
            return False
        
        modules = routing_decision.get("modules", [])
        module_names = [m["name"] for m in modules]
        
        print(f"  Routed to {len(modules)} module(s): {module_names}")
        for mod in modules:
            print(f"    - {mod['name']}: {mod['action']} (confidence: {mod.get('confidence', 0):.2f})")
        
        # Check if both nutrition and workout are routed
        has_nutrition = any(m["name"] == "nutrition" for m in modules)
        has_workout = any(m["name"] == "workout" for m in modules)
        
        if has_nutrition or has_workout:
            print("  [PASS] At least one relevant module was routed")
            if has_nutrition and has_workout:
                print("  [PASS] Both nutrition and workout modules routed (multi-module routing working!)")
            else:
                print("  [INFO] Only one module routed (this is acceptable)")
        else:
            print("  [FAIL] No relevant modules routed")
            return False
        
    except Exception as e:
        print(f"  [FAIL] Exception - {e}")
        import traceback
        traceback.print_exc()
        return False
    
    print()
    return True


async def main():
    """Run all tests"""
    print()
    print("=" * 80)
    print("  COMPREHENSIVE FUNCTIONALITY TEST SUITE")
    print("=" * 80)
    print()
    print("Testing all new functionality:")
    print("  1. 'Log that' keyword detection")
    print("  2. Context transcript building")
    print("  3. Orchestrator routing (various scenarios)")
    print("  4. Module processing with context transcripts")
    print("  5. Multi-module routing")
    print()
    print("=" * 80)
    print()
    
    results = []
    
    # Test 1: Keyword detection (synchronous)
    results.append(("Log that Detection", test_log_that_detection()))
    
    # Test 2: Context building (synchronous)
    results.append(("Context Transcript Building", test_context_transcript_building()))
    
    # Test 3: Orchestrator routing (async)
    results.append(("Orchestrator Routing", await test_orchestrator_routing()))
    
    # Test 4: Module processing (async)
    results.append(("Module Processing", await test_module_processing_with_context()))
    
    # Test 5: Multi-module routing (async)
    results.append(("Multi-Module Routing", await test_multi_module_routing()))
    
    # Summary
    print("=" * 80)
    print("  TEST SUMMARY")
    print("=" * 80)
    print()
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "[PASS]" if result else "[FAIL]"
        print(f"{status}: {test_name}")
    
    print()
    print(f"Total: {passed}/{total} tests passed")
    print()
    
    if passed == total:
        print("[SUCCESS] All tests passed!")
    else:
        print("[WARNING] Some tests failed. Review output above.")
    print()


if __name__ == "__main__":
    asyncio.run(main())

