# -*- coding: utf-8 -*-
"""
Personal Automation Platform - Main Entry Point (Python 3.13 compatible)

Coordinates all services:
- Limitless API polling
- Discord bot
- Task scheduler
- Module registry
- Database initialization
"""

import sys
import threading
import time
from datetime import datetime, date
import yaml
import asyncio

# Import core services (lazy Discord import handled in core/__init__.py)
from core import (
    init_database,
    LimitlessClient,
    OpenAIClient,
    Scheduler,
    AutomationOrchestrator,
    get_setup_bot,   # Lazy import function for Discord bot
)
from core.env_loader import get_env, validate_required_vars
from modules import ModuleRegistry

# Global reference to Discord channel (set after bot is ready)
_discord_channel = None
_discord_channel_lock = threading.Lock()

def set_discord_channel(channel):
    """Set the Discord channel for Limitless notifications"""
    global _discord_channel
    with _discord_channel_lock:
        _discord_channel = channel
        print(f'🔧 DEBUG: Channel set in set_discord_channel: {_discord_channel is not None}')

async def send_limitless_notification(embed=None, content=None):
    """
    Send notification from Limitless polling loop via Discord bot.
    
    Automatically retries if channel isn't ready yet (bot may still be connecting).
    This function handles the async nature of bot initialization gracefully.
    
    Returns:
        bool: True if notification was sent successfully, False otherwise
    """
    global _discord_channel, _discord_channel_lock
    
    # Try to get channel immediately
    channel = None
    with _discord_channel_lock:
        channel = _discord_channel
    
    # If channel not set, wait up to 5 seconds for bot to connect
    # This handles the case where polling loop starts before bot is ready
    if channel is None:
        for attempt in range(50):  # 50 * 0.1s = 5 seconds max wait
            await asyncio.sleep(0.1)
            with _discord_channel_lock:
                channel = _discord_channel
            if channel is not None:
                break
    
    if channel:
        try:
            if embed:
                await channel.send(embed=embed)
                title = embed.title if hasattr(embed, 'title') and embed.title else 'Notification'
                print(f"✅ Sent Discord notification: {title}")
            elif content:
                await channel.send(content)
                preview = content[:50] + "..." if len(content) > 50 else content
                print(f"✅ Sent Discord notification: {preview}")
            return True
        except Exception as e:
            print(f"❌ Failed to send Discord notification: {e}")
            import traceback
            traceback.print_exc()
            return False
    else:
        # Channel still not available - log warning with debug info
        with _discord_channel_lock:
            current_value = _discord_channel
        print(f"⚠️  Discord channel not available yet (bot may still be connecting). Notification will be skipped.")
        print(f"🔧 DEBUG: Channel value is: {current_value} (type: {type(current_value).__name__})")
        return False


def load_config() -> dict:
    """Load configuration from config.yaml."""
    try:
        with open("config.yaml", "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("WARNING: config.yaml not found, using defaults")
        return {"modules": {}}
    except Exception as e:
        print(f"ERROR: Error loading config.yaml: {e}")
        return {"modules": {}}


def validate_environment() -> None:
    """Ensure all required environment variables are present."""
    required_vars = [
        "LIMITLESS_API_KEY",
        "OPENAI_API_KEY",
        "DISCORD_BOT_TOKEN",
        "DISCORD_CHANNEL_ID",
    ]

    all_present, missing = validate_required_vars(required_vars)

    if not all_present:
        print(f"ERROR: Missing required environment variables: {', '.join(missing)}")
        print("   Please add them to your .env file and restart.")
        sys.exit(1)


def await_sync(coro):
    """Run an async coroutine from synchronous context."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def is_entry_processed(db, lifelog_id: str) -> bool:
    """
    Check if a lifelog entry has already been processed.
    
    Args:
        db: MongoDB database instance
        lifelog_id: Lifelog entry ID to check
        
    Returns:
        True if entry has been processed, False otherwise
    """
    processed_lifelogs = db["processed_lifelogs"]
    return processed_lifelogs.find_one({"lifelog_id": lifelog_id}) is not None


def mark_entry_processed(db, lifelog_id: str, source: str = "limitless"):
    """
    Mark a lifelog entry as processed.
    
    Args:
        db: MongoDB database instance
        lifelog_id: Lifelog entry ID to mark as processed
        source: Source of the entry (default "limitless")
    """
    processed_lifelogs = db["processed_lifelogs"]
    processed_lifelogs.update_one(
        {"lifelog_id": lifelog_id},
        {
            "$set": {
                "lifelog_id": lifelog_id,
                "processed_at": datetime.utcnow(),
                "source": source
            }
        },
        upsert=True
    )


def polling_loop(limitless_client, registry, db, orchestrator):
    """
    Poll Limitless API for new "log that" or summary requests using semantic search.
    
    Each iteration:
    - Searches semantically for "log that" or summary requests (limit 3, newest first)
    - Checks if entries are already processed (by lifelog_id)
    - Routes to orchestrator and processes modules
    - Marks entries as processed after successful handling
    """
    global _discord_channel, _discord_channel_lock  # Need to access global variable
    
    poll_interval = int(get_env("POLL_INTERVAL", "10"))  # Default 10 seconds
    timezone = get_env("TIMEZONE", "America/Los_Angeles")
    
    print(f"✅ Limitless polling started (every {poll_interval}s, semantic search, timezone: {timezone})")
    print("📡 Notifications will be sent when Discord bot is ready (automatic retry)")
    
    while True:
        try:
            # Search semantically for "log that" or summary requests
            # API returns entries in descending order (newest first), limit 3
            entries = limitless_client.search_lifelogs(
                query="log that or summary request",
                limit=3,
                timezone=timezone,
                direction="desc"
            )
            
            if not entries:
                # No matching entries - continue polling
                print(f"🔍 Polling... (no new entries found)")
                time.sleep(poll_interval)
                continue
            
            print(f"📥 Found {len(entries)} entry/entries from semantic search")
            
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
                    import discord
                    error_embed = discord.Embed(
                        title="❌ Routing Error",
                        description=f"Failed to route entry: {routing_decision['error']}",
                        color=0xFF0000
                    )
                    await_sync(send_limitless_notification(embed=error_embed))
                    mark_entry_processed(db, lifelog_id)  # Mark as processed even on error
                    continue
                
                # Handle summary requests
                if routing_decision.get("summary_request"):
                    target_date = routing_decision.get("summary_date", date.today())
                    print(f"📊 Summary request detected for {target_date.isoformat()}")
                    
                    from core.discord_bot import get_summary_for_date
                    summary_embed = await_sync(get_summary_for_date(registry, target_date, channel=None))
                    
                    if summary_embed:
                        await_sync(send_limitless_notification(embed=summary_embed))
                    
                    mark_entry_processed(db, lifelog_id)
                    continue
                
                # Handle out of scope
                if routing_decision.get("out_of_scope") or not routing_decision.get("modules"):
                    print(f"ℹ️  Entry {lifelog_id} is out of scope or no modules matched")
                    import discord
                    info_embed = discord.Embed(
                        title="ℹ️ No Action Taken",
                        description=f"Entry detected but no matching modules found.\n\nReasoning: {routing_decision.get('reasoning', 'Unknown')}",
                        color=0xFFFF00
                    )
                    await_sync(send_limitless_notification(embed=info_embed))
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
                    module_results = await_sync(asyncio.gather(*tasks, return_exceptions=True))
                else:
                    module_decision = modules_to_process[0]
                    result = await_sync(
                        process_module_async(
                            module_decision,
                            markdown,
                            lifelog_id,
                            module_decision.get("action", "log")
                        )
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
                        await_sync(send_limitless_notification(embed=result["embed"]))
                        processed_successfully = True
                
                # Mark as processed after successful handling
                if processed_successfully:
                    mark_entry_processed(db, lifelog_id)
            
            time.sleep(poll_interval)

        except KeyboardInterrupt:
            print("\n🛑 Polling stopped by user.")
            break
        except Exception as e:
            print(f"❌ Polling error: {e}")
            time.sleep(poll_interval * 2)


def main():
    """Main application entry point."""
    print("=" * 60)
    print("  Personal Automation Platform")
    print("=" * 60)
    print()

    # 1. Validate environment
    validate_environment()

    # 2. Load configuration
    config = load_config()

    # 3. Initialize database
    mongodb_url = get_env("MONGODB_URL", "mongodb://localhost:27017/automation_platform")
    db = init_database(mongodb_url)

    # 4. Initialize clients
    limitless_client = LimitlessClient(get_env("LIMITLESS_API_KEY"))
    openai_client = OpenAIClient(get_env("OPENAI_API_KEY"))

    # 5. Initialize module registry
    registry = ModuleRegistry(db, openai_client, limitless_client, config)

    print("\nActive Modules:")
    for module in registry.get_all_modules():
        keywords = ", ".join(module.get_keywords()[:3])
        print(f"   • {module.get_name()}: {keywords}...")
    print()

    # 6. Initialize automation orchestrator
    orchestrator = AutomationOrchestrator(openai_client, registry)
    print("✅ Automation Orchestrator initialized")

    # 7. Start scheduler
    scheduler = Scheduler(get_env("TIMEZONE", "America/Los_Angeles"))
    scheduler.load_from_registry(registry)
    threading.Thread(target=scheduler.run, daemon=True).start()

    # 8. Start Limitless polling
    threading.Thread(
        target=polling_loop, args=(limitless_client, registry, db, orchestrator), daemon=True
    ).start()

    # 9. Setup and run Discord bot (lazy import)
    print("✅ Platform initialized — starting Discord bot...\n")
    print("=" * 60)
    print("  Platform is live!")
    print("  Press Ctrl+C to stop.")
    print("=" * 60)
    print()

    setup_bot = get_setup_bot()
    bot = setup_bot(
        token=get_env("DISCORD_BOT_TOKEN"),
        channel_id=int(get_env("DISCORD_CHANNEL_ID")),
        registry=registry,
        db=db,
        orchestrator=orchestrator,
    )

    try:
        bot.run(get_env("DISCORD_BOT_TOKEN"))
    except KeyboardInterrupt:
        print("\n👋 Shutting down gracefully...")
    except Exception as e:
        print(f"❌ FATAL ERROR: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
