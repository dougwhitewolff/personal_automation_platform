"""
Discord bot setup and event handlers.

Handles:
- Message routing to modules
- Image processing
- Command handling
- Reaction-based confirmations
"""

import discord
from discord.ext import commands
from typing import Dict, Callable, Optional, List
import asyncio
from datetime import date, datetime, timedelta
import pytz
from utils.logger import get_logger


async def send_long_message(channel, content: str, max_length: int = 2000):
    """
    Send a message that may exceed Discord's character limit.
    Splits into multiple messages or uses an embed if needed.
    
    Args:
        channel: Discord channel to send to
        content: Message content to send
        max_length: Maximum length for plain messages (default 2000)
    """
    if len(content) <= max_length:
        # Short enough for a plain message
        await channel.send(content)
        return
    
    # Too long for plain message, use embed
    # Discord embed description limit is 4096 characters
    if len(content) <= 4096:
        embed = discord.Embed(
            description=content,
            color=0x0099ff
        )
        await channel.send(embed=embed)
        return
    
    # Even too long for embed description, split into multiple embeds
    # Split at paragraph boundaries when possible
    chunks = []
    current_chunk = ""
    
    # Try to split by double newlines first (paragraphs)
    paragraphs = content.split("\n\n")
    
    for paragraph in paragraphs:
        # If adding this paragraph would exceed limit, save current chunk and start new one
        if len(current_chunk) + len(paragraph) + 2 > 4096:
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
    if not chunks or any(len(chunk) > 4096 for chunk in chunks):
        chunks = []
        sentences = content.split(". ")
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 2 > 4096:
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
    
    # Send each chunk as an embed
    for i, chunk in enumerate(chunks):
        embed = discord.Embed(
            description=chunk,
            color=0x0099ff
        )
        if len(chunks) > 1:
            embed.set_footer(text=f"Part {i + 1} of {len(chunks)}")
        await channel.send(embed=embed)


async def get_summary_for_date(registry, target_date: date, channel=None):
    """
    Helper function to get and format summary for a specific date.
    Can be called from commands or orchestrator.
    
    Args:
        registry: ModuleRegistry instance
        target_date: Date to get summary for
        channel: Optional Discord channel to send embed to (if None, returns embed dict)
        
    Returns:
        Discord embed if channel is None, otherwise None (sends to channel)
    """
    summary_data = await registry.get_daily_summary_all(target_date)
    
    embed = discord.Embed(
        title="📅 Daily Summary",
        description=f"Summary for {target_date.strftime('%B %d, %Y')}",
        color=0x00ff00
    )
    
    for module_name, data in summary_data.items():
        if data and not data.get('error'):
            # Build detailed summary text
            summary_text = data.get('summary', 'No data')
            
            # Add emoji prefix based on module type
            emoji_map = {
                'nutrition': '🍽️',
                'workout': '🏋️',
                'sleep': '💤',
                'health': '🏥'
            }
            emoji = emoji_map.get(module_name, '📊')
            
            embed.add_field(
                name=f"{emoji} {module_name.title()}",
                value=summary_text,
                inline=False
            )
    
    if channel:
        await channel.send(embed=embed)
        return None
    else:
        return embed


def setup_bot(token: str, channel_id: int, registry, db, orchestrator=None):
    """
    Setup and configure Discord bot.
    
    Args:
        token: Discord bot token
        channel_id: Channel ID to monitor
        registry: Module registry for routing
        db: MongoDB database instance
        orchestrator: AutomationOrchestrator instance for semantic routing
        
    Returns:
        Configured bot instance
    """
    intents = discord.Intents.default()
    intents.message_content = True

    # Disable default help command to allow custom version
    bot = commands.Bot(command_prefix='!', intents=intents, help_command=None)
    
    # Store pending confirmations (for image analysis)
    pending_confirmations = {}
    # Store pending module selections (for image routing)
    pending_module_selections = {}
    # Store pending delete confirmations
    pending_delete_confirmations = {}
    
    @bot.event
    async def on_ready():
        print(f'✅ Discord bot connected as {bot.user}')
        # Set channel for Limitless notifications
        from main import set_discord_channel, set_discord_bot_loop
        channel = bot.get_channel(channel_id)
        if channel:
            set_discord_channel(channel)
            print(f'✅ Discord channel set for Limitless notifications')
        
        # Store the bot's event loop for thread-safe notifications
        set_discord_bot_loop(bot.loop)
        print(f'✅ Discord bot event loop registered for thread-safe notifications')
        
        # Send online message to channel
        if channel:
            try:
                # Use configured timezone for timestamp
                # Get UTC time first, then convert to configured timezone
                from datetime import timezone as tz_utc
                tz = pytz.timezone(registry.timezone)
                utc_now = datetime.now(tz_utc.utc)
                configured_time = utc_now.astimezone(tz)
                embed = discord.Embed(
                    title="🤖 Bot Online",
                    description="Personal Automation Platform is now online and ready!",
                    color=0x00ff00,
                    timestamp=configured_time
                )
                embed.add_field(
                    name="Status",
                    value="✅ All systems operational",
                    inline=False
                )
                await channel.send(embed=embed)
                print(f'✅ Sent online message to channel')
            except Exception as e:
                print(f'⚠️  Failed to send online message: {e}')
    
    @bot.event
    async def on_message(message):
        print(f"📨 on_message triggered: {message.content!r}")
        """Route messages to appropriate modules using orchestrator"""
        # Ignore own messages
        if message.author == bot.user:
            return
        
        # Only respond in designated channel
        if message.channel.id != channel_id:
            return
        
        # Handle images
        if message.attachments:
            await handle_attachments(message, registry, pending_confirmations, orchestrator)
            return
        
        content = message.content.strip()
        
        if not content:
            return
        
        # Skip orchestrator for Discord commands (messages starting with "!")
        # Commands are handled by bot.process_commands() at the end
        if content.startswith('!'):
            await bot.process_commands(message)
            return
        
        # Use orchestrator for semantic routing if available
        if orchestrator:
            try:
                # Show typing indicator during routing
                async with message.channel.typing():
                    # Route via orchestrator
                    routing_decision = orchestrator.route_intent(
                        transcript=content,
                        source="discord",
                        context={"message_id": str(message.id)}
                    )
                
                # Log orchestrator routing decision details
                logger = get_logger("discord_bot")
                logger.info("=" * 80)
                logger.info("ORCHESTRATOR ROUTING DECISION (Discord):")
                logger.info("-" * 80)
                logger.info(f"Message: {content[:100]}{'...' if len(content) > 100 else ''}")
                logger.info(f"Reasoning: {routing_decision.get('reasoning', 'N/A')}")
                
                modules = routing_decision.get("modules", [])
                if modules:
                    logger.info(f"Modules Selected: {len(modules)}")
                    for i, module in enumerate(modules, 1):
                        logger.info(f"  {i}. {module.get('name', 'unknown')} - Action: {module.get('action', 'unknown')}, Confidence: {module.get('confidence', 0):.2f}")
                        if module.get('reasoning'):
                            logger.info(f"     Reasoning: {module.get('reasoning')}")
                else:
                    logger.info("Modules Selected: NONE (no module calls made)")
                
                if routing_decision.get("summary_request"):
                    logger.info(f"Summary Request: YES (Date: {routing_decision.get('summary_date', 'N/A')})")
                else:
                    logger.info("Summary Request: NO")
                
                if routing_decision.get("needs_rag"):
                    logger.info(f"RAG Query: YES (Query: {routing_decision.get('rag_query', 'N/A')[:100]}...)")
                else:
                    logger.info("RAG Query: NO")
                
                if routing_decision.get("out_of_scope"):
                    logger.info("Out of Scope: YES")
                else:
                    logger.info("Out of Scope: NO")
                
                if routing_decision.get("direct_answer"):
                    logger.info(f"Direct Answer: YES (Length: {len(routing_decision.get('direct_answer', ''))} chars)")
                else:
                    logger.info("Direct Answer: NO")
                
                if routing_decision.get("error"):
                    logger.warning(f"Error: {routing_decision.get('error')}")
                
                logger.info("-" * 80)
                logger.info("=" * 80)
                
                # Handle routing decision
                if routing_decision.get("error"):
                    await message.channel.send(
                        f"❌ Error routing message: {routing_decision['error']}"
                    )
                    return
                
                # Check for summary request
                if routing_decision.get("summary_request"):
                    # Use orchestrator's parsed date, or fallback to today in configured timezone
                    target_date = routing_decision.get("summary_date")
                    if target_date is None:
                        target_date = get_today_in_timezone()
                    async with message.channel.typing():
                        await get_summary_for_date(registry, target_date, message.channel)
                    return
                
                # Check for RAG query (needs data from records)
                if routing_decision.get("needs_rag"):
                    async with message.channel.typing():
                        # Use the RAG query if provided by LLM, otherwise use original content
                        rag_query = routing_decision.get("rag_query") or content
                        answer = orchestrator.answer_query_with_rag(rag_query)
                        await send_long_message(message.channel, answer)
                    return
                
                # Check for direct answer (in-scope but no module routing)
                if routing_decision.get("direct_answer"):
                    await message.channel.send(routing_decision["direct_answer"])
                    return
                
                if routing_decision.get("out_of_scope"):
                    # Out of scope - send polite refusal
                    await message.channel.send(
                        "I'm sorry, but I can only help with personal automation tasks like "
                        "nutrition tracking, workout logging, and related questions. "
                        "I can't answer general questions outside my scope."
                    )
                    return
                
                modules_to_process = routing_decision.get("modules", [])
                
                if not modules_to_process:
                    await message.channel.send(
                        "I couldn't determine which module should handle your message. "
                        "Please try rephrasing or be more specific."
                    )
                    return
                
                # Process modules in parallel if multiple are selected
                async def process_module(module_decision, content, message_id):
                    """Process a single module and return result"""
                    module_name = module_decision["name"]
                    action = module_decision["action"]
                    confidence = module_decision.get("confidence", 0.8)
                    
                    # Find module in registry
                    module = None
                    for mod in registry.modules:
                        if mod.get_name() == module_name:
                            module = mod
                            break
                    
                    if not module:
                        return None
                    
                    # Only process if confidence is high enough
                    if confidence < 0.7:
                        return None
                    
                    try:
                        if action == "query":
                            # Queries are now handled by RAG via orchestrator
                            # This should not be reached if orchestrator is working correctly
                            print(f"⚠️  Query action detected but should use RAG - skipping module query")
                            return None
                        
                        elif action == "log":
                            # Handle as log command
                            print(f"📝 Routing log to {module_name} (confidence: {confidence:.2f})")
                            result = await module.handle_log(
                                content,
                                f"discord_{message_id}",
                                {}
                            )
                            return {"type": "log", "module_name": module_name, "result": result}
                    
                    except Exception as e:
                        print(f"❌ Error processing {module_name}: {e}")
                        import traceback
                        traceback.print_exc()
                        return {"type": "error", "module_name": module_name, "error": str(e)}
                
                # Show typing indicator while processing
                async with message.channel.typing():
                    # Process all modules in parallel
                    if len(modules_to_process) > 1:
                        # Multiple modules - process in parallel
                        tasks = [
                            process_module(module_decision, content, message.id)
                            for module_decision in modules_to_process
                        ]
                        results = await asyncio.gather(*tasks, return_exceptions=True)
                    else:
                        # Single module - process normally
                        results = [await process_module(modules_to_process[0], content, message.id)]
                
                # Log module processing results and extracted information
                logger.info("=" * 80)
                logger.info("MODULE PROCESSING RESULTS (Discord):")
                logger.info("-" * 80)
                for i, result in enumerate(results, 1):
                    if result is None:
                        logger.info(f"{i}. Module result: None")
                        continue
                    
                    if isinstance(result, Exception):
                        logger.error(f"{i}. Module result: Exception - {str(result)}")
                        continue
                    
                    module_name = result.get("module_name", "unknown")
                    if result.get("type") == "error":
                        logger.warning(f"{i}. {module_name}: ERROR - {result.get('error', 'Unknown error')}")
                    elif result.get("type") == "log":
                        module_result = result.get("result", {})
                        logged_items = module_result.get("logged_items", [])
                        
                        logger.info(f"{i}. {module_name}: SUCCESS")
                        if logged_items:
                            logger.info(f"   Extracted Information ({len(logged_items)} items):")
                            for item in logged_items:
                                logger.info(f"     • {item}")
                        else:
                            # Try to get information from embed if available
                            embed = module_result.get("embed")
                            if embed:
                                title = getattr(embed, 'title', 'N/A')
                                description = getattr(embed, 'description', 'N/A')
                                logger.info(f"   Extracted Information (from embed):")
                                logger.info(f"     • Title: {title}")
                                if description:
                                    logger.info(f"     • Description: {description[:200]}{'...' if len(description) > 200 else ''}")
                            else:
                                message_text = module_result.get("message", "")
                                if message_text:
                                    logger.info(f"   Extracted Information (from message):")
                                    logger.info(f"     • {message_text[:200]}{'...' if len(message_text) > 200 else ''}")
                                else:
                                    logger.info(f"   Extracted Information: None (no logged_items, embed, or message found)")
                    elif result.get("type") == "query":
                        logger.info(f"{i}. {module_name}: QUERY - {result.get('answer', 'N/A')[:100]}...")
                
                logger.info("-" * 80)
                logger.info("=" * 80)
                
                # Send all results
                for result in results:
                    if result is None:
                        continue
                    
                    if isinstance(result, Exception):
                        await message.channel.send(
                            f"❌ Error processing module: {str(result)}"
                        )
                        continue
                    
                    if result.get("type") == "error":
                        await message.channel.send(
                            f"❌ Error processing with {result['module_name']} module: {result['error']}"
                        )
                    elif result.get("type") == "query":
                        await message.channel.send(result["answer"])
                    elif result.get("type") == "log":
                        if result["result"] and result["result"].get("embed"):
                            await message.channel.send(embed=result["result"]["embed"])
                        elif result["result"] and result["result"].get("message"):
                            await message.channel.send(result["result"]["message"])
                
                return  # Don't process commands if orchestrator handled it
                
            except Exception as e:
                print(f"❌ Orchestrator error: {e}")
                import traceback
                traceback.print_exc()
                # Fall through to keyword matching fallback
        
        # Fallback to keyword matching if orchestrator unavailable or failed
        content_lower = content.lower()
        
        # Check for questions
        for module in registry.modules:
            if module.matches_question(content_lower):
                print(f"✅ Question match for module: {module.get_name()} (fallback)")

                try:
                    async with message.channel.typing():
                        answer = await module.handle_query(content, {})
                    await message.channel.send(answer)
                except Exception as e:
                    print(f"❌ Error answering query: {e}")
                    await message.channel.send(f"❌ Error: {str(e)}")

                return
                
        # Process commands
        await bot.process_commands(message)
    
    async def handle_attachments(message, registry, pending_confirmations, orchestrator=None):
        """Handle image attachments"""
        for attachment in message.attachments:
            if not attachment.content_type or not attachment.content_type.startswith('image/'):
                continue
            
            image_bytes = await attachment.read()
            content = message.content or ""
            print(f"🧾 Processing image with content: {repr(content)}")
            
            # Determine which module should process using orchestrator if available
            matched_module = None
            
            if orchestrator and content.strip():
                try:
                    routing_decision = orchestrator.route_intent(
                        transcript=content,
                        source="discord",
                        context={"has_image": True}
                    )
                    
                    if not routing_decision.get("out_of_scope") and routing_decision.get("modules"):
                        # Get highest confidence module
                        best_module_decision = max(
                            routing_decision["modules"],
                            key=lambda m: m.get("confidence", 0)
                        )
                        
                        module_name = best_module_decision["name"]
                        for module in registry.modules:
                            if module.get_name() == module_name:
                                matched_module = module
                                break
                except Exception as e:
                    print(f"⚠️  Orchestrator error for image: {e}")
            
            # Fallback to keyword matching
            if not matched_module:
                content_lower = content.lower()
                for module in registry.modules:
                    if module.matches_keyword(content_lower):
                        matched_module = module
                        break
            
            if not matched_module:
                # Ask user
                msg = await message.channel.send(
                    "I see an image! Which module should process it?\n"
                    + "\n".join([f"{i+1}. {mod.get_name()}" 
                                for i, mod in enumerate(registry.modules)])
                )
                # Add reaction options
                number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
                for i in range(len(registry.modules)):
                    await msg.add_reaction(number_emojis[i])
                
                # Store pending module selection
                pending_module_selections[msg.id] = {
                    'image_bytes': image_bytes,
                    'original_message': message,
                    'modules': registry.modules
                }
                return
            
            try:
                result = await matched_module.handle_image(image_bytes, message.content)
                
                if result.get('needs_confirmation'):
                    # Send for user confirmation
                    embed = result['embed']
                    msg = await message.channel.send(embed=embed)
                    await msg.add_reaction('✅')
                    await msg.add_reaction('❌')
                    
                    # Store pending confirmation
                    pending_confirmations[msg.id] = {
                        'module': matched_module,
                        'data': result['data'],
                        'original_message': message
                    }
                else:
                    # Auto-confirmed
                    await message.channel.send(embed=result.get('embed'))
                    await message.add_reaction('✅')
                    
            except Exception as e:
                print(f"❌ Error processing image: {e}")
                await message.channel.send(f"❌ Error: {str(e)}")
    
    @bot.event
    async def on_reaction_add(reaction, user):
        """Handle confirmation reactions and module selection reactions"""
        if user.bot:
            return
        
        message_id = reaction.message.id
        
        # Check for module selection (number emojis)
        number_emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣"]
        if message_id in pending_module_selections:
            selection = pending_module_selections[message_id]
            emoji_str = str(reaction.emoji)
            
            if emoji_str in number_emojis:
                # Get selected module index
                module_index = number_emojis.index(emoji_str)
                modules = selection['modules']
                
                if module_index < len(modules):
                    selected_module = modules[module_index]
                    image_bytes = selection['image_bytes']
                    original_message = selection['original_message']
                    channel = reaction.message.channel
                    
                    # Remove the selection message
                    try:
                        await reaction.message.delete()
                    except:
                        pass
                    
                    # Process image with selected module
                    try:
                        async with channel.typing():
                            result = await selected_module.handle_image(
                                image_bytes, 
                                original_message.content or ""
                            )
                        
                        if result.get('needs_confirmation'):
                            # Send for user confirmation
                            embed = result['embed']
                            msg = await channel.send(embed=embed)
                            await msg.add_reaction('✅')
                            await msg.add_reaction('❌')
                            
                            # Store pending confirmation
                            pending_confirmations[msg.id] = {
                                'module': selected_module,
                                'data': result['data'],
                                'original_message': original_message
                            }
                        else:
                            # Auto-confirmed
                            await channel.send(embed=result.get('embed'))
                            await original_message.add_reaction('✅')
                        
                        # Clean up
                        del pending_module_selections[message_id]
                        
                    except Exception as e:
                        print(f"❌ Error processing image with {selected_module.get_name()}: {e}")
                        import traceback
                        traceback.print_exc()
                        await channel.send(f"❌ Error: {str(e)}")
                        del pending_module_selections[message_id]
            
            return
        
        # Check for delete confirmations first
        if message_id in pending_delete_confirmations:
            delete_conf = pending_delete_confirmations[message_id]
            ctx = delete_conf['ctx']
            
            if str(reaction.emoji) == '✅':
                # Confirmed - execute deletion
                try:
                    async with ctx.channel.typing():
                        # Get RAG service if available
                        rag_service = None
                        if orchestrator and hasattr(orchestrator, 'rag_service'):
                            rag_service = orchestrator.rag_service
                        
                        if delete_conf['type'] == 'table_all':
                            # Delete all records from table
                            result = await delete_records(
                                delete_conf['table_name'],
                                {},
                                rag_service
                            )
                            if result['success']:
                                embed = discord.Embed(
                                    title="✅ Deletion Complete",
                                    description=result['message'],
                                    color=0x00ff00
                                )
                            else:
                                embed = discord.Embed(
                                    title="❌ Deletion Failed",
                                    description=result['message'],
                                    color=0xff0000
                                )
                            await ctx.send(embed=embed)
                        
                        elif delete_conf['type'] == 'table_date':
                            # Delete records from table for specific date
                            result = await delete_records(
                                delete_conf['table_name'],
                                {"date": delete_conf['date'].isoformat()},
                                rag_service
                            )
                            if result['success']:
                                embed = discord.Embed(
                                    title="✅ Deletion Complete",
                                    description=result['message'],
                                    color=0x00ff00
                                )
                            else:
                                embed = discord.Embed(
                                    title="❌ Deletion Failed",
                                    description=result['message'],
                                    color=0xff0000
                                )
                            await ctx.send(embed=embed)
                        
                        elif delete_conf['type'] == 'table_item_date':
                            # Delete records by item name for a specific date
                            import re
                            field_name = delete_conf['field_name']
                            item_name = delete_conf['item_name']
                            target_date = delete_conf['date']
                            query = {
                                field_name: {"$regex": f"^{re.escape(item_name)}$", "$options": "i"},
                                "date": target_date.isoformat()
                            }
                            
                            result = await delete_records(
                                delete_conf['table_name'],
                                query,
                                rag_service
                            )
                            if result['success']:
                                embed = discord.Embed(
                                    title="✅ Deletion Complete",
                                    description=result['message'],
                                    color=0x00ff00
                                )
                            else:
                                embed = discord.Embed(
                                    title="❌ Deletion Failed",
                                    description=result['message'],
                                    color=0xff0000
                                )
                            await ctx.send(embed=embed)
                        
                        elif delete_conf['type'] == 'date_all':
                            # Delete all records for all tables on a date
                            collections = get_available_collections()
                            total_deleted = 0
                            results = []
                            
                            for table_name in collections:
                                result = await delete_records(
                                    table_name,
                                    {"date": delete_conf['date'].isoformat()},
                                    rag_service
                                )
                                if result['success'] and result['deleted_count'] > 0:
                                    total_deleted += result['deleted_count']
                                    results.append(f"• `{table_name}`: {result['deleted_count']} record(s)")
                            
                            if total_deleted > 0:
                                embed = discord.Embed(
                                    title="✅ Deletion Complete",
                                    description=(
                                        f"Successfully deleted **{total_deleted}** record(s) "
                                        f"for {delete_conf['date'].strftime('%B %d, %Y')}.\n\n"
                                        f"**Breakdown:**\n" + "\n".join(results)
                                    ),
                                    color=0x00ff00
                                )
                            else:
                                embed = discord.Embed(
                                    title="ℹ️ No Records Found",
                                    description=f"No records found to delete for {delete_conf['date'].isoformat()}",
                                    color=0x0099ff
                                )
                            await ctx.send(embed=embed)
                    
                    del pending_delete_confirmations[message_id]
                    
                except Exception as e:
                    await ctx.send(f"❌ Error during deletion: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    del pending_delete_confirmations[message_id]
            
            elif str(reaction.emoji) == '❌':
                # Cancelled
                await ctx.send("❌ Deletion cancelled.")
                del pending_delete_confirmations[message_id]
            
            return
        
        # Check for confirmation reactions (image processing)
        if message_id not in pending_confirmations:
            return
        
        confirmation = pending_confirmations[message_id]
        module = confirmation['module']
        
        if str(reaction.emoji) == '✅':
            # Confirmed - process the data
            try:
                result = await module.handle_log(
                    "",
                    f"discord_img_{message_id}",
                    confirmation['data']
                )
                
                await reaction.message.channel.send(embed=result.get('embed'))
                del pending_confirmations[message_id]
                
            except Exception as e:
                await reaction.message.channel.send(f"❌ Error: {str(e)}")
        
        elif str(reaction.emoji) == '❌':
            # Cancelled
            await reaction.message.channel.send("❌ Cancelled.")
            del pending_confirmations[message_id]
    
    # Helper function to get today in registry's timezone
    def get_today_in_timezone():
        """Get today's date in the registry's configured timezone."""
        tz = pytz.timezone(registry.timezone)
        now_tz = datetime.now(tz)
        return now_tz.date()
    
    # Commands
    @bot.command(name='summary')
    async def daily_summary(ctx, date_str: str = None):
        """Get summary from all modules for a specific date or today
        
        Usage:
        !summary - Today's summary
        !summary 2024-01-15 - Specific date
        !summary yesterday - Yesterday's summary
        !summary today - Today's summary
        """
        from datetime import date, datetime, timedelta
        
        # Get today in configured timezone
        today = get_today_in_timezone()
        
        # Parse date if provided
        if date_str:
            date_str_lower = date_str.lower().strip()
            try:
                if date_str_lower == "yesterday":
                    target_date = today - timedelta(days=1)
                elif date_str_lower == "today":
                    target_date = today
                else:
                    # Try parsing various date formats
                    try:
                        target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                    except ValueError:
                        try:
                            target_date = datetime.strptime(date_str, "%Y/%m/%d").date()
                        except ValueError:
                            target_date = datetime.strptime(date_str, "%m/%d/%Y").date()
            except (ValueError, AttributeError):
                await ctx.send("❌ Invalid date format. Use YYYY-MM-DD, 'today', or 'yesterday'")
                return
        else:
            target_date = today
        
        async with ctx.channel.typing():
            await get_summary_for_date(registry, target_date, ctx.channel)
    
    @bot.command(name='list')
    async def list_command(ctx, *, args: str = None):
        """
        List logs from a table.
        
        Usage:
        !list food [date] - List food logs (defaults to today)
        !list exercise [date] - List exercise logs (defaults to today)
        !list sleep [date] - List sleep logs (defaults to today)
        !list health [date] - List health logs (defaults to today)
        !list hydration [date] - List hydration logs (defaults to today)
        !list table <table_name> [date <date>] - List logs from any table
        
        Examples:
        !list food - Today's food logs
        !list food yesterday - Yesterday's food logs
        !list food 2024-01-15 - Food logs for specific date
        !list table food_logs - Recent food logs (all dates)
        !list table exercise_logs date 2024-01-15
        """
        if not args:
            embed = discord.Embed(
                title="❌ List Command Usage",
                description="Please specify what to list. Use `!help list` for examples.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            return
        
        parts = args.split()
        
        # Map shortcuts to table names
        shortcut_map = {
            "food": "food_logs",
            "exercise": "exercise_logs",
            "workout": "exercise_logs",
            "sleep": "sleep_logs",
            "health": "daily_health",
            "hydration": "hydration_logs",
            "water": "hydration_logs",
            "wellness": "wellness_scores"
        }
        
        table_name = None
        target_date = None
        
        # Check if first part is a shortcut
        first_part = parts[0].lower()
        if first_part in shortcut_map:
            # Shortcut format: !list food [date]
            table_name = shortcut_map[first_part]
            # Default to today if no date specified
            if len(parts) == 1:
                target_date = get_today_in_timezone()
            else:
                # Date is provided
                date_str = " ".join(parts[1:])
                try:
                    target_date = parse_date_string(date_str)
                except (ValueError, AttributeError):
                    await ctx.send("❌ Invalid date format. Use YYYY-MM-DD, 'today', or 'yesterday'")
                    return
        elif len(parts) >= 2 and parts[0].lower() == "table":
            # Full format: !list table <table_name> [date <date>]
            table_name = parts[1]
            collections = get_available_collections()
            
            if table_name not in collections:
                await ctx.send(
                    f"❌ Invalid table name: `{table_name}`\n"
                    f"Available tables: {', '.join(collections)}"
                )
                return
            
            # Parse date if provided
            if len(parts) >= 4 and parts[2].lower() == "date":
                date_str = " ".join(parts[3:])
                try:
                    target_date = parse_date_string(date_str)
                except (ValueError, AttributeError):
                    await ctx.send("❌ Invalid date format. Use YYYY-MM-DD, 'today', or 'yesterday'")
                    return
        else:
            await ctx.send(
                "❌ Invalid format.\n\n"
                "**Shortcuts:**\n"
                "• `!list food` - Today's food logs\n"
                "• `!list food yesterday` - Yesterday's food logs\n"
                "• `!list exercise` - Today's exercise logs\n\n"
                "**Full format:**\n"
                "• `!list table <table_name> [date <date>]`\n\n"
                "Use `!help list` for more examples."
            )
            return
        
        if not table_name:
            await ctx.send("❌ Could not determine table name. Use `!help list` for usage.")
            return
        
        # Query the collection
        collection = db[table_name]
        query = {}
        if target_date:
            query["date"] = target_date.isoformat()
        
        # Get records (limit to 50 for display)
        records = list(collection.find(query).sort("date", -1).sort("timestamp", -1).limit(50))
        
        if not records:
            date_str = f" for {target_date.isoformat()}" if target_date else ""
            await ctx.send(f"✅ No records found in `{table_name}`{date_str}")
            return
        
        # Format records for display
        # Create a friendly title based on table name
        title_map = {
            "food_logs": "🍽️ Food Logs",
            "exercise_logs": "🏋️ Exercise Logs",
            "sleep_logs": "💤 Sleep Logs",
            "daily_health": "🏥 Health Logs",
            "hydration_logs": "💧 Hydration Logs",
            "wellness_scores": "😊 Wellness Scores",
            "training_days": "📅 Training Days"
        }
        title = title_map.get(table_name, f"📋 Logs from `{table_name}`")
        
        # Format date for description
        if target_date:
            date_desc = target_date.strftime('%B %d, %Y')
            if target_date == get_today_in_timezone():
                date_desc = "Today"
            elif target_date == get_today_in_timezone() - timedelta(days=1):
                date_desc = "Yesterday"
        else:
            date_desc = "All dates"
        
        embed = discord.Embed(
            title=title,
            description=f"Showing {len(records)} record(s) for {date_desc}",
            color=0x0099ff
        )
        
        # Format records based on table type
        formatted_records = []
        for i, record in enumerate(records[:20], 1):  # Limit to 20 for embed
            record_date = record.get("date", "Unknown")
            record_time = record.get("timestamp", "")
            if record_time:
                try:
                    # Extract time from timestamp
                    if isinstance(record_time, str):
                        time_part = record_time.split("T")[1].split(".")[0] if "T" in record_time else ""
                    else:
                        time_part = str(record_time)
                except:
                    time_part = ""
            else:
                time_part = ""
            
            if table_name == "food_logs":
                item = record.get("item", "Unknown")
                calories = record.get("calories", 0)
                protein = record.get("protein_g", 0)
                formatted_records.append(
                    f"**{i}.** `{item}` - {calories} cal, {protein}g protein ({record_date}" + 
                    (f" {time_part[:5]}" if time_part else "") + ")"
                )
            elif table_name == "exercise_logs":
                ex_type = record.get("exercise_type", "Unknown")
                duration = record.get("duration_minutes", 0)
                calories = record.get("calories_burned", 0)
                formatted_records.append(
                    f"**{i}.** `{ex_type}` - {duration} min, {calories} cal ({record_date}" +
                    (f" {time_part[:5]}" if time_part else "") + ")"
                )
            elif table_name == "hydration_logs":
                amount = record.get("amount_oz", 0)
                formatted_records.append(
                    f"**{i}.** {amount} oz ({record_date}" +
                    (f" {time_part[:5]}" if time_part else "") + ")"
                )
            elif table_name == "sleep_logs":
                hours = record.get("hours", 0)
                score = record.get("sleep_score")
                quality = record.get("quality_notes", "")
                score_str = f", score: {score}" if score else ""
                quality_str = f", {quality}" if quality else ""
                formatted_records.append(
                    f"**{i}.** {hours} hours{score_str}{quality_str} ({record_date})"
                )
            elif table_name == "daily_health":
                weight = record.get("weight_lbs")
                bm = record.get("bowel_movements", 0)
                electrolytes = record.get("electrolytes_taken")
                parts = []
                if weight:
                    parts.append(f"Weight: {weight} lbs")
                if bm > 0:
                    parts.append(f"BM: {bm}")
                if electrolytes is not None:
                    parts.append(f"Electrolytes: {'Yes' if electrolytes else 'No'}")
                formatted_records.append(
                    f"**{i}.** {', '.join(parts) if parts else 'Health markers'} ({record_date})"
                )
            elif table_name == "wellness_scores":
                mood = record.get("mood")
                energy = record.get("energy")
                stress = record.get("stress")
                parts = []
                if mood:
                    parts.append(f"Mood: {mood}")
                if energy:
                    parts.append(f"Energy: {energy}")
                if stress:
                    parts.append(f"Stress: {stress}")
                formatted_records.append(
                    f"**{i}.** {', '.join(parts) if parts else 'Wellness scores'} ({record_date})"
                )
            else:
                # Generic format
                formatted_records.append(f"**{i}.** {str(record)[:100]} ({record_date})")
        
        # Split into chunks if too long (Discord embed field limit is 1024 chars)
        if formatted_records:
            # Join all records
            all_text = "\n".join(formatted_records)
            
            # If too long, split into multiple fields
            if len(all_text) > 1024:
                # Split into chunks
                chunks = []
                current_chunk = ""
                for record in formatted_records:
                    if len(current_chunk) + len(record) + 1 > 1024:
                        chunks.append(current_chunk)
                        current_chunk = record
                    else:
                        if current_chunk:
                            current_chunk += "\n" + record
                        else:
                            current_chunk = record
                if current_chunk:
                    chunks.append(current_chunk)
                
                for i, chunk in enumerate(chunks[:5], 1):  # Max 5 fields
                    embed.add_field(
                        name=f"Records (Part {i})" if len(chunks) > 1 else "Records",
                        value=chunk,
                        inline=False
                    )
            else:
                embed.add_field(
                    name="Records",
                    value=all_text,
                    inline=False
                )
        
        if len(records) > 20:
            embed.set_footer(text=f"Showing first 20 of {len(records)} records. Use date filter to narrow results.")
        
        await ctx.send(embed=embed)
    
    def parse_date_string(date_str: str) -> date:
        """Parse date string into date object"""
        from datetime import timedelta
        today = get_today_in_timezone()
        date_str_lower = date_str.lower().strip()
        
        if date_str_lower == "yesterday":
            return today - timedelta(days=1)
        elif date_str_lower == "today":
            return today
        elif date_str_lower == "tomorrow":
            return today + timedelta(days=1)
        else:
            # Try parsing various date formats
            try:
                return datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                try:
                    return datetime.strptime(date_str, "%Y/%m/%d").date()
                except ValueError:
                    return datetime.strptime(date_str, "%m/%d/%Y").date()
    
    def get_available_collections() -> List[str]:
        """Get list of available log collections"""
        # Core log collections (excluding system collections)
        collections = [
            "food_logs",
            "hydration_logs",
            "wellness_scores",
            "sleep_logs",
            "daily_health",
            "exercise_logs",
            "training_days"
        ]
        return collections
    
    def _format_record_preview(table_name: str, record: Dict) -> str:
        """Format a record for display in delete confirmation"""
        if table_name == "food_logs":
            item = record.get("item", "Unknown")
            calories = record.get("calories", 0)
            return f"{item} ({calories} cal)"
        elif table_name == "exercise_logs":
            ex_type = record.get("exercise_type", "Unknown")
            duration = record.get("duration_minutes", 0)
            return f"{ex_type} ({duration} min)"
        elif table_name == "hydration_logs":
            amount = record.get("amount_oz", 0)
            return f"{amount} oz"
        elif table_name == "sleep_logs":
            hours = record.get("hours", 0)
            return f"{hours} hours"
        elif table_name == "daily_health":
            weight = record.get("weight_lbs")
            bm = record.get("bowel_movements", 0)
            parts = []
            if weight:
                parts.append(f"Weight: {weight} lbs")
            if bm > 0:
                parts.append(f"BM: {bm}")
            return ", ".join(parts) if parts else "Health markers"
        else:
            return str(record)[:100]
    
    async def delete_records(collection_name: str, filter_query: Dict, rag_service=None) -> Dict:
        """
        Delete records from a collection and clean up RAG vectors if needed.
        
        Args:
            collection_name: Name of the collection
            filter_query: MongoDB filter query
            rag_service: Optional RAG service for vector cleanup
            
        Returns:
            Dict with deletion results
        """
        try:
            collection = db[collection_name]
            
            # Find records to be deleted (for RAG cleanup)
            records_to_delete = list(collection.find(filter_query))
            count = len(records_to_delete)
            
            if count == 0:
                return {"success": True, "deleted_count": 0, "message": "No records found to delete"}
            
            # Delete from MongoDB
            result = collection.delete_many(filter_query)
            deleted_count = result.deleted_count
            
            # Clean up RAG vectors if service is available
            if rag_service and deleted_count > 0:
                for record in records_to_delete:
                    record_id = str(record.get("_id", ""))
                    if record_id:
                        try:
                            rag_service.delete_documents_by_source_id(record_id, collection_name)
                        except Exception as e:
                            print(f"⚠️  Warning: Failed to delete RAG vectors for {collection_name}/{record_id}: {e}")
            
            return {
                "success": True,
                "deleted_count": deleted_count,
                "message": f"Successfully deleted {deleted_count} record(s) from {collection_name}"
            }
        except Exception as e:
            return {
                "success": False,
                "deleted_count": 0,
                "message": f"Error deleting from {collection_name}: {str(e)}"
            }
    
    @bot.command(name='delete')
    async def delete_command(ctx, *, args: str = None):
        """
        Delete logs from the database.
        
        Usage:
        !delete food <item_name> - Delete food item from today's log
        !delete food <item_name> <date> - Delete food item from specific date
        !delete exercise <item_name> - Delete exercise from today's log
        !delete table <table_name> date <date> - Delete all logs for a table on a specific date
        !delete table <table_name> all - Delete all logs for a table
        !delete date <date> - Delete all logs for all tables on a specific date
        
        Examples:
        !delete food smoothie - Delete smoothie from today
        !delete food smoothie yesterday - Delete smoothie from yesterday
        !delete exercise cycling - Delete cycling workout from today
        !delete table food_logs date 2024-01-15
        !delete table sleep_logs all
        
        Tip: Use !list food first to see available items!
        """
        if not args:
            embed = discord.Embed(
                title="❌ Delete Command Usage",
                description="Please specify what to delete. Use `!help delete` for examples.",
                color=0xff0000
            )
            await ctx.send(embed=embed)
            return
        
        args_lower = args.lower().strip()
        parts = args.split()
        
        # Get RAG service if available
        rag_service = None
        if orchestrator and hasattr(orchestrator, 'rag_service'):
            rag_service = orchestrator.rag_service
        
        # Map shortcuts to table names and field names
        shortcut_map = {
            "food": {"table": "food_logs", "field": "item"},
            "exercise": {"table": "exercise_logs", "field": "exercise_type"},
            "workout": {"table": "exercise_logs", "field": "exercise_type"}
        }
        
        # Parse command
        try:
            # Check if first part is a shortcut (food, exercise, etc.)
            first_part = parts[0].lower()
            if first_part in shortcut_map:
                # Shortcut format: !delete food <item_name> [date]
                table_info = shortcut_map[first_part]
                table_name = table_info["table"]
                field_name = table_info["field"]
                
                if len(parts) < 2:
                    await ctx.send(
                        f"❌ Please specify an item name. Usage: `!delete {first_part} <item_name> [date]`\n"
                        f"Example: `!delete {first_part} smoothie` or `!delete {first_part} smoothie yesterday`"
                    )
                    return
                
                # Get item name (could be multiple words)
                # Check if last part looks like a date
                item_parts = parts[1:]
                target_date = get_today_in_timezone()  # Default to today
                
                # Try to parse last part as date
                if len(item_parts) > 1:
                    # Check if last part is a date keyword or date format
                    last_part = item_parts[-1].lower()
                    if last_part in ["today", "yesterday", "tomorrow"] or \
                       any(c.isdigit() for c in last_part):  # Looks like a date
                        try:
                            target_date = parse_date_string(item_parts[-1])
                            item_name = " ".join(item_parts[:-1])  # Everything except last part
                        except (ValueError, AttributeError):
                            # Not a valid date, treat as part of item name
                            item_name = " ".join(item_parts)
                    else:
                        item_name = " ".join(item_parts)
                else:
                    item_name = item_parts[0]
                
                # Check if records exist (case-insensitive search, for today by default)
                collection = db[table_name]
                import re
                query = {
                    field_name: {"$regex": f"^{re.escape(item_name)}$", "$options": "i"},
                    "date": target_date.isoformat()
                }
                
                records = list(collection.find(query))
                
                if not records:
                    date_str = "today" if target_date == get_today_in_timezone() else target_date.isoformat()
                    await ctx.send(
                        f"❌ No records found with item name `{item_name}` in `{table_name}` for {date_str}.\n"
                        f"Use `!list {first_part}` to see available items."
                    )
                    return
                
                # Show matching records and ask for confirmation
                if len(records) == 1:
                    record = records[0]
                    preview = _format_record_preview(table_name, record)
                    
                    embed = discord.Embed(
                        title="⚠️ Confirm Deletion",
                        description=(
                            f"You are about to delete a record from `{table_name}`.\n\n"
                            f"**Item:** `{item_name}`\n"
                            f"**Date:** {target_date.isoformat()}\n"
                            f"**Details:** {preview}\n\n"
                            f"This action **CANNOT** be undone!\n\n"
                            f"React with ✅ to confirm or ❌ to cancel."
                        ),
                        color=0xff9900
                    )
                else:
                    # Multiple records found
                    embed = discord.Embed(
                        title="⚠️ Confirm Deletion",
                        description=(
                            f"You are about to delete **{len(records)}** record(s) from `{table_name}` "
                            f"with item name `{item_name}` for {target_date.isoformat()}.\n\n"
                            f"This action **CANNOT** be undone!\n\n"
                            f"React with ✅ to confirm or ❌ to cancel."
                        ),
                        color=0xff9900
                    )
                
                msg = await ctx.send(embed=embed)
                await msg.add_reaction('✅')
                await msg.add_reaction('❌')
                
                pending_delete_confirmations[msg.id] = {
                    'type': 'table_item_date',
                    'table_name': table_name,
                    'item_name': item_name,
                    'field_name': field_name,
                    'date': target_date,
                    'ctx': ctx
                }
                return
            
            # Continue with existing table-based commands
            if len(parts) >= 2 and parts[0].lower() == "table" and parts[1].lower() == "all":
                # Delete all logs for a table
                if len(parts) < 3:
                    await ctx.send("❌ Please specify a table name. Usage: `!delete table <table_name> all`")
                    return
                
                table_name = parts[2]
                collections = get_available_collections()
                
                if table_name not in collections:
                    await ctx.send(
                        f"❌ Invalid table name: `{table_name}`\n"
                        f"Available tables: {', '.join(collections)}"
                    )
                    return
                
                # Confirmation required for destructive operation
                embed = discord.Embed(
                    title="⚠️ Confirm Deletion",
                    description=(
                        f"You are about to delete **ALL** logs from `{table_name}`.\n\n"
                        f"This action **CANNOT** be undone!\n\n"
                        f"React with ✅ to confirm or ❌ to cancel."
                    ),
                    color=0xff9900
                )
                msg = await ctx.send(embed=embed)
                await msg.add_reaction('✅')
                await msg.add_reaction('❌')
                
                pending_delete_confirmations[msg.id] = {
                    'type': 'table_all',
                    'table_name': table_name,
                    'ctx': ctx
                }
                return
            
            elif len(parts) >= 4 and parts[0].lower() == "table" and parts[2].lower() == "date":
                # Delete logs for a table on a specific date
                table_name = parts[1]
                date_str = " ".join(parts[3:])
                collections = get_available_collections()
                
                if table_name not in collections:
                    await ctx.send(
                        f"❌ Invalid table name: `{table_name}`\n"
                        f"Available tables: {', '.join(collections)}"
                    )
                    return
                
                try:
                    target_date = parse_date_string(date_str)
                except (ValueError, AttributeError):
                    await ctx.send("❌ Invalid date format. Use YYYY-MM-DD, 'today', or 'yesterday'")
                    return
                
                # Show what will be deleted and ask for confirmation
                collection = db[table_name]
                count = collection.count_documents({"date": target_date.isoformat()})
                
                if count == 0:
                    await ctx.send(f"✅ No records found in `{table_name}` for {target_date.isoformat()}")
                    return
                
                embed = discord.Embed(
                    title="⚠️ Confirm Deletion",
                    description=(
                        f"You are about to delete **{count}** log(s) from `{table_name}` "
                        f"for **{target_date.strftime('%B %d, %Y')}**.\n\n"
                        f"This action **CANNOT** be undone!\n\n"
                        f"React with ✅ to confirm or ❌ to cancel."
                    ),
                    color=0xff9900
                )
                msg = await ctx.send(embed=embed)
                await msg.add_reaction('✅')
                await msg.add_reaction('❌')
                
                pending_delete_confirmations[msg.id] = {
                    'type': 'table_date',
                    'table_name': table_name,
                    'date': target_date,
                    'ctx': ctx
                }
                return
            
            
            elif len(parts) >= 2 and parts[0].lower() == "date":
                # Delete all logs for all tables on a specific date
                date_str = " ".join(parts[1:])
                
                try:
                    target_date = parse_date_string(date_str)
                except (ValueError, AttributeError):
                    await ctx.send("❌ Invalid date format. Use YYYY-MM-DD, 'today', or 'yesterday'")
                    return
                
                # Count records across all collections
                collections = get_available_collections()
                total_count = 0
                counts_by_table = {}
                
                for table_name in collections:
                    collection = db[table_name]
                    count = collection.count_documents({"date": target_date.isoformat()})
                    if count > 0:
                        counts_by_table[table_name] = count
                        total_count += count
                
                if total_count == 0:
                    await ctx.send(f"✅ No records found for {target_date.isoformat()}")
                    return
                
                # Show breakdown and ask for confirmation
                breakdown = "\n".join([f"• `{table}`: {count} record(s)" for table, count in counts_by_table.items()])
                
                embed = discord.Embed(
                    title="⚠️ Confirm Deletion",
                    description=(
                        f"You are about to delete **{total_count}** log(s) across all tables "
                        f"for **{target_date.strftime('%B %d, %Y')}**.\n\n"
                        f"**Breakdown:**\n{breakdown}\n\n"
                        f"This action **CANNOT** be undone!\n\n"
                        f"React with ✅ to confirm or ❌ to cancel."
                    ),
                    color=0xff9900
                )
                msg = await ctx.send(embed=embed)
                await msg.add_reaction('✅')
                await msg.add_reaction('❌')
                
                pending_delete_confirmations[msg.id] = {
                    'type': 'date_all',
                    'date': target_date,
                    'ctx': ctx
                }
                return
            
            else:
                await ctx.send(
                    "❌ Invalid delete command format.\n\n"
                    "**Usage:**\n"
                "• `!delete food <item_name>` - Delete food item from today's log\n"
                "• `!delete food <item_name> <date>` - Delete food item from specific date\n"
                "• `!delete exercise <item_name>` - Delete exercise from today's log\n"
                "• `!delete table <table_name> date <date>` - Delete all logs for a table on a date\n"
                "• `!delete table <table_name> all` - Delete all logs for a table\n"
                "• `!delete date <date>` - Delete all logs for all tables on a date\n\n"
                "**Examples:**\n"
                "• `!delete food smoothie` - Delete smoothie from today\n"
                "• `!delete food smoothie yesterday` - Delete smoothie from yesterday\n"
                "• `!delete exercise cycling` - Delete cycling workout from today\n"
                "• `!delete table food_logs date 2024-01-15`\n"
                "• `!delete table sleep_logs all`\n\n"
                "**Tip:** Use `!list food` first to see available items!"
                )
                return
        
        except Exception as e:
            await ctx.send(f"❌ Error parsing delete command: {str(e)}")
            import traceback
            traceback.print_exc()
    
    @bot.command(name='help')
    async def help_command(ctx, command: str = None):
        """Show available commands and modules"""
        if command and command.lower() == "list":
            embed = discord.Embed(
                title="📋 List Command Help",
                description="List logs from a table to see what's available",
                color=0x0099ff
            )
            embed.add_field(
                name="Shortcuts (defaults to today)",
                value=(
                    "`!list food` - Today's food logs\n"
                    "`!list food yesterday` - Yesterday's food logs\n"
                    "`!list exercise` - Today's exercise logs\n"
                    "`!list sleep` - Today's sleep logs\n"
                    "`!list health` - Today's health logs\n"
                    "`!list hydration` - Today's hydration logs"
                ),
                inline=False
            )
            embed.add_field(
                name="Full Format",
                value=(
                    "`!list table <table_name>` - List recent logs from a table\n"
                    "`!list table <table_name> date <date>` - List logs for a specific date"
                ),
                inline=False
            )
            embed.add_field(
                name="Examples",
                value=(
                    "`!list food` - Today's food\n"
                    "`!list food 2024-01-15` - Food for specific date\n"
                    "`!list table food_logs` - All recent food logs\n"
                    "`!list exercise yesterday` - Yesterday's workouts"
                ),
                inline=False
            )
            embed.add_field(
                name="Available Tables",
                value="`food_logs`, `hydration_logs`, `wellness_scores`, `sleep_logs`, `daily_health`, `exercise_logs`, `training_days`",
                inline=False
            )
            embed.add_field(
                name="Date Formats",
                value="`YYYY-MM-DD`, `today`, `yesterday`, `tomorrow`",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        if command and command.lower() == "delete":
            embed = discord.Embed(
                title="🗑️ Delete Command Help",
                description="Delete logs from the database",
                color=0x0099ff
            )
            embed.add_field(
                name="Shortcuts (defaults to today)",
                value=(
                    "`!delete food <item_name>` - Delete food item from today's log\n"
                    "`!delete food <item_name> <date>` - Delete food item from specific date\n"
                    "`!delete exercise <item_name>` - Delete exercise from today's log\n"
                    "`!delete exercise <item_name> <date>` - Delete exercise from specific date"
                ),
                inline=False
            )
            embed.add_field(
                name="Full Format",
                value=(
                    "`!delete table <table_name> date <date>` - Delete all logs for a table on a date\n"
                    "`!delete table <table_name> all` - Delete all logs for a table\n"
                    "`!delete date <date>` - Delete all logs for all tables on a date"
                ),
                inline=False
            )
            embed.add_field(
                name="Examples",
                value=(
                    "`!delete food smoothie` - Delete smoothie from today\n"
                    "`!delete food smoothie yesterday` - Delete smoothie from yesterday\n"
                    "`!delete exercise cycling` - Delete cycling workout from today\n"
                    "`!delete table food_logs date 2024-01-15`\n"
                    "`!delete table sleep_logs all`"
                ),
                inline=False
            )
            embed.add_field(
                name="Available Tables",
                value="`food_logs`, `hydration_logs`, `wellness_scores`, `sleep_logs`, `daily_health`, `exercise_logs`, `training_days`",
                inline=False
            )
            embed.add_field(
                name="Date Formats",
                value="`YYYY-MM-DD`, `today`, `yesterday`, `tomorrow`",
                inline=False
            )
            embed.add_field(
                name="Tip",
                value="Use `!list food` first to see available items!",
                inline=False
            )
            await ctx.send(embed=embed)
            return
        
        embed = discord.Embed(
            title="🤖 Bot Commands",
            description="Available commands and modules",
            color=0x0099ff
        )
        
        # Commands
        embed.add_field(
            name="Commands",
            value=(
                "`!summary` - Today's summary from all modules\n"
                "`!summary 2024-01-15` - Summary for specific date\n"
                "`!summary yesterday` - Yesterday's summary\n"
                "`!list food` - List today's food logs (use `!help list` for more)\n"
                "`!list exercise` - List today's exercise logs\n"
                "`!delete` - Delete logs (use `!help delete` for details)\n"
                "`!help` - This message\n"
                "`!help list` - List command help\n"
                "`!help delete` - Delete command help\n\n"
                "You can also ask for summaries naturally:\n"
                "- \"show me today's summary\"\n"
                "- \"what did I do yesterday?\"\n"
                "- \"summary for January 15th\""
            ),
            inline=False
        )
        
        # Active modules
        module_list = "\n".join([
            f"• **{mod.get_name()}**: {', '.join(mod.get_keywords()[:3])}"
            for mod in registry.modules
        ])
        
        embed.add_field(
            name="Active Modules",
            value=module_list,
            inline=False
        )
        
        await ctx.send(embed=embed)
    print("🧩 Discord bot setup complete — event handlers registered")

    return bot


def send_webhook_notification(webhook_url: str, embed_data: Dict = None, content: str = None):
    """
    Send notification via Discord webhook (one-way, no bot needed).
    
    Args:
        webhook_url: Discord webhook URL
        embed_data: Embed configuration dict (title, description, color, fields, etc.)
        content: Plain text content (optional, used if embed_data is None)
        
    Returns:
        bool: True if notification was sent successfully, False otherwise
    """
    import requests
    
    if not webhook_url:
        print("⚠️  No webhook URL provided")
        return False
    
    payload = {}
    
    if embed_data:
        # Build embed from dict
        embed = {
            "title": embed_data.get("title"),
            "description": embed_data.get("description"),
            "color": embed_data.get("color", 0x0099ff),
            "fields": embed_data.get("fields", []),
            "footer": embed_data.get("footer"),
            "timestamp": embed_data.get("timestamp")
        }
        # Remove None values
        embed = {k: v for k, v in embed.items() if v is not None}
        payload["embeds"] = [embed]
    elif content:
        payload["content"] = content
    else:
        print("⚠️  No content or embed_data provided")
        return False
    
    try:
        response = requests.post(webhook_url, json=payload, timeout=10)
        if response.status_code == 204:
            return True
        else:
            print(f"❌ Webhook notification failed: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Failed to send webhook notification: {e}")
        return False
