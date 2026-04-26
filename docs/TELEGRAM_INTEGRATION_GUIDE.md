# Telegram Integration Guide

Stuart AI includes a powerful headless communication channel via Telegram. This allows you to chat with Stuart, dispatch autonomous tasks, and receive alerts directly on your mobile device, even when you aren't at your computer.

## Setup Instructions

### 1. Register a Telegram Bot
1. Open Telegram and search for **@BotFather**.
2. Send the command `/newbot`.
3. Follow the prompts to name your bot (e.g., `Stuart_Personal_Agent`).
4. BotFather will provide an **HTTP API Token**. Keep this secure.

### 2. Configure Stuart
1. Open your `.env` file located in the root of the Stuart AI project.
2. Add your token to the configuration:
   ```ini
   TELEGRAM_BOT_TOKEN="your_token_from_botfather"
   ```

### 3. Launch the Bot
The Telegram integration runs automatically when Stuart boots in headless mode (or via the CLI). 
- **Via Docker:** `docker-compose up -d`
- **Via CLI:** `python cli_agent.py`

Once booted, you will see a log entry: `StuartTelegramBot initialized and polling...`

## Interacting with Stuart

Open Telegram and send a message to your bot.

### Supported Inputs
- **Natural Language:** "Research the latest advancements in solid-state batteries."
- **Slash Commands:** `/status`, `/sysmon`, `/note`, `/pomodoro` (See the [CLI & Commands Reference](CLI_AND_COMMANDS_REFERENCE.md) for details).

### How it Works Under the Hood
1. Messages sent via Telegram are captured by the `StuartTelegramBot` polling thread.
2. The bot wraps the user's message in a standard event and dispatches it to the `EventBus`.
3. The `Orchestrator` receives the event, processes the prompt, runs the ReAct loop, executes any necessary tools (like searching Wikipedia or executing Python), and returns the final response string.
4. The bot transmits the response back to your Telegram client.

> [!CAUTION]  
> Currently, the Telegram bot responds to anyone who messages it. For production hardening, it is highly recommended to modify `channels/telegram_bot.py` to check the `update.effective_user.id` against a hardcoded whitelist to prevent unauthorized access to your agent.
