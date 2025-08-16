import torch

DEVICE = "cpu"
GEMINI_API_KEY = "AIzaSyB2FWy0a3HuJUkiIWN5yKdk8hE8ZeZ32cY"  # Gemini API key
TRANSLATION_TARGET_LANGUAGE = "JA"  # Target language code (e.g., 'en', 'ja', 'es')
TRANSLATION_SOURCE_LANGUAGE = "EN"  # Source language code (e.g., 'en', 'ja', 'es')

PORT_NO = 9090

# SSL証明書の設定
USE_SSL = False
SSL_CERT = "/path/to/cert.pem"
SSL_KEY = "/path/to/privkey.pem"
