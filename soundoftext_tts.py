"""Sound of Text API TTS engine using Google TTS.

This module provides high-quality text-to-speech synthesis using the Sound of Text API,
which uses Google's TTS engine under the hood.
"""
import asyncio
import aiohttp
import logging
from typing import Optional
import time

logger = logging.getLogger("soundoftext_tts")

class SoundOfTextTTS:
    """Sound of Text API client for high-quality TTS synthesis."""
    
    BASE_URL = "https://api.soundoftext.com/sounds"
    FILES_URL = "https://files.soundoftext.com"
    
    # Voice mapping for common languages
    VOICE_MAP = {
        'en': 'en-US',
        'en-us': 'en-US', 
        'en-gb': 'en-GB',
        'ja': 'ja-JP',
        'ja-jp': 'ja-JP',
        'de': 'de-DE',
        'fr': 'fr-FR',
        'es': 'es-ES',
        'it': 'it-IT',
        'pt': 'pt-BR',
        'pt-br': 'pt-BR',
        'ru': 'ru-RU',
        'ko': 'ko-KR',
        'zh': 'zh-CN',
        'nl': 'nl-NL',
        'sv': 'sv-SE',
        'no': 'nb-NO',
        'da': 'da-DK',
        'fi': 'fi-FI',
        'pl': 'pl-PL',
        'tr': 'tr-TR',
        'ar': 'ar-SA',
        'hi': 'hi-IN',
        'th': 'th-TH',
        'vi': 'vi-VN'
    }
    
    def __init__(self, timeout: int = 30):
        self.timeout = timeout
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()
        return self.session
    
    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
    
    def _get_voice_code(self, lang_code: str) -> str:
        """Convert language code to Sound of Text voice code."""
        lang_lower = lang_code.lower()
        return self.VOICE_MAP.get(lang_lower, 'en-US')
    
    async def synthesize_to_mp3_url(self, text: str, lang_code: str = 'en') -> str:
        """Synthesize text and return the MP3 URL.
        
        Args:
            text: Text to synthesize
            lang_code: Language code (e.g., 'en', 'ja', 'de')
            
        Returns:
            URL to the generated MP3 file
            
        Raises:
            RuntimeError: If synthesis fails
        """
        if not text.strip():
            raise ValueError("Text cannot be empty")
        
        voice = self._get_voice_code(lang_code)
        session = await self._get_session()
        
        # Step 1: Submit TTS request
        payload = {
            "engine": "Google",
            "data": {
                "text": text,
                "voice": voice
            }
        }
        
        logger.info(f"Submitting TTS request for voice '{voice}': {text[:50]}...")
        
        try:
            async with session.post(self.BASE_URL, json=payload, timeout=self.timeout) as response:
                if not response.ok:
                    error_text = await response.text()
                    raise RuntimeError(f"Sound of Text API error {response.status}: {error_text}")
                
                result = await response.json()
                if not result.get('success'):
                    raise RuntimeError(f"Sound of Text API failed: {result}")
                
                audio_id = result.get('id')
                if not audio_id:
                    raise RuntimeError("No ID returned from Sound of Text API")
        
        except asyncio.TimeoutError:
            raise RuntimeError("Timeout submitting TTS request")
        except Exception as e:
            raise RuntimeError(f"Failed to submit TTS request: {e}")
        
        # Step 2: Poll for completion and get audio URL
        check_url = f"{self.BASE_URL}/{audio_id}"
        max_attempts = 20  # 20 attempts * 1.5 seconds = 30 seconds max wait
        
        for attempt in range(max_attempts):
            try:
                await asyncio.sleep(1.5)  # Wait between checks
                
                async with session.get(check_url, timeout=self.timeout) as response:
                    if not response.ok:
                        error_text = await response.text()
                        logger.warning(f"Status check failed (attempt {attempt + 1}): {error_text}")
                        continue
                    
                    result = await response.json()
                    status = result.get('status', '').lower()
                    
                    if status == 'done':
                        audio_url = result.get('location')
                        if audio_url:
                            logger.info(f"TTS synthesis completed: {audio_url}")
                            return audio_url
                        else:
                            raise RuntimeError("No audio location in completed response")
                    
                    elif status == 'error':
                        raise RuntimeError(f"Sound of Text synthesis failed: {result}")
                    
                    elif status in ['pending', 'processing']:
                        logger.debug(f"TTS still processing (attempt {attempt + 1})")
                        continue
                    
                    else:
                        logger.warning(f"Unknown status: {status}")
                        continue
                        
            except asyncio.TimeoutError:
                logger.warning(f"Timeout checking status (attempt {attempt + 1})")
                continue
            except Exception as e:
                logger.warning(f"Error checking status (attempt {attempt + 1}): {e}")
                continue
        
        raise RuntimeError("TTS synthesis timed out or failed to complete")
    
    async def synthesize_to_bytes(self, text: str, lang_code: str = 'en') -> bytes:
        """Synthesize text and return MP3 audio bytes.
        
        Args:
            text: Text to synthesize
            lang_code: Language code (e.g., 'en', 'ja', 'de')
            
        Returns:
            MP3 audio data as bytes
        """
        audio_url = await self.synthesize_to_mp3_url(text, lang_code)
        session = await self._get_session()
        
        try:
            async with session.get(audio_url, timeout=self.timeout) as response:
                if not response.ok:
                    raise RuntimeError(f"Failed to download audio: {response.status}")
                
                audio_data = await response.read()
                logger.info(f"Downloaded {len(audio_data)} bytes of MP3 audio")
                return audio_data
                
        except asyncio.TimeoutError:
            raise RuntimeError("Timeout downloading audio")
        except Exception as e:
            raise RuntimeError(f"Failed to download audio: {e}")


# Singleton instance for reuse
_tts_instance: Optional[SoundOfTextTTS] = None

async def get_tts_instance() -> SoundOfTextTTS:
    """Get or create the singleton TTS instance."""
    global _tts_instance
    if _tts_instance is None:
        _tts_instance = SoundOfTextTTS()
    return _tts_instance

async def synthesize_soundoftext(text: str, lang_code: str = 'en') -> bytes:
    """Convenience function for TTS synthesis.
    
    Args:
        text: Text to synthesize
        lang_code: Language code
        
    Returns:
        MP3 audio data as bytes
    """
    tts = await get_tts_instance()
    return await tts.synthesize_to_bytes(text, lang_code)
