from translator import Translator
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_translation():
    try:
        # Get API key from user input
        api_key = input("Please enter your Gemini API key: ").strip()
        
        if not api_key:
            raise ValueError("API key cannot be empty")
            
        logger.info("Initializing translator...")
        translator = Translator(api_key)
        
        # Test cases with different languages
        test_cases = [
            {
                "text": "Hello, how are you?",
                "source_lang": "English",
                "target_lang": "Japanese"
            },
            {
                "text": "こんにちは、元気ですか？",
                "source_lang": "Japanese",
                "target_lang": "English"
            },
        ]
        
        print("\nTesting Translator:")
        print("-" * 50)
        
        for case in test_cases:
            print(f"\nSource ({case['source_lang']}): {case['text']}")
            result = translator.translate(
                case['text'],
                case['target_lang'],
                case['source_lang']
            )
            print(f"Translation ({case['target_lang']}): {result}")
            print("-" * 50)
            
    except Exception as e:
        logger.error(f"Error in test_translation: {str(e)}")
        print(f"\nError: {str(e)}")

if __name__ == "__main__":
    test_translation()
