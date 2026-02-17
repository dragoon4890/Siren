"""
Speech Recognition Module using Faster-Whisper

This module provides speech-to-text functionality using OpenAI's Faster-Whisper
implementation, optimized for real-time transcription with configurable models
and device support (CPU/GPU).
"""
import time
import io
import traceback
from typing import Tuple, Optional
# Using only faster-whisper for CPU testing
# Available models: tiny, base, small, medium, large-v1, large-v2, large-v3
# Smaller models are much faster but slightly less accurate
from faster_whisper import WhisperModel

class SpeechRecognizer:
    """
    Speech recognition using Faster-Whisper with optimized performance.
    
    This class provides speech-to-text transcription capabilities using
    OpenAI's Faster-Whisper implementation. It supports various model sizes
    and automatically configures compute type based on device availability.
    
    Args:
        target_language: Target language code for translation context
        device: Device to use for inference ('cpu' or 'cuda')
        model: Whisper model size ('tiny', 'base', 'small', 'medium', 'large-v1', 'large-v2', 'large-v3')
        
    Attributes:
        target_language: The target language for translation context
        device: Device being used for inference
        model: Model size identifier
        model_fast_whisper: The loaded Faster-Whisper model instance
    """
    
    def __init__(self, target_language: str, device: str, model: str):
        """
        Initialize the speech recognizer with specified configuration.
        
        Args:
            target_language: Target language code (e.g., 'ja', 'en', 'es')
            device: Computing device ('cpu' or 'cuda')
            model: Whisper model size identifier
        """
        self.target_language = target_language
        self.device = device
        self.model = model

        # Determine compute type based on device
        compute_type = "float32" if device == "cpu" else "float16"
        print(f"Initializing WhisperModel with model={model}, device={device}, compute_type={compute_type}")
        
        # Initialize Faster-Whisper model (Note: model weights are saved in FP16)
        self.model_fast_whisper = WhisperModel(model, device=device, compute_type=compute_type)
        
    def recognize(self, wav_file: str) -> Tuple[str, str]:
        """
        Recognize speech from a WAV file.
        
        This is a wrapper method that delegates to the Faster-Whisper implementation.
        
        Args:
            wav_file: Path to the WAV file to process
            
        Returns:
            Tuple of (transcribed_text, detected_language_code)
        """
        result, lang = self.recognize_fast_whisper(wav_file)
        return result, lang
        
    def recognize_from_bytes(self, audio_bytes: bytes) -> Tuple[str, str]:
        """
        Process audio data directly from memory using BytesIO with name attribute.
        
        This method processes audio data without requiring file I/O, making it
        ideal for real-time audio processing from network streams or microphone input.
        
        Args:
            audio_bytes: Raw audio data as bytes (WAV format expected)
            
        Returns:
            Tuple of (transcribed_text, detected_language_code)
            
        Note:
            The audio_buffer.name attribute is crucial for format detection.
            Faster-whisper infers the audio format from the file extension.
        """
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
            
            # Process and clean the transcribed text
            text = text.strip()
            
            # Filter out common false positives and noise
            if text in ["You", "you", ""]:
                text = ""
                
            # Filter out Korean news channel mentions (domain-specific noise filtering)
            if "MBC뉴스" in text or "MBC 뉴스" in text:
                text = ""

            # Handle unknown language detection edge cases
            if info.language == "nn":  # 'nn' is an unknown language code
                if text:
                    info.language = "en"  # Default to English if we have text but unknown language
                else:
                    text = ""

            # Performance logging
            lapse_time = time.time() - start_time
            print(f"faster_whisper bytes processing: lang={info.language}, chars={len(text)}, time={lapse_time:.2f}s, text='{text[:50]}...'")
            
            return text, info.language

        except Exception as e:
            lapse_time = time.time() - start_time
            print(f"Error in recognize_from_bytes after {lapse_time:.2f}s: {e}")
            traceback.print_exc()
            return "", "en"  # Return safe defaults on error

    def recognize_fast_whisper(self, wav_file: str) -> Tuple[str, str]:
        """
        Recognize speech from a file using Faster-Whisper.
        
        This method processes audio files using the Faster-Whisper model with
        optimized beam search and includes post-processing for noise filtering.
        
        Args:
            wav_file: Path to the audio file to process
            
        Returns:
            Tuple of (transcribed_text, detected_language_code)
            
        Note:
            Includes domain-specific filtering for common false positives
            and handles edge cases in language detection.
        """
        start_time = time.time()
        segments, info = self.model_fast_whisper.transcribe(wav_file, beam_size=5)

        # Concatenate all segments and clean the text
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
        print(f"faster_whisper file processing: lang={info.language}, chars={len(text)}, time={lapse_time:.2f}s, text='{text[:80]}'")
        return text, info.language
