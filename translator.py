import google.generativeai as genai
import logging

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
    def __init__(self, api_key):
        try:
            self.api_key = api_key
            genai.configure(api_key=api_key)
            # Use Gemini 2.0 Flash model for faster translation
            self.model = genai.GenerativeModel('gemini-2.0-flash')
            logger.info("Gemini 2.0 Flash translator initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing Gemini: {str(e)}")
            raise

    def translate(self, text: str, target_lang: str, source_lang: str | None):
        """Translate text using Gemini.

        source_lang / target_lang can be language codes (en, ja, etc.) or names. We try to map codes
        to full language names for a more reliable prompt. If source_lang is empty/None we omit it.
        """
        try:
            if not text:
                return ""
            src_code = (source_lang or '').strip().lower()
            tgt_code = (target_lang or '').strip().lower()

            src_name = LANG_CODE_TO_NAME.get(src_code, source_lang) if source_lang else ''
            tgt_name = LANG_CODE_TO_NAME.get(tgt_code, target_lang)

            # Build a clear deterministic prompt. Keep it minimal to reduce latency / hallucinations.
            if src_name:
                prompt = (
                    "You are a translation engine. Translate the following "
                    f"{src_name} text into {tgt_name}. Output ONLY the translated {tgt_name} text with no extra words.\n\n"
                    f"Text: {text}"
                )
            else:
                # No reliable source language; ask Gemini to infer.
                prompt = (
                    "You are a translation engine. Detect the language of the following text and translate it into "
                    f"{tgt_name}. Output ONLY the translated {tgt_name} text.\n\nText: {text}"
                )

            response = self.model.generate_content(prompt, stream=False)
            translated = (response.text or '').strip()
            logger.info(f"Translation OK: {source_lang}->{target_lang} | '{text[:40]}' -> '{translated[:40]}'")
            return translated
        except Exception as e:
            error_msg = f"Translation error: {str(e)}"
            logger.error(error_msg)
            return ""
