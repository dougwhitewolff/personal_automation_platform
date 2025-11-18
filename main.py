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
from utils.logger import get_logger

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

# Global reference to Discord bot's event loop (for thread-safe notifications)
_discord_bot_loop = None
_discord_bot_loop_lock = threading.Lock()

def set_discord_channel(channel):
    """Set the Discord channel for Limitless notifications"""
    global _discord_channel
    with _discord_channel_lock:
        _discord_channel = channel
        print(f'🔧 DEBUG: Channel set in set_discord_channel: {_discord_channel is not None}')

def set_discord_bot_loop(loop):
    """Set the Discord bot's event loop for thread-safe notifications"""
    global _discord_bot_loop
    with _discord_bot_loop_lock:
        _discord_bot_loop = loop
        print(f'🔧 DEBUG: Bot event loop registered: {_discord_bot_loop is not None}')


def _create_embeds_from_long_content(content: str, title: str = None, color: int = 0x0099ff, max_length: int = 4096):
    """
    Create one or more Discord embeds from content that may exceed Discord's limits.
    
    Args:
        content: Content to put in embed description
        title: Title for the embed(s)
        color: Color for the embed(s)
        max_length: Maximum length for embed description (default 4096)
        
    Returns:
        List of discord.Embed objects
    """
    import discord
    
    if len(content) <= max_length:
        # Short enough for a single embed
        embed = discord.Embed(
            title=title,
            description=content,
            color=color
        )
        return [embed]
    
    # Too long, split into multiple embeds
    embeds = []
    chunks = []
    current_chunk = ""
    
    # Try to split by double newlines first (paragraphs)
    paragraphs = content.split("\n\n")
    
    for paragraph in paragraphs:
        # If adding this paragraph would exceed limit, save current chunk and start new one
        if len(current_chunk) + len(paragraph) + 2 > max_length:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = paragraph
        else:
            if current_chunk:
                current_chunk += "\n\n" + paragraph
            else:
                current_chunk = paragraph
    
    # Add the last chunk
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    # If still too long, split by sentences
    if not chunks or any(len(chunk) > max_length for chunk in chunks):
        chunks = []
        sentences = content.split(". ")
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 2 > max_length:
                if current_chunk:
                    chunks.append(current_chunk.strip() + ".")
                current_chunk = sentence
            else:
                if current_chunk:
                    current_chunk += ". " + sentence
                else:
                    current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk.strip() + ("." if not current_chunk.endswith(".") else ""))
    
    # Create embeds for each chunk
    for i, chunk in enumerate(chunks):
        chunk_title = title
        if len(chunks) > 1:
            chunk_title = f"{title} (Part {i + 1}/{len(chunks)})" if title else f"Part {i + 1}/{len(chunks)}"
        
        embed = discord.Embed(
            title=chunk_title,
            description=chunk,
            color=color
        )
        embeds.append(embed)
    
    return embeds


async def _send_notification_async(embed=None, content=None):
    """
    Internal async function to send notification.
    This runs in the bot's event loop.
    """
    global _discord_channel, _discord_channel_lock
    
    # Try to get channel immediately
    channel = None
    with _discord_channel_lock:
        channel = _discord_channel
    
    # If channel not set, wait up to 5 seconds for bot to connect
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
        # Channel still not available
        with _discord_channel_lock:
            current_value = _discord_channel
        print(f"⚠️  Discord channel not available yet (bot may still be connecting). Notification will be skipped.")
        print(f"🔧 DEBUG: Channel value is: {current_value} (type: {type(current_value).__name__})")
        return False

def send_limitless_notification(embed=None, content=None):
    """
    Send notification from Limitless polling loop via Discord bot.
    
    This function can be called from any thread. It automatically detects if it's
    being called from the bot's event loop or from another thread (like the polling loop),
    and handles it appropriately.
    
    Returns:
        bool: True if notification was sent successfully, False otherwise
    """
    global _discord_bot_loop, _discord_bot_loop_lock
    
    # Check if we're in the bot's event loop
    try:
        current_loop = asyncio.get_running_loop()
        with _discord_bot_loop_lock:
            bot_loop = _discord_bot_loop
        
        # If we're in the bot's loop, we can await directly
        if bot_loop and current_loop is bot_loop:
            # We're in the bot's event loop - use await directly
            # But this function is sync, so we need to handle it differently
            # Actually, if we're in an async context in the bot's loop, we should use the async version
            # For now, let's use the thread-safe method for consistency
            pass
    except RuntimeError:
        # No running loop - we're in a sync context
        pass
    
    # Get the bot's event loop
    with _discord_bot_loop_lock:
        bot_loop = _discord_bot_loop
    
    if bot_loop:
        # Schedule the coroutine on the bot's event loop from this thread
        future = asyncio.run_coroutine_threadsafe(
            _send_notification_async(embed=embed, content=content),
            bot_loop
        )
        try:
            # Wait for the result (with timeout)
            return future.result(timeout=10.0)
        except Exception as e:
            print(f"❌ Failed to send Discord notification (thread-safe): {e}")
            import traceback
            traceback.print_exc()
            return False
    else:
        # Bot loop not available yet - try using await_sync as fallback
        print("⚠️  Bot event loop not available, using fallback method")
        return await_sync(_send_notification_async(embed=embed, content=content))


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
    
    logger = get_logger("polling")
    poll_interval = int(get_env("POLL_INTERVAL", "10"))  # Default 10 seconds
    timezone = get_env("TIMEZONE", "America/Los_Angeles")
    
    logger.info(f"Limitless polling started (every {poll_interval}s, semantic search, timezone: {timezone})")
    logger.info("Notifications will be sent when Discord bot is ready (automatic retry)")
    
    while True:
        try:
            # Search semantically for "log that" or summary requests
            # API returns entries in descending order (newest first), limit 3
            logger.debug("Searching Limitless API for new entries...")
            entries = limitless_client.search_lifelogs(
                query="log that or summary request",
                limit=3,
                timezone=timezone,
                direction="desc"
            )
            
            if not entries:
                # No matching entries - continue polling
                logger.debug("No new entries found")
                time.sleep(poll_interval)
                continue
            
            logger.info(f"Found {len(entries)} entry/entries from semantic search")
            
            # Process each entry
            for entry in entries:
                lifelog_id = entry.get("id")
                markdown = entry.get("markdown", "")
                
                # Log full markdown for all entries found
                logger.info("=" * 80)
                logger.info(f"ENTRY FOUND - ID: {lifelog_id}")
                logger.info("=" * 80)
                logger.info("FULL MARKDOWN:")
                logger.info("-" * 80)
                logger.info(markdown)
                logger.info("-" * 80)
                
                # Check if already processed
                if is_entry_processed(db, lifelog_id):
                    logger.info(f"⏭️  SKIPPING: Entry {lifelog_id} already processed")
                    logger.info("=" * 80)
                    continue
                
                logger.info(f"🔄 PROCESSING: Entry {lifelog_id} (length: {len(markdown)} chars)")
                logger.info("=" * 80)
                
                # Route via orchestrator - pass entry markdown directly (API provides full context)
                logger.debug(f"Routing entry {lifelog_id} via orchestrator")
                routing_decision = orchestrator.route_intent(
                    transcript=markdown,
                    source="limitless",
                    context={"lifelog_id": lifelog_id}
                )
                
                # Handle routing decision
                if routing_decision.get("error"):
                    logger.error(f"Orchestrator error for entry {lifelog_id}: {routing_decision['error']}")
                    import discord
                    error_embed = discord.Embed(
                        title="❌ Routing Error",
                        description=f"Failed to route entry: {routing_decision['error']}",
                        color=0xFF0000
                    )
                    await_sync(send_limitless_notification(embed=error_embed))
                    mark_entry_processed(db, lifelog_id)  # Mark as processed even on error
                    continue
                
                # Handle RAG queries (needs data from records)
                if routing_decision.get("needs_rag"):
                    logger.info(f"RAG query detected for entry {lifelog_id}")
                    # Use the RAG query if provided by LLM, otherwise use original markdown
                    rag_query = routing_decision.get("rag_query") or markdown
                    logger.debug(f"Answering RAG query: {rag_query[:100]}...")
                    answer = orchestrator.answer_query_with_rag(rag_query)
                    logger.info(f"✓ RAG query answered (response length: {len(answer)} chars)")
                    
                    import discord
                    # Split long answers into multiple embeds if needed
                    embeds = _create_embeds_from_long_content(answer, title="💬 Answer", color=0x0099ff)
                    for embed in embeds:
                        send_limitless_notification(embed=embed)
                    mark_entry_processed(db, lifelog_id)
                    continue
                
                # Handle summary requests
                if routing_decision.get("summary_request"):
                    # Orchestrator already returns timezone-aware date, but provide fallback
                    target_date = routing_decision.get("summary_date")
                    if target_date is None:
                        # Fallback: get today from registry's timezone
                        import pytz
                        tz = pytz.timezone(timezone)
                        target_date = datetime.now(tz).date()
                    logger.info(f"Summary request detected for {target_date.isoformat()}")
                    
                    from core.discord_bot import get_summary_for_date
                    summary_embed = await_sync(get_summary_for_date(registry, target_date, channel=None))
                    
                    if summary_embed:
                        send_limitless_notification(embed=summary_embed)
                    
                    mark_entry_processed(db, lifelog_id)
                    continue
                
                # Handle out of scope
                if routing_decision.get("out_of_scope") or not routing_decision.get("modules"):
                    logger.info(f"Entry {lifelog_id} is out of scope or no modules matched")
                    import discord
                    info_embed = discord.Embed(
                        title="ℹ️ No Action Taken",
                        description=f"Entry detected but no matching modules found.\n\nReasoning: {routing_decision.get('reasoning', 'Unknown')}",
                        color=0xFFFF00
                    )
                    send_limitless_notification(embed=info_embed)
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
                        logger.warning(f"Module '{module_name}' not found in registry")
                        return None
                    
                    if confidence < 0.7:
                        logger.warning(f"Skipping {module_name} due to low confidence ({confidence:.2f})")
                        return None
                    
                    try:
                        logger.info(f"Routing to {module_name} ({action}, confidence: {confidence:.2f}) for entry {entry_id}")
                        
                        if action == "log":
                            result = await module.handle_log(entry_markdown, entry_id, {})
                        elif action == "query":
                            # Queries are now handled by RAG via orchestrator
                            # This should not be reached if orchestrator is working correctly
                            logger.warning(f"Query action detected but should use RAG - skipping module query")
                            return None
                        else:
                            logger.warning(f"Unknown action: {action}")
                            return None
                        
                        logger.info(f"✓ Successfully processed {module_name} for entry {entry_id}")
                        return {"module_name": module_name, "result": result}
                    
                    except Exception as e:
                        logger.error(f"Error processing {module_name} for entry {entry_id}: {e}", exc_info=True)
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
                        send_limitless_notification(embed=result["embed"])
                        processed_successfully = True
                
                # Mark as processed after successful handling
                if processed_successfully:
                    logger.info(f"✓ Entry {lifelog_id} processed successfully, marking as processed")
                    mark_entry_processed(db, lifelog_id)
                else:
                    logger.warning(f"No successful module results for entry {lifelog_id}, not marking as processed")
            
            time.sleep(poll_interval)

        except KeyboardInterrupt:
            logger.info("Polling stopped by user")
            break
        except Exception as e:
            logger.error(f"Polling error: {e}", exc_info=True)
            time.sleep(poll_interval * 2)


def main():
    """Main application entry point."""
    logger = get_logger("main")
    
    print("=" * 60)
    print("  Personal Automation Platform")
    print("=" * 60)
    print()

    # 1. Validate environment
    logger.info("Validating environment variables...")
    validate_environment()
    logger.info("✓ Environment validation passed")

    # 2. Load configuration
    logger.info("Loading configuration...")
    config = load_config()
    logger.info("✓ Configuration loaded")

    # 3. Initialize database
    logger.info("Initializing database...")
    mongodb_url = get_env("MONGODB_URL", "mongodb://localhost:27017/automation_platform")
    db = init_database(mongodb_url)
    logger.info(f"✓ Database initialized: {mongodb_url}")

    # 4. Initialize clients
    logger.info("Initializing API clients...")
    limitless_client = LimitlessClient(get_env("LIMITLESS_API_KEY"))
    openai_client = OpenAIClient(get_env("OPENAI_API_KEY"))
    logger.info("✓ API clients initialized")

    # 5. Initialize RAG service (before registry so modules can use it)
    logger.info("Initializing RAG service...")
    rag_service = None
    try:
        from core.rag_service import RAGService
        pinecone_api_key = get_env("PINECONE_API_KEY")
        if pinecone_api_key:
            rag_service = RAGService(
                pinecone_api_key=pinecone_api_key,
                openai_api_key=get_env("OPENAI_API_KEY"),
                index_name=get_env("PINECONE_INDEX_NAME", "rag-chunks"),
                namespace=get_env("PINECONE_NAMESPACE", "default")
            )
            logger.info("✓ RAG Service initialized with Pinecone")
        else:
            logger.warning("PINECONE_API_KEY not set, RAG service disabled")
            logger.warning("Vectorization will be skipped, but logging will continue.")
    except Exception as e:
        logger.error(f"RAG Service initialization failed: {e}", exc_info=True)
        logger.warning("Vectorization will be skipped, but logging will continue.")

    # 6. Initialize module registry (with rag_service for automatic vectorization)
    logger.info("Initializing module registry...")
    timezone = get_env("TIMEZONE", "America/Los_Angeles")
    registry = ModuleRegistry(db, openai_client, limitless_client, config, timezone=timezone, rag_service=rag_service)

    logger.info("Active Modules:")
    for module in registry.get_all_modules():
        keywords = ", ".join(module.get_keywords()[:3])
        logger.info(f"  • {module.get_name()}: {keywords}...")
    
    # 7. Initialize automation orchestrator
    logger.info("Initializing automation orchestrator...")
    orchestrator = AutomationOrchestrator(openai_client, registry, rag_service=rag_service, timezone=timezone)
    logger.info("✓ Automation Orchestrator initialized")

    # 8. Start scheduler
    logger.info("Starting scheduler...")
    scheduler = Scheduler(get_env("TIMEZONE", "America/Los_Angeles"))
    scheduler.load_from_registry(registry)
    threading.Thread(target=scheduler.run, daemon=True).start()
    logger.info("✓ Scheduler started")

    # 9. Start Limitless polling
    logger.info("Starting Limitless polling thread...")
    threading.Thread(
        target=polling_loop, args=(limitless_client, registry, db, orchestrator), daemon=True
    ).start()
    logger.info("✓ Polling thread started")

    # 10. Setup and run Discord bot (lazy import)
    logger.info("Platform initialized — starting Discord bot...")
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
        logger.info("Starting Discord bot...")
        bot.run(get_env("DISCORD_BOT_TOKEN"))
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
    except Exception as e:
        logger.critical(f"FATAL ERROR: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
