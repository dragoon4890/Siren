import torch
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Auto-detect device: use GPU if available, otherwise CPU
# Note: faster-whisper accepts "cuda" for GPU and "cpu" for CPU
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"Using device: {DEVICE} (CUDA available: {torch.cuda.is_available()})")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")  # Load from environment variables

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY environment variable is required. Please set it in your .env file.")

TRANSLATION_TARGET_LANGUAGE = "JA"  # Target language code (e.g., 'en', 'ja', 'es')
TRANSLATION_SOURCE_LANGUAGE = "EN"  # Source language code (e.g., 'en', 'ja', 'es')

PORT_NO = 9090

# SSL証明書の設定
USE_SSL = False
SSL_CERT = "/path/to/cert.pem"
SSL_KEY = "/path/to/privkey.pem"


# whisper # Available models: tiny, base, small, medium, large-v1, large-v2, large-v3
# Smaller models are much faster but slightly less accurate

MODEL = "tiny" 