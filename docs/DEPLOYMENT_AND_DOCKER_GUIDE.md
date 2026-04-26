# Deployment & Docker Guide

Stuart AI offers two distinct deployment modes depending on your use case: **Native Desktop** (for the stealth GUI overlay) and **Headless Docker** (for 24/7 server deployment, Telegram bot, and APIs).

## 1. Native Desktop Deployment (Windows)

Native deployment is required if you want to use Stuart's signature **Transparent Stealth Overlay** and **Global Hotkeys**. Docker containers (especially Linux-based ones) cannot hook into your host operating system's keyboard or render borderless transparent windows.

### Prerequisites
- Python 3.12+
- Windows 10/11

### Step-by-Step
1. **Clone the repository:**
   ```bash
   git clone https://github.com/ui07xWizardOp/Stuart-AI.git
   cd Stuart-AI
   ```
2. **Setup Virtual Environment:**
   ```bash
   python -m venv venv
   .\venv\Scripts\activate
   ```
3. **Install Full Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
4. **Configure Secrets:**
   Copy `.env.example` to `.env` and fill in your API keys (Groq, Cerebras, Deepgram, etc.).
5. **Launch:**
   Run the batch script to launch the GUI:
   ```cmd
   run.bat
   ```

---

## 2. Headless Docker Deployment (Server / Cloud)

Docker deployment is ideal if you want Stuart to run 24/7 on a VPS, Raspberry Pi, or NAS, acting primarily through the **Telegram Integration** or as an automated background researcher.

> [!WARNING]  
> The Docker container **does not include** the PyWebview GUI or Pynput hotkeys. It is purely a conversational and programmatic interface.

### Architecture
The `docker-compose.yml` spins up two services:
1. **stuart-agent:** The core Python logic running `cli_agent.py`.
2. **qdrant:** A dedicated vector database for long-term memory.

### Step-by-Step
1. **Configure Secrets:**
   You must create a `.env` file in the root directory. To use the headless bot effectively, ensure you have set:
   ```ini
   TELEGRAM_BOT_TOKEN="your_bot_token_here"
   # Add your LLM keys (Groq, Cerebras, etc.)
   ```
2. **Build and Run:**
   ```bash
   docker-compose up -d --build
   ```
3. **Verify Execution:**
   Check the logs to ensure the agent booted and connected to Telegram:
   ```bash
   docker logs -f stuart_core_agent
   ```

### Volume Persistence
The `docker-compose.yml` is configured to mount local directories into the container. This means:
- **Your Memory survives restarts:** Vector embeddings go to `./qdrant_storage`, and SQLite snapshots go to `./database`.
- **Your Logs are accessible:** You can read `./logs/stuart_runtime.log` directly from your host machine.

> [!TIP]
> If you make changes to `skills_registry.json` or write custom Python tools, you will need to restart the container (`docker-compose restart stuart-agent`) for the new code to load.
