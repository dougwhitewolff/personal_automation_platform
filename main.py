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
import re

# Import core services (lazy Discord import handled in core/__init__.py)
from core import (
    init_database,
    LimitlessClient,
    OpenAIClient,
    Scheduler,
    AutomationOrchestrator,
    get_setup_bot,   # Lazy import function for Discord bot
)
from core.database import get_last_processed_time, update_last_processed_time
from core.env_loader import get_env, validate_required_vars
from modules import ModuleRegistry


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
    import asyncio
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def is_log_that_command(text: str) -> bool:
    """
    Detect canonical "Log that" trigger phrase in text.
    
    Checks for variants like "log that", "track that", "log this", etc.
    Case-insensitive matching.
    
    Args:
        text: Text to check for trigger phrase
        
    Returns:
        True if "log that" variant is detected
    """
    if not text:
        return False
    
    # Pattern matches: log/track + that/this/it
    pattern = r'\b(log|track)\s+(that|this|it)\b'
    return bool(re.search(pattern, text, re.IGNORECASE))


def polling_loop(limitless_client, registry, conn, orchestrator):
    """
    Poll Limitless API for new lifelogs and dispatch them to modules.

    Each iteration:
    - Retrieves new entries
    - Detects "Log that" trigger phrase
    - Routes to orchestrator for semantic routing
    - Processes selected modules
    - Updates last processed time
    """
    poll_interval = int(get_env("POLL_INTERVAL", "2"))
    timezone = get_env("TIMEZONE", "America/Los_Angeles")

    print(f"✅ Limitless polling started (every {poll_interval}s, timezone: {timezone})")

    while True:
        try:
            last_time = get_last_processed_time(conn)
            entries = limitless_client.poll_recent_entries(
                start_time=last_time, limit=10, timezone=timezone
            )

            if not entries:
                time.sleep(poll_interval)
                continue

            newest_entry = entries[0]
            update_last_processed_time(
                conn, newest_entry["endTime"], newest_entry["id"]
            )

            # Process entries with index tracking for context building
            for idx, entry in enumerate(entries):
                markdown = entry.get("markdown", "")
                
                # Step 1: Check for "Log that" first to build context before routing
                if is_log_that_command(markdown):
                    print(f"🔍 'Log that' detected in entry {entry['id']}")
                    
                    # Build context transcript BEFORE routing (so orchestrator has full context)
                    # Entries are in reverse chronological order (newest first), so we need to reverse
                    # to get chronological order (oldest to newest) for context
                    start_idx = max(0, idx - 4)  # Get up to 5 entries (current + 4 preceding)
                    context_entries = entries[start_idx:idx + 1]
                    # Reverse to get chronological order (oldest to newest)
                    context_entries = list(reversed(context_entries))
                    # Build context transcript by joining markdown entries
                    context_transcript = "\n\n".join([
                        e.get("markdown", "") for e in context_entries if e.get("markdown")
                    ])
                    
                    # Step 2: Route via orchestrator WITH context transcript (for better routing decisions)
                    routing_decision = orchestrator.route_intent(
                        transcript=context_transcript,  # Pass full context, not just single entry
                        source="limitless",
                        context={"lifelog_id": entry["id"]}
                    )
                else:
                    # For non-"Log that" entries, check for summary requests (single entry is fine)
                    routing_decision = orchestrator.route_intent(
                        transcript=markdown,
                        source="limitless",
                        context={"lifelog_id": entry["id"]}
                    )
                    
                    # Handle summary requests (don't require "Log that")
                    if routing_decision.get("summary_request"):
                        target_date = routing_decision.get("summary_date", date.today())
                        print(f"📊 Summary request detected for {target_date.isoformat()} in entry {entry['id']}")
                        
                        # Get summary and send to Discord
                        from core.discord_bot import get_summary_for_date
                        summary_embed = await_sync(get_summary_for_date(registry, target_date, channel=None))
                        
                        if summary_embed:
                            from core.discord_bot import send_webhook_notification
                            webhook_url = get_env("DISCORD_WEBHOOK_URL")
                            if webhook_url:
                                send_webhook_notification(
                                    webhook_url,
                                    {"embeds": [summary_embed.to_dict()]},
                                )
                        continue
                    
                    # Skip entries without "Log that" (unless it was a summary request)
                    continue
                
                # Step 4: Handle routing decision
                if routing_decision.get("error"):
                    print(f"⚠️  Orchestrator error: {routing_decision['error']}")
                    # Send error notification to Discord
                    from core.discord_bot import send_webhook_notification
                    webhook_url = get_env("DISCORD_WEBHOOK_URL")
                    if webhook_url:
                        import discord
                        error_embed = discord.Embed(
                            title="❌ Routing Error",
                            description=f"Failed to route entry: {routing_decision['error']}",
                            color=0xFF0000
                        )
                        send_webhook_notification(
                            webhook_url,
                            {"embeds": [error_embed.to_dict()]},
                        )
                    continue
                
                if routing_decision.get("out_of_scope") or not routing_decision.get("modules"):
                    print(f"ℹ️  Entry {entry['id']} is out of scope or no modules matched")
                    # Send notification that nothing was logged
                    from core.discord_bot import send_webhook_notification
                    webhook_url = get_env("DISCORD_WEBHOOK_URL")
                    if webhook_url:
                        import discord
                        info_embed = discord.Embed(
                            title="ℹ️ No Action Taken",
                            description=f"Entry detected but no matching modules found.\n\nReasoning: {routing_decision.get('reasoning', 'Unknown')}",
                            color=0xFFFF00
                        )
                        send_webhook_notification(
                            webhook_url,
                            {"embeds": [info_embed.to_dict()]},
                        )
                    continue
                
                # Step 5: Process each selected module
                for module_decision in routing_decision["modules"]:
                    module_name = module_decision["name"]
                    action = module_decision["action"]
                    confidence = module_decision.get("confidence", 0.8)
                    
                    # Find module in registry
                    module = None
                    for mod in registry.get_all_modules():
                        if mod.get_name() == module_name:
                            module = mod
                            break
                    
                    if not module:
                        print(f"⚠️  Module '{module_name}' not found in registry")
                        continue
                    
                    # Only process if confidence is high enough
                    if confidence < 0.7:
                        print(f"⚠️  Skipping {module_name} due to low confidence ({confidence:.2f})")
                        continue
                    
                    try:
                        print(
                            f"🧩 ROUTING: {module_name} ({action}, confidence: {confidence:.2f}) "
                            f"for entry {entry['id']}"
                        )
                        
                        # Execute appropriate action
                        # Pass context_transcript instead of just markdown
                        if action == "log":
                            result = await_sync(
                                module.handle_log(
                                    context_transcript, entry["id"], {}
                                )
                            )
                        elif action == "query":
                            # For queries, we'd typically need a question, but in "log that" context
                            # it's usually a log action. Handle as log for now.
                            result = await_sync(
                                module.handle_log(
                                    context_transcript, entry["id"], {}
                                )
                            )
                        else:
                            print(f"⚠️  Unknown action: {action}")
                            continue
                        
                        # Send Discord notification
                        if result and result.get("embed"):
                            from core.discord_bot import send_webhook_notification
                            webhook_url = get_env("DISCORD_WEBHOOK_URL")
                            if webhook_url:
                                send_webhook_notification(
                                    webhook_url,
                                    {"embeds": [result["embed"].to_dict()]},
                                )
                    
                    except Exception as e:
                        print(
                            f"❌ ERROR processing {module_name} for entry {entry['id']}: {e}"
                        )
                        import traceback
                        traceback.print_exc()

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
    db_path = get_env("DATABASE_PATH", "./nutrition_tracker.db")
    conn = init_database(db_path)

    # 4. Initialize clients
    limitless_client = LimitlessClient(get_env("LIMITLESS_API_KEY"))
    openai_client = OpenAIClient(get_env("OPENAI_API_KEY"))

    # 5. Initialize module registry
    registry = ModuleRegistry(conn, openai_client, limitless_client, config)

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
        target=polling_loop, args=(limitless_client, registry, conn, orchestrator), daemon=True
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
        conn=conn,
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
