"""
Discord Bot Channel (Phase 13: Multi-Channel Access)

Provides a Discord bot interface to the Stuart agent.
Users can send messages on Discord, which are routed to the
Orchestrator, with responses sent back to the channel.

Requires DISCORD_BOT_TOKEN in .env
"""

import os
import asyncio
import threading
from typing import Optional

from observability import get_logging_system

# Check for discord library
try:
    import discord
    from discord.ext import commands
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False


class StuartDiscordBot:
    """
    Discord bot that bridges messages to the Stuart Orchestrator.
    Runs in its own thread with its own asyncio event loop.
    """

    def __init__(self, token: str, orchestrator):
        self.logger = get_logging_system()
        self.token = token
        self.orchestrator = orchestrator
        self._thread: Optional[threading.Thread] = None
        
        if not DISCORD_AVAILABLE:
            self.logger.error("discord.py not installed. Run: pip install discord.py")
            return

        self.logger.info("StuartDiscordBot initialized.")

    def start(self):
        """Start the Discord bot in a background thread."""
        if not DISCORD_AVAILABLE:
            self.logger.warning("Cannot start Discord bot — library not available.")
            return

        self._thread = threading.Thread(target=self._run_bot, daemon=True, name="discord-bot")
        self._thread.start()
        self.logger.info("Discord bot thread started.")

    def _run_bot(self):
        """Entry point for the bot thread. Creates its own event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Intents required for reading message content
        intents = discord.Intents.default()
        intents.message_content = True
        
        bot = commands.Bot(command_prefix="!", intents=intents, loop=loop)

        @bot.event
        async def on_ready():
            self.logger.info(f"Discord bot connected as {bot.user}")

        @bot.event
        async def on_message(message):
            # Ignore messages from ourselves or other bots
            if message.author.bot:
                return
            
            # Ignore messages without content (e.g. system messages)
            if not message.content.strip():
                return
                
            user_text = message.content
            channel = message.channel
            
            self.logger.info(f"Discord message from {message.author}: {user_text[:50]}...")
            
            # Send a typing indicator
            async with channel.typing():
                try:
                    # Run the orchestrator in a thread to prevent blocking the Discord event loop
                    response = await asyncio.to_thread(self.orchestrator.run, user_text)
                    
                    # Discord has a 2000 char limit per message
                    limit = 1950
                    if len(response) > limit:
                        # Split into chunks
                        for i in range(0, len(response), limit):
                            chunk = response[i:i + limit]
                            await channel.send(chunk)
                    else:
                        await channel.send(response)
                        
                except Exception as e:
                    self.logger.error(f"Discord handler error: {e}")
                    await channel.send(f"⚠️ Error processing your request: {str(e)[:200]}")

            await bot.process_commands(message)

        try:
            loop.run_until_complete(bot.start(self.token))
        except Exception as e:
            self.logger.error(f"Discord bot crashed: {e}")
        finally:
            loop.run_until_complete(bot.close())
            loop.close()

    def stop(self):
        """Stop the bot gracefully."""
        self.logger.info("Stopping Discord bot...")
        # The application will be stopped when the thread is terminated,
        # but in a more robust setup, we'd trigger bot.close() safely.
