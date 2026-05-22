"""
LLM Client Wrappers (Phase 7 Dual-LLM Routing)

Provides physical HTTP execution interfaces for:
1. Ollama (Local FAST_CHEAP internal tasks)
2. OpenAI (Remote REASONING heavy codebase tasks)
"""

import os
import json
import requests
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

from observability import get_logging_system

load_dotenv()

class BaseLLMClient:
    def generate_chat(self, messages: List[Dict[str, str]], model_name: Optional[str] = None, temperature: Optional[float] = None) -> str:
        raise NotImplementedError

    def chat(self, messages: List[Dict[str, str]], model_name: Optional[str] = None, temperature: Optional[float] = None, **kwargs) -> str:
        raise NotImplementedError

class OllamaClient(BaseLLMClient):
    """
    Connects to local Ollama instance (default localhost:11434).
    Zero cost. Used for GC distillation, booleans, and workflow routing.
    """
    def __init__(self, model_name: str = "llama3:latest", host: str = "http://localhost:11434"):
        self.logger = get_logging_system()
        # Allows user to inject their preferred local model via .env
        self.model_name = os.getenv("OLLAMA_MODEL", model_name)
        self.host = host
        self.api_url = f"{self.host}/api/chat"

    def generate_chat(self, messages: List[Dict[str, str]], model_name: Optional[str] = None, temperature: Optional[float] = None) -> str:
        model = model_name or self.model_name
        temp = temperature if temperature is not None else 0.1
        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temp
            }
        }
        
        try:
            self.logger.debug(f"Routing to local Ollama ({model})...")
            response = requests.post(self.api_url, json=payload, timeout=120)
            response.raise_for_status()
            
            data = response.json()
            return data.get("message", {}).get("content", "")
            
        except requests.exceptions.ConnectionError:
            self.logger.error("Failed to connect to local Ollama. Ensure Ollama is running.")
            raise RuntimeError("OLLAMA_CONNECTION_FAILED")
        except Exception as e:
            self.logger.error(f"Ollama generation failed: {e}")
            raise

    def chat(self, messages: List[Dict[str, str]], model_name: Optional[str] = None, temperature: Optional[float] = None, **kwargs) -> str:
        return self.generate_chat(messages, model_name=model_name, temperature=temperature)

class OpenAIClient(BaseLLMClient):
    """
    Connects to OpenAI API.
    Costs money. Used for intense coding sessions and deep reasoning tasks.
    """
    def __init__(self, model_name: str = "gpt-4o"):
        self.logger = get_logging_system()
        self.model_name = model_name
        from security.vault import get_vault_secret
        self.api_key = get_vault_secret("OPENAI_API_KEY")
        
        if not self.api_key:
            self.logger.warning("OPENAI_API_KEY missing from environment. Cloud routing will fail.")
            
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key) if self.api_key else None
        except ImportError:
            self.logger.error("openai package not installed.")
            self.client = None

    def generate_chat(self, messages: List[Dict[str, str]], model_name: Optional[str] = None, temperature: Optional[float] = None) -> str:
        if not self.client:
            raise RuntimeError("OpenAI client not installed or missing key.")
            
        model = model_name or self.model_name
        temp = temperature if temperature is not None else 0.1
        try:
            self.logger.debug(f"Routing to Cloud OpenAI ({model})...")
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=temp
            )
            return response.choices[0].message.content
        except Exception as e:
            self.logger.error(f"OpenAI generation failed: {e}")
            raise

    def chat(self, messages: List[Dict[str, str]], model_name: Optional[str] = None, temperature: Optional[float] = None, **kwargs) -> str:
        return self.generate_chat(messages, model_name=model_name, temperature=temperature)
