import os
import settings
from translator import Translator
from speech_recognizer import SpeechRecognizer

def test_gemini_translation():
    """Test the Gemini translation functionality."""
    translator = Translator(settings.GEMINI_API_KEY)
    
    print("\n===== TESTING GEMINI TRANSLATION =====")
    
    # Test English to Japanese
    test_text = "Hello, how are you today? I hope you're doing well."
    print(f"\nTranslating from English to Japanese:")
    print(f"Input: {test_text}")
    result = translator.translate(test_text, settings.TRANSLATION_TARGET_LANGUAGE, settings.TRANSLATION_SOURCE_LANGUAGE)
    print(f"Output: {result}")
    
    # Test Japanese to English
    test_text = "こんにちは、お元気ですか？今日はいい天気ですね。"
    print(f"\nTranslating from Japanese to English:")
    print(f"Input: {test_text}")
    result = translator.translate(test_text, settings.TRANSLATION_SOURCE_LANGUAGE, settings.TRANSLATION_TARGET_LANGUAGE)
    print(f"Output: {result}")
    
    print("\n===== GEMINI TRANSLATION TEST COMPLETE =====")

def test_speech_recognition():
    """Test the speech recognition functionality."""
    # Make sure we're using CPU
    recognizer = SpeechRecognizer(settings.TRANSLATION_TARGET_LANGUAGE, settings.DEVICE)
    
    print("\n===== TESTING SPEECH RECOGNITION (CPU) =====")
    print(f"Using device: {settings.DEVICE}")
    print(f"Model: tiny (fastest, smaller file size, good enough accuracy)")
    print(f"Compute type: float32 (recommended for CPU)")
    print("----------------------------------------")
    
    # Create audio directory if it doesn't exist
    os.makedirs("audio", exist_ok=True)
    
    # Check for test audio files
    audio_files = [f for f in os.listdir("audio") if f.endswith(".wav")]
    
    if not audio_files:
        print("\nNo test audio files found in the 'audio' directory.")
        print("To test speech recognition, add WAV files to the 'audio' folder.")
    else:
        print(f"\nFound {len(audio_files)} audio file(s) to test:")
        for i, audio_file in enumerate(audio_files):
            print(f"\nTesting file {i+1}/{len(audio_files)}: {audio_file}")
            file_path = os.path.join("audio", audio_file)
            
            print("Recognition in progress (this might take a moment on CPU)...")
            text, lang = recognizer.recognize(file_path)
            
            print(f"Detected language: {lang}")
            print(f"Recognized text: {text}")
            
            # Also test translation of the recognized text
            if text:
                translator = Translator(settings.GEMINI_API_KEY)
                if lang.lower() == "ja":
                    translated = translator.translate(text, settings.TRANSLATION_SOURCE_LANGUAGE, "")
                    print(f"Translation to English: {translated}")
                else:
                    translated = translator.translate(text, settings.TRANSLATION_TARGET_LANGUAGE, "")
                    print(f"Translation to Japanese: {translated}")
    
    print("\n===== SPEECH RECOGNITION TEST COMPLETE =====")

if __name__ == "__main__":
    print("\nRunning tests using CPU for processing...")
    test_gemini_translation()
    test_speech_recognition()
