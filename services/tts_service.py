"""
Text-to-Speech (TTS) Service using Deepgram Aura
"""

import httpx
import base64
from core.config import settings
from observability import get_logging_system

class TTSService:
    def __init__(self):
        self.logger = get_logging_system()
        self.api_key = settings.DEEPGRAM_API_KEY
        # You can switch models (e.g., aura-asteria-en, aura-luna-en, aura-stella-en, aura-orion-en)
        self.url = "https://api.deepgram.com/v1/speak?model=aura-asteria-en&encoding=mp3"

    async def generate_audio_base64(self, text: str) -> str:
        """
        Takes input text and calls Deepgram Aura TTS API to generate audio.
        Returns the audio encoded as a base64 string.
        """
        if not self.api_key:
            self.logger.warning("Deepgram API key missing. TTS disabled.")
            return None
            
        if not text or not text.strip():
            return None

        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "text": text
        }
        
        try:
            # TTS can take a few seconds depending on text length
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(self.url, headers=headers, json=payload)
                
                if response.status_code == 200:
                    audio_bytes = response.content
                    self.logger.info(f"TTS successfully generated audio ({len(audio_bytes)} bytes).")
                    return base64.b64encode(audio_bytes).decode('utf-8')
                else:
                    self.logger.error(f"Deepgram TTS failed: {response.status_code} - {response.text}")
                    return None
        except Exception as e:
            self.logger.error(f"TTS Exception: {e}")
            return None

# Singleton instance
tts_service = TTSService()
