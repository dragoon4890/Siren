import time
import io
# Using only faster-whisper for CPU testing
# Available models: tiny, base, small, medium, large-v1, large-v2, large-v3
# Smaller models are much faster but slightly less accurate
from faster_whisper import WhisperModel

class SpeechRecognizer:
    def __init__(self, target_language, device):
        self.target_language = target_language
        self.device = device

        # Determine compute type based on device
        compute_type = "float32" if device == "cpu" else "float16"
        print(f"Initializing WhisperModel with model=tiny, device={device}, compute_type={compute_type}")
        
        # Using tiny model for faster processing (Note: model weights are saved in FP16)
        self.model_fast_whisper = WhisperModel("tiny", device=device, compute_type=compute_type)
        
    def recognize(self, wav_file):
        result, lang = self.recognize_fast_whisper(wav_file)
        return result, lang
        
    def recognize_from_bytes(self, audio_bytes):
        """Process audio data directly from memory using BytesIO with name attribute"""
        start_time = time.time()
        
        try:
            print(f"Received audio bytes: {len(audio_bytes)} bytes")
            
            # Create BytesIO buffer and set the name attribute for format detection
            # This is crucial - faster-whisper infers format from the file extension
            audio_buffer = io.BytesIO(audio_bytes)
            audio_buffer.name = "audio.wav"  # Set extension so faster-whisper knows the format
            
            # Use the buffer directly with faster-whisper
            segments, info = self.model_fast_whisper.transcribe(audio_buffer, beam_size=5)
            
            text = ""
            for segment in segments:
                text += segment.text
            
            # Process text
            text = text.strip()
            
            # Filter out common false positives
            if text in ["You", "you", ""]:
                text = ""
            # Filter out Korean news channel mentions
            if "MBC뉴스" in text or "MBC 뉴스" in text:
                text = ""

            # Handle language detection issues - don't filter out "nn" completely
            # Instead, if we get "nn" but have text, assume it's English
            if info.language == "nn" and text:
                info.language = "en"  # Default to English if language is unknown but we have text
            elif info.language == "nn" and not text:
                text = ""  # Only filter out if both language is unknown AND no text
                
            # Log processing time
            lapse_time = time.time() - start_time
            print(f"faster_whisper lang={info.language} chars={len(text)} time={lapse_time:.2f}s text='{text[:80]}'")
            
            return text, info.language
            
        except Exception as e:
            print(f"Error processing audio data: {e}")
            import traceback
            traceback.print_exc()
            return "", "en"

    def recognize_fast_whisper(self, wav_file):
        start_time = time.time()
        segments, info = self.model_fast_whisper.transcribe(wav_file, beam_size=5)

        text = "".join(segment.text for segment in segments).strip()

        # Basic false positive / noise filtering
        if text in ("You", "you"):
            text = ""
        if "MBC뉴스" in text or "MBC 뉴스" in text:
            text = ""

        # Handle unknown language code "nn" edge case
        if info.language == "nn":
            if text:
                info.language = "en"
            else:
                text = ""

        lapse_time = time.time() - start_time
        print(f"faster_whisper file lang={info.language} chars={len(text)} time={lapse_time:.2f}s text='{text[:80]}'")
        return text, info.language
