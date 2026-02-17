"""
Translation Module using Google Gemini

This module provides text translation capabilities using Google's Gemini LLM,
which offers superior context-aware translation compared to traditional services,
especially for languages where meaning changes with context.
"""
import google.generativeai as genai
import logging
from typing import Optional, Dict

# Comprehensive mapping from ISO 639-1 codes to English language names for better Gemini translation
LANG_CODE_TO_NAME = {
    # Major world languages
    'en': 'English', 'es': 'Spanish', 'fr': 'French', 'de': 'German', 'it': 'Italian', 'pt': 'Portuguese',
    'ru': 'Russian', 'ja': 'Japanese', 'ko': 'Korean', 'zh': 'Chinese', 'ar': 'Arabic', 'hi': 'Hindi',
    'th': 'Thai', 'vi': 'Vietnamese', 'tr': 'Turkish', 'id': 'Indonesian',
    
    # Chinese variants
    'cmn-Hant-TW': 'Traditional Chinese', 'cmn-Hans-CN': 'Simplified Chinese',
    
    # Language variants with regional codes
    'nb-NO': 'Norwegian', 'fil-PH': 'Filipino',
    
    # European languages
    'pl': 'Polish', 'nl': 'Dutch', 'sv': 'Swedish', 'no': 'Norwegian', 'da': 'Danish', 'fi': 'Finnish',
    'cs': 'Czech', 'hu': 'Hungarian', 'ro': 'Romanian', 'bg': 'Bulgarian', 'hr': 'Croatian', 'sk': 'Slovak',
    'sl': 'Slovenian', 'et': 'Estonian', 'lv': 'Latvian', 'lt': 'Lithuanian', 'uk': 'Ukrainian', 'el': 'Greek',
    
    # Middle Eastern and South Asian languages
    'he': 'Hebrew', 'fa': 'Persian', 'ur': 'Urdu', 'bn': 'Bengali', 'gu': 'Gujarati', 'kn': 'Kannada',
    'ml': 'Malayalam', 'mr': 'Marathi', 'ta': 'Tamil', 'te': 'Telugu', 'ne': 'Nepali', 'si': 'Sinhala',
    
    # Southeast Asian and other languages
    'ms': 'Malay', 'tl': 'Filipino', 'my': 'Myanmar', 'km': 'Khmer', 'lo': 'Lao', 'ka': 'Georgian',
    'hy': 'Armenian', 'az': 'Azerbaijani', 'kk': 'Kazakh', 'uz': 'Uzbek', 'sq': 'Albanian', 'bs': 'Bosnian',
    'sr': 'Serbian', 'mk': 'Macedonian', 'mt': 'Maltese', 'is': 'Icelandic', 'ga': 'Irish', 'cy': 'Welsh',
    'eu': 'Basque', 'ca': 'Catalan', 'af': 'Afrikaans', 'sw': 'Swahili', 'am': 'Amharic', 'la': 'Latin'
}


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Translator:
    """
    Google Gemini-based text translator with context awareness.
    
    This class provides translation services using Google's Gemini LLM,
    which offers superior performance for context-dependent translations
    compared to traditional rule-based translation services.
    
    Attributes:
        api_key: Google Gemini API key
        model: Initialized Gemini model instance
    """
    
    def __init__(self, api_key: str):
        """
        Initialize the translator with Google Gemini API.
        
        Args:
            api_key: Valid Google Gemini API key
            
        Raises:
            Exception: If API key is invalid or model initialization fails
        """
        try:
            self.api_key = api_key
            genai.configure(api_key=api_key)
            # Use Gemini 2.0 Flash model for faster translation
            self.model = genai.GenerativeModel('gemini-2.0-flash')
            logger.info("Gemini 2.0 Flash translator initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Gemini: {str(e)}")
            raise

    def translate(self, text: str, target_lang: str, source_lang: Optional[str] = None) -> str:
        """
        Translate text using Gemini with intelligent language handling.

        The method automatically maps language codes to full language names
        for more reliable translation prompts. If source_lang is not provided,
        Gemini will automatically detect the source language.

        Args:
            text: Text to translate (required)
            target_lang: Target language code or name (e.g., 'ja', 'Japanese')
            source_lang: Source language code or name (optional, auto-detected if None)

        Returns:
            Translated text string, or empty string if translation fails

        Note:
            Uses minimal prompts to reduce latency and prevent hallucinations.
            Language codes are mapped to full names for better model understanding.
        """
            source_lang: Source language code or name (optional, auto-detected if None)

        Returns:
            Translated text string, or empty string if translation fails

        Note:
            Uses minimal prompts to reduce latency and prevent hallucinations.
            Language codes are mapped to full names for better model understanding.
        """
        try:
            if not text or not text.strip():
                return ""
                
            src_code = (source_lang or '').strip().lower()
            tgt_code = (target_lang or '').strip().lower()

            # Map language codes to full names for better prompt clarity
            src_name = LANG_CODE_TO_NAME.get(src_code, source_lang) if source_lang else ''
            tgt_name = LANG_CODE_TO_NAME.get(tgt_code, target_lang)

            # Build a clear, deterministic prompt with minimal complexity
            if src_name:
                prompt = (
                    "You are a translation engine. Translate the following "
                    f"{src_name} text into {tgt_name}. Output ONLY the translated {tgt_name} text with no extra words.\n\n"
                    f"Text: {text}"
                )
            else:
                # No reliable source language; ask Gemini to infer
                prompt = (
                    "You are a translation engine. Detect the language of the following text and translate it into "
                    f"{tgt_name}. Output ONLY the translated {tgt_name} text.\n\nText: {text}"
                )

            # Generate translation with error handling
            response = self.model.generate_content(prompt, stream=False)
            translated = (response.text or '').strip()
            
            # Log successful translation (truncated for readability)
            logger.info(f"Translation OK: {source_lang or 'auto'}->{target_lang} | '{text[:40]}...' -> '{translated[:40]}...'")
            return translated
            
        except Exception as e:
            error_msg = f"Translation error: {str(e)}"
            logger.error(error_msg)
            return ""  # Return empty string on failure for graceful degradation
