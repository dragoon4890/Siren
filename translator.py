import google.generativeai as genai
import logging


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

    def translate(self, text, target_lang, source_lang):
        try:
            # Create a simple and direct prompt for translation
            prompt = f"Translate from  {source_lang} to {target_lang} and only include transaltion as output: {text}"
            
            # Get response from Gemini with stream=False for faster response
            response = self.model.generate_content(prompt, stream=False)
            
            # Log successful translation
            logger.info(f"Translation successful: {source_lang} -> {target_lang}")
            
            # Return the translated text
            return response.text.strip()
        except Exception as e:
            error_msg = f"Translation error: {str(e)}"
            logger.error(error_msg)
            return error_msg
