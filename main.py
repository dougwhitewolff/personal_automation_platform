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
from datetime import datetime
import yaml

# Import core services (lazy Discord import handled in core/__init__.py)
from core import (
    init_database,
    LimitlessClient,
    OpenAIClient,
    Scheduler,
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


def polling_loop(limitless_client, registry, conn):
    """
    Poll Limitless API for new lifelogs and dispatch them to modules.

    Each iteration:
    - Retrieves new entries
    - Detects keywords
    - Routes logs to matching modules
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

            for entry in entries:
                for module in registry.get_all_modules():
                    if module.matches_keyword(entry.get("markdown", "")):
                        try:
                            print(
                                f"🧩 DETECTED: {module.get_name()} matched for entry {entry['id']}"
                            )

                            result = await_sync(
                                module.handle_log(
                                    entry["markdown"], entry["id"], {}
                                )
                            )

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
                                f"❌ ERROR processing {module.get_name()} for entry {entry['id']}: {e}"
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

    # 6. Start scheduler
    scheduler = Scheduler(get_env("TIMEZONE", "America/Los_Angeles"))
    scheduler.load_from_registry(registry)
    threading.Thread(target=scheduler.run, daemon=True).start()

    # 7. Start Limitless polling
    threading.Thread(
        target=polling_loop, args=(limitless_client, registry, conn), daemon=True
    ).start()

    # 8. Setup and run Discord bot (lazy import)
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
