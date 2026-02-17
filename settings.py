import torch
import os
from dotenv import load_dotenv
from typing import Optional
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

class ConfigurationError(Exception):
    """Raised when configuration is invalid or missing."""
    pass

class AppSettings:
    """Application configuration with validation."""
    
    def __init__(self):
        self._validate_and_set_device()
        self._validate_and_set_api_keys()
        self._validate_and_set_languages()
        self._validate_and_set_server_config()
        self._validate_and_set_model_config()
        
    def _validate_and_set_device(self):
        """Auto-detect and validate device configuration."""
        self.DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {self.DEVICE} (CUDA available: {torch.cuda.is_available()})")
        
    def _validate_and_set_api_keys(self):
        """Validate required API keys."""
        self.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
        if not self.GEMINI_API_KEY:
            raise ConfigurationError(
                "GEMINI_API_KEY environment variable is required. Please set it in your .env file."
            )
        if len(self.GEMINI_API_KEY.strip()) < 10:
            raise ConfigurationError("GEMINI_API_KEY appears to be invalid (too short)")
            
    def _validate_and_set_languages(self):
        """Validate language configuration."""
        self.TRANSLATION_TARGET_LANGUAGE = os.getenv("TRANSLATION_TARGET_LANGUAGE", "JA").upper()
        self.TRANSLATION_SOURCE_LANGUAGE = os.getenv("TRANSLATION_SOURCE_LANGUAGE", "EN").upper()
        
        # Validate language codes (basic validation)
        valid_languages = {"EN", "JA", "ES", "FR", "DE", "IT", "PT", "RU", "KO", "ZH", "AR", "HI"}
        if self.TRANSLATION_TARGET_LANGUAGE not in valid_languages:
            logger.warning(f"Unusual target language: {self.TRANSLATION_TARGET_LANGUAGE}")
        if self.TRANSLATION_SOURCE_LANGUAGE not in valid_languages:
            logger.warning(f"Unusual source language: {self.TRANSLATION_SOURCE_LANGUAGE}")
            
    def _validate_and_set_server_config(self):
        """Validate server configuration."""
        try:
            self.PORT_NO = int(os.getenv("PORT_NO", "9090"))
            if not (1024 <= self.PORT_NO <= 65535):
                raise ConfigurationError(f"PORT_NO must be between 1024-65535, got {self.PORT_NO}")
        except ValueError:
            raise ConfigurationError("PORT_NO must be a valid integer")
            
        # SSL Configuration
        self.USE_SSL = os.getenv("USE_SSL", "false").lower() in ("true", "1", "yes")
        self.SSL_CERT = os.getenv("SSL_CERT", "/path/to/cert.pem")
        self.SSL_KEY = os.getenv("SSL_KEY", "/path/to/privkey.pem")
        
        if self.USE_SSL:
            if not os.path.exists(self.SSL_CERT):
                raise ConfigurationError(f"SSL certificate not found: {self.SSL_CERT}")
            if not os.path.exists(self.SSL_KEY):
                raise ConfigurationError(f"SSL private key not found: {self.SSL_KEY}")
                
    def _validate_and_set_model_config(self):
        """Validate model configuration."""
        valid_models = {"tiny", "base", "small", "medium", "large-v1", "large-v2", "large-v3"}
        self.MODEL = os.getenv("WHISPER_MODEL", "tiny").lower()
        
        if self.MODEL not in valid_models:
            logger.warning(f"Unknown Whisper model: {self.MODEL}. Valid options: {valid_models}")
            self.MODEL = "tiny"  # Fallback to safest option
            
        logger.info(f"Using Whisper model: {self.MODEL}")
        
    def get_config_summary(self) -> dict:
        """Get a summary of current configuration (safe for logging)."""
        return {
            "device": self.DEVICE,
            "model": self.MODEL,
            "port": self.PORT_NO,
            "target_language": self.TRANSLATION_TARGET_LANGUAGE,
            "source_language": self.TRANSLATION_SOURCE_LANGUAGE,
            "use_ssl": self.USE_SSL,
            "gemini_api_configured": bool(self.GEMINI_API_KEY)
        }

# Create global settings instance
try:
    settings = AppSettings()
    logger.info(f"Configuration loaded successfully: {settings.get_config_summary()}")
except ConfigurationError as e:
    logger.error(f"Configuration error: {e}")
    raise

# Backward compatibility - expose settings as module-level variables
DEVICE = settings.DEVICE
GEMINI_API_KEY = settings.GEMINI_API_KEY
TRANSLATION_TARGET_LANGUAGE = settings.TRANSLATION_TARGET_LANGUAGE
TRANSLATION_SOURCE_LANGUAGE = settings.TRANSLATION_SOURCE_LANGUAGE
PORT_NO = settings.PORT_NO
USE_SSL = settings.USE_SSL
SSL_CERT = settings.SSL_CERT
SSL_KEY = settings.SSL_KEY
MODEL = settings.MODEL 