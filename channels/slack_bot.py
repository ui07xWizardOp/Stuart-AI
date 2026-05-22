"""
Slack Bot Channel (Phase 13: Multi-Channel Access)

Provides a Slack bot interface to the Stuart agent.
Users can send DMs or mention the bot, which routes messages
to the Orchestrator and sends responses back.

Requires SLACK_BOT_TOKEN and SLACK_APP_TOKEN in .env
"""

import os
import threading
from typing import Optional

from observability import get_logging_system

# Check for slack library
try:
    from slack_sdk import WebClient
    from slack_sdk.socket_mode import SocketModeHandler
    SLACK_AVAILABLE = True
except ImportError:
    SLACK_AVAILABLE = False


class StuartSlackBot:
    """
    Slack bot using Socket Mode that bridges messages to the Stuart Orchestrator.
    Runs in its own background thread.
    """

    def __init__(self, bot_token: str, app_token: str, orchestrator):
        self.logger = get_logging_system()
        self.bot_token = bot_token
        self.app_token = app_token
        self.orchestrator = orchestrator
        self._thread: Optional[threading.Thread] = None
        self.handler: Optional[SocketModeHandler] = None
        
        if not SLACK_AVAILABLE:
            self.logger.error("slack-sdk not installed. Run: pip install slack-sdk")
            return

        self.client = WebClient(token=self.bot_token)
        self.logger.info("StuartSlackBot initialized.")

    def start(self):
        """Start the Slack bot in a background thread."""
        if not SLACK_AVAILABLE:
            self.logger.warning("Cannot start Slack bot — library not available.")
            return

        self._thread = threading.Thread(target=self._run_bot, daemon=True, name="slack-bot")
        self._thread.start()
        self.logger.info("Slack bot thread started.")

    def _run_bot(self):
        """Entry point for the bot thread. Starts Socket Mode Handler."""
        try:
            self.handler = SocketModeHandler(self.client, self.app_token)
            
            # Register event listeners
            @self.handler.event("app_mention")
            def handle_app_mention(client, req, resp):
                resp.accept()  # Acknowledge the event immediately
                event = req.payload.get("event", {})
                self._process_message(client, event)

            @self.handler.event("message")
            def handle_message(client, req, resp):
                resp.accept()  # Acknowledge the event immediately
                event = req.payload.get("event", {})
                
                # Check if it's a Direct Message (IM)
                channel_type = event.get("channel_type")
                if channel_type == "im":
                    self._process_message(client, event)

            self.logger.info("Slack Socket Mode client connecting...")
            self.handler.start()
        except Exception as e:
            self.logger.error(f"Slack bot crashed: {e}")

    def _process_message(self, client, event):
        # Ignore messages from bots (including ourselves)
        if event.get("bot_id") or event.get("subtype") == "bot_message":
            return
            
        user_text = event.get("text", "")
        channel_id = event.get("channel")
        thread_ts = event.get("thread_ts") or event.get("ts")
        user_id = event.get("user")
        
        if not user_text.strip():
            return
            
        self.logger.info(f"Slack message from user {user_id} in channel {channel_id}: {user_text[:50]}...")
        
        # In a real environment, we'd send a temporary "thinking" react or reply,
        # but let's post an ephemeral response or a simple message thread.
        # Let's reply in the same thread.
        try:
            # Run the orchestrator
            # Note: since this callback is running in a handler thread pool, blocking is acceptable.
            response = self.orchestrator.run(user_text)
            
            # Slack has a 4000 char limit per message block
            limit = 3800
            if len(response) > limit:
                for i in range(0, len(response), limit):
                    chunk = response[i:i + limit]
                    client.web_client.chat_postMessage(
                        channel=channel_id,
                        text=chunk,
                        thread_ts=thread_ts
                    )
            else:
                client.web_client.chat_postMessage(
                    channel=channel_id,
                    text=response,
                    thread_ts=thread_ts
                )
                
        except Exception as e:
            self.logger.error(f"Slack handler error: {e}")
            try:
                client.web_client.chat_postMessage(
                    channel=channel_id,
                    text=f"⚠️ Error processing your request: {str(e)[:200]}",
                    thread_ts=thread_ts
                )
            except Exception as se:
                self.logger.error(f"Failed to send Slack error response: {se}")

    def stop(self):
        """Stop the bot gracefully."""
        if self.handler:
            self.logger.info("Stopping Slack bot...")
            self.handler.close()
