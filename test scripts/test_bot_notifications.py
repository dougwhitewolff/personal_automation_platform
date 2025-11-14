#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test Bot Confirmation Notifications

Tests that Limitless transcript polling correctly sends Discord bot notifications.
This script mocks the Limitless polling loop and verifies notification flow.

Usage:
    python "test scripts/test_bot_notifications.py"
    
Options:
    --dry-run    : Don't actually send to Discord, just verify code path
    --real-bot   : Actually send notifications to Discord (requires bot to be running)
"""

import sys
import os
import asyncio
import argparse
from datetime import date, datetime, timedelta
import yaml

# Set UTF-8 encoding for Windows console
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from core.env_loader import get_env
from core import init_database, OpenAIClient, AutomationOrchestrator
from modules import ModuleRegistry
from main import is_entry_processed, mark_entry_processed, await_sync, send_limitless_notification, set_discord_channel
import discord


# Mock Discord channel for testing
class MockDiscordChannel:
    """Mock Discord channel that captures sent messages"""
    def __init__(self):
        self.sent_messages = []
        self.sent_embeds = []
    
    async def send(self, content=None, embed=None):
        """Capture sent messages"""
        if embed:
            self.sent_embeds.append(embed)
            print(f"📤 [MOCK] Would send embed: {embed.title if hasattr(embed, 'title') else 'No title'}")
        if content:
            self.sent_messages.append(content)
            print(f"📤 [MOCK] Would send message: {content[:100]}...")
        return MockMessage()
    
    def get_sent_count(self):
        """Get total number of messages/embeds sent"""
        return len(self.sent_messages) + len(self.sent_embeds)


class MockMessage:
    """Mock Discord message object"""
    pass


# Mock LimitlessClient for testing
class MockLimitlessClient:
    """Mock Limitless client that returns test entries"""
    def __init__(self, test_entries):
        self.test_entries = test_entries
        self.call_count = 0
    
    def search_lifelogs(self, query="log that or summary request", limit=3, timezone="America/Los_Angeles", direction="desc"):
        """Return test entries matching semantic search"""
        self.call_count += 1
        return self.test_entries


def create_test_entries_nutrition():
    """Create test entries for nutrition logging"""
    base_time = datetime.now()
    return [
        {
            "id": "test_entry_11",
            "startTime": (base_time - timedelta(minutes=5)).isoformat(),
            "endTime": (base_time - timedelta(minutes=4)).isoformat(),
            "markdown": "I had a protein smoothie with banana, protein powder, and almond milk. Log that."
        }
    ]


def create_test_entries_workout():
    """Create test entries for workout logging"""
    base_time = datetime.now()
    return [
        {
            "id": "test_entry_12",
            "startTime": (base_time - timedelta(minutes=5)).isoformat(),
            "endTime": (base_time - timedelta(minutes=4)).isoformat(),
            "markdown": "Just finished a 30-minute Peloton ride. Log that."
        }
    ]


def create_test_entries_multi():
    """Create test entries that trigger multiple modules"""
    base_time = datetime.now()
    return [
        {
            "id": "test_entry_13",
            "startTime": (base_time - timedelta(minutes=10)).isoformat(),
            "endTime": (base_time - timedelta(minutes=9)).isoformat(),
            "markdown": "I just finished a 45-minute Peloton ride."
        },
        {
                "id": "test_entry_14",
            "startTime": (base_time - timedelta(minutes=5)).isoformat(),
            "endTime": (base_time - timedelta(minutes=4)).isoformat(),
            "markdown": "Had a protein smoothie after the workout. Log that."
        }
    ]


def create_test_entries_summary():
    """Create test entries for summary request"""
    base_time = datetime.now()
    return [
        {
            "id": "test_entry_15",
            "startTime": (base_time - timedelta(minutes=5)).isoformat(),
            "endTime": (base_time - timedelta(minutes=4)).isoformat(),
            "markdown": "Show me my summary for today"
        }
    ]


async def simulate_polling_loop_iteration(
    limitless_client, 
    registry, 
    db, 
    orchestrator,
    test_entries
):
    """
    Simulate one iteration of the polling loop with test entries.
    This mimics the logic from main.py polling_loop() using semantic search.
    """
    # Search semantically for "log that" or summary requests
    entries = limitless_client.search_lifelogs(
        query="log that or summary request",
        limit=3,
        timezone="America/Los_Angeles",
        direction="desc"
    )
    
    if not entries:
        return {"processed": 0, "notifications": 0}
    
    print(f"📥 Found {len(entries)} entry/entries from semantic search")
    
    notifications_sent = 0
    
    # Process each entry
    for entry in entries:
        lifelog_id = entry.get("id")
        markdown = entry.get("markdown", "")
        
        # Check if already processed
        if is_entry_processed(db, lifelog_id):
            print(f"⏭️  Skipping already-processed entry: {lifelog_id}")
            continue
        
        print(f"🔍 Processing entry: {lifelog_id}")
        
        # Route via orchestrator - pass entry markdown directly (API provides full context)
        routing_decision = orchestrator.route_intent(
            transcript=markdown,
            source="limitless",
            context={"lifelog_id": lifelog_id}
        )
        
        # Handle routing decision
        if routing_decision.get("error"):
            print(f"⚠️  Orchestrator error: {routing_decision['error']}")
            error_embed = discord.Embed(
                title="❌ Routing Error",
                description=f"Failed to route entry: {routing_decision['error']}",
                color=0xFF0000
            )
            if await send_limitless_notification(embed=error_embed):
                notifications_sent += 1
            mark_entry_processed(db, lifelog_id)  # Mark as processed even on error
            continue
        
        # Handle summary requests
        if routing_decision.get("summary_request"):
            target_date = routing_decision.get("summary_date", date.today())
            print(f"📊 Summary request detected for {target_date.isoformat()}")
            
            from core.discord_bot import get_summary_for_date
            summary_embed = await get_summary_for_date(registry, target_date, channel=None)
            
            if summary_embed:
                if await send_limitless_notification(embed=summary_embed):
                    notifications_sent += 1
            
            mark_entry_processed(db, lifelog_id)
            continue
        
        # Handle out of scope
        if routing_decision.get("out_of_scope") or not routing_decision.get("modules"):
            print(f"ℹ️  Entry {lifelog_id} is out of scope or no modules matched")
            info_embed = discord.Embed(
                title="ℹ️ No Action Taken",
                description=f"Entry detected but no matching modules found.\n\nReasoning: {routing_decision.get('reasoning', 'Unknown')}",
                color=0xFFFF00
            )
            if await send_limitless_notification(embed=info_embed):
                notifications_sent += 1
            mark_entry_processed(db, lifelog_id)
            continue
        
        # Process modules in parallel
        async def process_module_async(module_decision, entry_markdown, entry_id, action):
            """Process a single module asynchronously"""
            module_name = module_decision["name"]
            confidence = module_decision.get("confidence", 0.8)
            
            # Find module in registry
            module = None
            for mod in registry.modules:
                if mod.get_name() == module_name:
                    module = mod
                    break
            
            if not module:
                print(f"⚠️  Module '{module_name}' not found in registry")
                return None
            
            if confidence < 0.7:
                print(f"⚠️  Skipping {module_name} due to low confidence ({confidence:.2f})")
                return None
            
            try:
                print(f"🧩 ROUTING: {module_name} ({action}, confidence: {confidence:.2f}) for entry {entry_id}")
                
                if action == "log":
                    result = await module.handle_log(entry_markdown, entry_id, {})
                elif action == "query":
                    result = await module.handle_log(entry_markdown, entry_id, {})
                else:
                    print(f"⚠️  Unknown action: {action}")
                    return None
                
                return {"module_name": module_name, "result": result}
            
            except Exception as e:
                print(f"❌ ERROR processing {module_name} for entry {entry_id}: {e}")
                import traceback
                traceback.print_exc()
                return {"module_name": module_name, "error": str(e)}
        
        # Process all modules in parallel
        modules_to_process = routing_decision["modules"]
        if len(modules_to_process) > 1:
            tasks = [
                process_module_async(
                    module_decision,
                    markdown,
                    lifelog_id,
                    module_decision.get("action", "log")
                )
                for module_decision in modules_to_process
            ]
            module_results = await asyncio.gather(*tasks, return_exceptions=True)
        else:
            module_decision = modules_to_process[0]
            result = await process_module_async(
                module_decision,
                markdown,
                lifelog_id,
                module_decision.get("action", "log")
            )
            module_results = [result] if result else []
        
        # Send Discord notifications and mark as processed
        processed_successfully = False
        for module_result in module_results:
            if module_result is None or isinstance(module_result, Exception):
                continue
            
            if module_result.get("error"):
                continue
            
            result = module_result.get("result")
            if result and result.get("embed"):
                # Verify channel is accessible before sending
                from main import _discord_channel, _discord_channel_lock
                with _discord_channel_lock:
                    channel_check = _discord_channel
                if channel_check is None:
                    print(f"⚠️  WARNING: Channel is None before sending notification for {lifelog_id}")
                if await send_limitless_notification(embed=result["embed"]):
                    notifications_sent += 1
                    processed_successfully = True
        
        # Mark as processed after successful handling
        if processed_successfully:
            mark_entry_processed(db, lifelog_id)
    
    return {"processed": len(entries), "notifications": notifications_sent}


async def test_notification_flow(dry_run=True):
    """Test the complete notification flow"""
    print("=" * 80)
    print("  Bot Confirmation Notifications Test")
    print("=" * 80)
    print()
    
    if dry_run:
        print("🔧 DRY RUN MODE: Notifications will be mocked (not sent to Discord)")
    else:
        print("⚠️  LIVE MODE: Notifications will be sent to Discord!")
        print("   Make sure your Discord bot is running and connected.")
    print()
    
    # Initialize components
    print("1. Initializing components...")
    db = init_database()
    openai_client = OpenAIClient(get_env("OPENAI_API_KEY"))
    
    try:
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        config = {"modules": {}}
    
    registry = ModuleRegistry(db, openai_client, None, config)
    orchestrator = AutomationOrchestrator(openai_client, registry)
    
    # Setup mock or real Discord channel
    mock_channel = None
    test_bot_instance = None
    bot_task = None
    
    if dry_run:
        mock_channel = MockDiscordChannel()
        set_discord_channel(mock_channel)
        print("✅ Mock Discord channel set up")
        
        # Verify channel is actually set and accessible
        from main import _discord_channel, _discord_channel_lock
        await asyncio.sleep(0.1)  # Small delay to ensure channel is set
        with _discord_channel_lock:
            verify_channel = _discord_channel
        if verify_channel is None:
            print("❌ ERROR: Channel was not set properly!")
            return False
        elif verify_channel is not mock_channel:
            print(f"⚠️  WARNING: Channel mismatch! Expected mock, got {type(verify_channel).__name__}")
        else:
            print(f"✅ Verified channel is set and accessible: {type(verify_channel).__name__}")
    else:
        # In real mode, create our own Discord bot connection to send notifications
        # Note: This is a separate process from main.py, so we need our own connection
        print("⚠️  Real mode: Creating Discord bot connection for testing...")
        print("   (This is separate from the main bot process)")
        
        try:
            import discord
            from discord.ext import commands
            
            # Get Discord credentials
            bot_token = get_env("DISCORD_BOT_TOKEN")
            channel_id = int(get_env("DISCORD_CHANNEL_ID"))
            
            # Create a simple bot client
            intents = discord.Intents.default()
            intents.message_content = True
            test_bot = commands.Bot(command_prefix='!', intents=intents)
            
            # Set up on_ready to get the channel
            channel_ready = asyncio.Event()
            test_channel = None
            
            @test_bot.event
            async def on_ready():
                nonlocal test_channel
                print(f"✅ Test bot connected as {test_bot.user}")
                test_channel = test_bot.get_channel(channel_id)
                if test_channel:
                    set_discord_channel(test_channel)
                    print(f"✅ Test bot channel set: {test_channel.name}")
                    channel_ready.set()
                else:
                    print(f"❌ ERROR: Could not find channel with ID {channel_id}")
                    channel_ready.set()  # Set anyway to unblock
            
            # Start the bot in the background
            async def start_bot():
                try:
                    await test_bot.start(bot_token)
                except discord.errors.LoginFailure as e:
                    print(f"❌ Failed to login: Invalid bot token")
                    channel_ready.set()
                except discord.errors.PrivilegedIntentsRequired as e:
                    print(f"❌ Missing required intents. Check bot permissions in Discord Developer Portal")
                    channel_ready.set()
                except Exception as e:
                    error_msg = str(e)
                    if "Already connected" in error_msg or "already running" in error_msg.lower():
                        print(f"⚠️  Bot token is already in use (main.py might be running)")
                        print(f"   Please stop main.py first, or use --dry-run mode for testing")
                    else:
                        print(f"❌ Failed to start test bot: {e}")
                    channel_ready.set()
            
            # Start bot connection
            bot_task = asyncio.create_task(start_bot())
            
            # Wait for channel to be ready (with timeout)
            try:
                await asyncio.wait_for(channel_ready.wait(), timeout=10.0)
            except asyncio.TimeoutError:
                print("❌ ERROR: Test bot failed to connect within 10 seconds")
                await test_bot.close()
                return False
            
            if test_channel is None:
                print("❌ ERROR: Could not get Discord channel")
                await test_bot.close()
                return False
            
            print("✅ Test bot ready for notifications")
            
            # Store bot reference for cleanup
            test_bot_instance = test_bot
            
        except Exception as e:
            print(f"❌ ERROR: Failed to set up Discord bot connection: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    print()
    
    # Test cases
    test_cases = [
        {
            "name": "Nutrition Logging",
            "entries": create_test_entries_nutrition(),
            "expected_notifications": 1
        },
        {
            "name": "Workout Logging",
            "entries": create_test_entries_workout(),
            "expected_notifications": 1
        },
        {
            "name": "Summary Request",
            "entries": create_test_entries_summary(),
            "expected_notifications": 1
        },
    ]
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"{'=' * 80}")
        print(f"TEST {i}: {test_case['name']}")
        print(f"{'=' * 80}")
        print()
        
        # Create mock client with test entries
        limitless_client = MockLimitlessClient(test_case["entries"])
        
        # Simulate polling loop iteration
        try:
            result = await simulate_polling_loop_iteration(
                limitless_client,
                registry,
                db,
                orchestrator,
                test_case["entries"]
            )
            
            print()
            print(f"✅ Processed {result['processed']} entries")
            print(f"📤 Sent {result['notifications']} notifications")
            
            if dry_run:
                print(f"📊 Mock channel received {mock_channel.get_sent_count()} messages/embeds")
            
            # Verify expected notifications
            if result['notifications'] >= test_case['expected_notifications']:
                print(f"✅ PASS: Expected at least {test_case['expected_notifications']} notification(s)")
                results.append(True)
            else:
                print(f"❌ FAIL: Expected {test_case['expected_notifications']} notification(s), got {result['notifications']}")
                results.append(False)
            
        except Exception as e:
            print(f"❌ ERROR: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
        
        print()
        print()
    
    # Cleanup: Close bot connection if we created one
    if test_bot_instance is not None:
        print()
        print("🔄 Closing test bot connection...")
        try:
            await test_bot_instance.close()
            if bot_task and not bot_task.done():
                await asyncio.sleep(1)  # Give it time to close
        except Exception as e:
            print(f"⚠️  Error closing bot: {e}")
    
    # Summary
    print("=" * 80)
    print("  TEST SUMMARY")
    print("=" * 80)
    print()
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")
    
    if passed == total:
        print("✅ All tests passed!")
        return True
    else:
        print(f"❌ {total - passed} test(s) failed")
        return False


def main():
    parser = argparse.ArgumentParser(description="Test bot confirmation notifications")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't send to Discord, just verify code path (default)"
    )
    parser.add_argument(
        "--real-bot",
        action="store_true",
        help="Actually send notifications to Discord (requires bot to be running)"
    )
    
    args = parser.parse_args()
    
    dry_run = not args.real_bot  # Default to dry-run unless --real-bot is specified
    
    try:
        success = await_sync(test_notification_flow(dry_run=dry_run))
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n🛑 Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

