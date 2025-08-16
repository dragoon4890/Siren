import torch
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

DEVICE = "cpu"
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
