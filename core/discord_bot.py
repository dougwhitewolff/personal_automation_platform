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
from typing import Dict, Callable
import asyncio


def setup_bot(token: str, channel_id: int, registry, conn):
    """
    Setup and configure Discord bot.
    
    Args:
        token: Discord bot token
        channel_id: Channel ID to monitor
        registry: Module registry for routing
        conn: Database connection
        
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
    
    @bot.event
    async def on_message(message):
        print(f"📨 on_message triggered: {message.content!r}")
        """Route messages to appropriate modules"""
        # Ignore own messages
        if message.author == bot.user:
            return
        
        # Only respond in designated channel
        if message.channel.id != channel_id:
            return
        
        # Handle images
        if message.attachments:
            await handle_attachments(message, registry, pending_confirmations)
            return
        
        content = message.content.lower()
        
        # Route to modules based on keywords
        # Check for questions
        for module in registry.modules:
            if module.matches_question(content):
                print(f"✅ Question match for module: {module.get_name()}")

                try:
                    # Diagnostic print — confirm the query is being sent
                    print(f"🧠 Sending query to {module.get_name()}.handle_query() with message: {message.content}")

                    # Call into the module
                    answer = await module.handle_query(message.content, {})

                    # Diagnostic print — confirm a response was received
                    print(f"🧠 Response received from {module.get_name()}: {answer!r}")

                    # Send the result to Discord
                    await message.channel.send(answer)

                except Exception as e:
                    print(f"❌ Error answering query: {e}")
                    await message.channel.send(f"❌ Error: {str(e)}")

                # Stop checking other modules
                return
                
        # Process commands
        await bot.process_commands(message)
    
    async def handle_attachments(message, registry, pending_confirmations):
        """Handle image attachments"""
        for attachment in message.attachments:
            if not attachment.content_type or not attachment.content_type.startswith('image/'):
                continue
            
            image_bytes = await attachment.read()
            content = message.content.lower()
            print(f"🧾 Normalized content for matching: {repr(content)}")
            
            # Determine which module should process
            matched_module = None
            for module in registry.modules:
                if module.matches_keyword(content):
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
    async def daily_summary(ctx):
        """Get today's summary from all modules"""
        from datetime import date
        
        summary_data = await registry.get_daily_summary_all(date.today())
        
        embed = discord.Embed(
            title="📅 Daily Summary",
            description=f"Summary for {date.today().strftime('%B %d, %Y')}",
            color=0x00ff00
        )
        
        for module_name, data in summary_data.items():
            if data:
                embed.add_field(
                    name=f"📊 {module_name.title()}",
                    value=data.get('summary', 'No data'),
                    inline=False
                )
        
        await ctx.send(embed=embed)
    
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
            value="`!summary` - Daily summary from all modules\n"
                  "`!help` - This message",
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
    Send notification via webhook (one-way, no bot needed).
    
    Args:
        webhook_url: Discord webhook URL
        embed_data: Embed configuration
    """
    import requests
    
    try:
        response = requests.post(webhook_url, json=embed_data)
        return response.status_code == 204
    except Exception as e:
        print(f"❌ Webhook failed: {e}")
        return False
