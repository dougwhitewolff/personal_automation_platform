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
    
    @bot.event
    async def on_ready():
        print(f'✅ Discord bot connected as {bot.user}')
        # Set channel for Limitless notifications
        from main import set_discord_channel
        channel = bot.get_channel(channel_id)
        if channel:
            set_discord_channel(channel)
            print(f'✅ Discord channel set for Limitless notifications')
    
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
                    target_date = routing_decision.get("summary_date", date.today())
                    async with message.channel.typing():
                        await get_summary_for_date(registry, target_date, message.channel)
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
                            # Handle as question
                            print(f"🧠 Routing query to {module_name} (confidence: {confidence:.2f})")
                            answer = await module.handle_query(content, {})
                            return {"type": "query", "module_name": module_name, "answer": answer}
                        
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
                    + "\n".join([f"{i+1}️⃣ {mod.get_name()}" 
                                for i, mod in enumerate(registry.modules)])
                )
                # Add reaction options
                for i in range(len(registry.modules)):
                    await msg.add_reaction(f"{i+1}️⃣")
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
        """Handle confirmation reactions"""
        if user.bot:
            return
        
        message_id = reaction.message.id
        
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
        
        # Parse date if provided
        if date_str:
            date_str_lower = date_str.lower().strip()
            try:
                if date_str_lower == "yesterday":
                    target_date = date.today() - timedelta(days=1)
                elif date_str_lower == "today":
                    target_date = date.today()
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
            target_date = date.today()
        
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
