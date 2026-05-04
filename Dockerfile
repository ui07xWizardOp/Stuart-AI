FROM python:3.12-slim

# Set environment variables for headless execution
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HEADLESS_MODE=True \
    DEBIAN_FRONTEND=noninteractive

# Set the working directory
WORKDIR /app

# Install system dependencies (needed for psycopg2, etc.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy the headless requirements file
COPY requirements-headless.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application codebase
COPY . /app/

# Ensure necessary runtime directories exist
RUN mkdir -p /app/database /app/data /app/logs /app/.stuart_checkpoints

# Expose port for FastAPI backend (if running API instead of just Telegram bot)
EXPOSE 8000

# Default command to run the CLI Agent in headless/Telegram mode
CMD ["python", "cli_agent.py"]
