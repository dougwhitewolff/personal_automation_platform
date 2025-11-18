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
from typing import Dict, Callable, Optional
import asyncio
from datetime import date, datetime, timedelta
import pytz


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
            
            # Add sleep and bowel movements for nutrition module
            if module_name == 'nutrition':
                sleep = data.get('sleep', {})
                health = data.get('health', {})
                
                details = []
                if sleep.get('hours') is not None:
                    sleep_info = f"💤 Sleep: {sleep['hours']:.1f}h"
                    if sleep.get('score'):
                        sleep_info += f" (score: {sleep['score']})"
                    if sleep.get('quality'):
                        sleep_info += f" - {sleep['quality']}"
                    details.append(sleep_info)
                
                if health.get('bowel_movements', 0) > 0:
                    details.append(f"🚽 Bowel movements: {health['bowel_movements']}")
                
                if health.get('weight_lbs'):
                    details.append(f"⚖️ Weight: {health['weight_lbs']} lbs")
                
                if details:
                    summary_text += "\n" + "\n".join(details)
            
            embed.add_field(
                name=f"📊 {module_name.title()}",
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
        
        # Check for confirmation reactions
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
    
    @bot.command(name='help')
    async def help_command(ctx):
        """Show available commands and modules"""
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
                "`!help` - This message\n\n"
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


def send_webhook_notification(webhook_url: str, embed_data: Dict):
    """
    DEPRECATED: Send notification via webhook (one-way, no bot needed).
    
    This function is kept for backwards compatibility but is no longer used.
    All notifications now go through the Discord bot.
    
    Args:
        webhook_url: Discord webhook URL (unused)
        embed_data: Embed configuration (unused)
    """
    print("⚠️  send_webhook_notification is deprecated. Use bot.send() instead.")
    return False
