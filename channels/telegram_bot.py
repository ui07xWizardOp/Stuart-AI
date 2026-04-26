"""
Telegram Bot Channel (Phase 13: Multi-Channel Access)

Provides a Telegram bot interface to the Stuart agent.
Users can send messages from Telegram, which are routed to the
Orchestrator, with responses sent back to the chat.

Requires TELEGRAM_BOT_TOKEN in .env
"""

import os
import asyncio
import threading
from typing import Optional

from observability import get_logging_system

# Check for telegram library
try:
    from telegram import Update
    from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False


class StuartTelegramBot:
    """
    Telegram bot that bridges messages to the Stuart Orchestrator.
    Runs in its own thread with its own asyncio event loop.
    """

    def __init__(self, token: str, orchestrator):
        self.logger = get_logging_system()
        self.token = token
        self.orchestrator = orchestrator
        self._thread: Optional[threading.Thread] = None
        self._app = None

        if not TELEGRAM_AVAILABLE:
            self.logger.error("python-telegram-bot not installed. Run: pip install python-telegram-bot")
            return

        self.logger.info("StuartTelegramBot initialized.")

    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        await update.message.reply_text(
            "🧠 **Stuart Agent Online**\n\n"
            "I am your Personal Cognitive Agent. "
            "Send me any message and I will process it through my reasoning engine.\n\n"
            "Commands:\n"
            "  /start — Show this message\n"
            "  /status — Agent health check\n"
            "  /telos — View my core alignment\n\n"
            "Just type naturally to interact!",
            parse_mode="Markdown"
        )

    async def _status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /status command."""
        await update.message.reply_text("🟢 Stuart Agent is online and processing.")

    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Route user messages to the Orchestrator."""
        user_text = update.message.text
        chat_id = update.effective_chat.id

        self.logger.info(f"Telegram message from chat {chat_id}: {user_text[:50]}...")

        # Send a "thinking" indicator
        await update.message.reply_text("🤔 Processing...")

        try:
            # Run the orchestrator synchronously (it's designed for sync)
            response = self.orchestrator.run(user_text)

            # Telegram has a 4096 char limit per message
            if len(response) > 4000:
                # Split into chunks
                for i in range(0, len(response), 4000):
                    chunk = response[i:i + 4000]
                    await update.message.reply_text(chunk)
            else:
                await update.message.reply_text(response)

        except Exception as e:
            self.logger.error(f"Telegram handler error: {e}")
            await update.message.reply_text(f"❌ Error processing your request: {str(e)[:200]}")

    def start(self):
        """Start the Telegram bot in a background thread."""
        if not TELEGRAM_AVAILABLE:
            self.logger.warning("Cannot start Telegram bot — library not available.")
            return

        self._thread = threading.Thread(target=self._run_bot, daemon=True, name="telegram-bot")
        self._thread.start()
        self.logger.info("Telegram bot thread started.")

    def _run_bot(self):
        """Entry point for the bot thread. Creates its own event loop."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            self._app = ApplicationBuilder().token(self.token).build()

            # Register handlers
            self._app.add_handler(CommandHandler("start", self._start_command))
            self._app.add_handler(CommandHandler("status", self._status_command))
            self._app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))

            self.logger.info("Telegram bot polling started.")
            loop.run_until_complete(self._app.run_polling(drop_pending_updates=True))
        except Exception as e:
            self.logger.error(f"Telegram bot crashed: {e}")
        finally:
            loop.close()

    def stop(self):
        """Stop the bot gracefully."""
        if self._app:
            self.logger.info("Stopping Telegram bot...")
            # The application will be stopped when the thread is terminated
