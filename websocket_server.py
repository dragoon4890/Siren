import datetime
import logging
from typing import Tuple
from aiohttp import web

import settings
from speech_recognizer import SpeechRecognizer
from translator import Translator
from soundoftext_tts import synthesize_soundoftext

# ------------------------------------------------------------
# CORS Middleware
# ------------------------------------------------------------
@web.middleware
async def cors_middleware(request, handler):
    if request.method == 'OPTIONS':
        resp = web.Response()
    else:
        try:
            resp = await handler(request)
        except web.HTTPException as ex:  # allow normal HTTP exceptions
            resp = ex
    # Add permissive CORS (adjust origin if you want restriction)
    origin = request.headers.get('Origin')
    resp.headers['Access-Control-Allow-Origin'] = origin if origin else '*'
    resp.headers['Vary'] = 'Origin'
    resp.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type,Authorization'
    resp.headers['Access-Control-Allow-Credentials'] = 'false'
    # Prevent caching of CORS preflights
    if request.method == 'OPTIONS':
        resp.headers['Access-Control-Max-Age'] = '86400'
    return resp

# ------------------------------------------------------------
# Configuration & Initialization
# ------------------------------------------------------------
# Single (lazy) instances to avoid reloading models per connection.
recognizer: SpeechRecognizer | None = None
translator: Translator | None = None

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("server")

# ------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------

def ensure_components() -> None:
    """Initialize heavy components once (lazy)."""
    global recognizer, translator
    if recognizer is None:
        logger.info("Loading SpeechRecognizer (model=tiny, device=%s)", settings.DEVICE)
        recognizer = SpeechRecognizer(settings.TRANSLATION_TARGET_LANGUAGE, settings.DEVICE)
    if translator is None:
        logger.info("Initializing Gemini translator")
        translator = Translator(settings.GEMINI_API_KEY)

def translate_text(text: str, detected_lang: str) -> Tuple[str, str]:
    """Translate recognized text switching direction based on detected_lang.

    If the detected language matches the configured TARGET, we translate back to SOURCE.
    Otherwise translate into TARGET. We now pass the detected language to the translator
    to assist Gemini with context for non-English input.
    Returns (translated_text, chosen_target_language_code).
    """
    ensure_components()
    assert translator is not None
    if not text:
        return "", ""
    if detected_lang and detected_lang.lower() == settings.TRANSLATION_TARGET_LANGUAGE.lower():
        target = settings.TRANSLATION_SOURCE_LANGUAGE
    else:
        target = settings.TRANSLATION_TARGET_LANGUAGE
    translated = translator.translate(text, target, detected_lang)
    return translated, target

def format_payload(timestamp: datetime.datetime, lang: str, original: str, translated: str) -> str:
    """Format outgoing message for client."""
    return f"{timestamp.strftime('%Y/%m/%d %H:%M:%S')} ({lang}){original}({translated})"

# ------------------------------------------------------------
# WebSocket Handler
# ------------------------------------------------------------

async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    """Handle bi-directional audio streaming over WebSocket.

    Client sends full audio chunks (binary). For each received chunk:
      1. Run speech recognition (in‑memory)
      2. Translate the recognized text
      3. Send formatted result back
    """
    ensure_components()
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    logger.info("WebSocket connection opened")
    await ws.send_str("connected")

    assert recognizer is not None
    async for msg in ws:
        if msg.type == web.WSMsgType.BINARY:
            received_time = datetime.datetime.now()
            audio_size = len(msg.data)
            print(f"Received audio bytes: {audio_size} bytes")
            try:
                text, detected_lang = recognizer.recognize_from_bytes(msg.data)
            except Exception as e:  # Safety net to keep WS alive
                logger.exception("Recognition error: %s", e)
                continue

            if not text:
                continue  # Skip empty recognitions

            translated, _ = translate_text(text, detected_lang)
            payload = format_payload(received_time, detected_lang, text, translated)
            logger.info(payload)
            await ws.send_str(payload)
        else:
            # Optionally handle PING / CLOSE / TEXT if needed
            continue

    logger.info("WebSocket connection closed")
    return ws

# ------------------------------------------------------------
# Auxiliary HTTP Handlers
# ------------------------------------------------------------

async def health(request: web.Request) -> web.Response:
    """Simple health probe."""
    return web.json_response({
        "status": "ok",
        "device": settings.DEVICE,
        "target_language": settings.TRANSLATION_TARGET_LANGUAGE,
    })

async def tts(request: web.Request) -> web.Response:
    """Google TTS endpoint (primary TTS service).
    
    Supports both GET and POST requests for MP3 audio generation.
    
    GET /tts?text=...&lang=en
    POST /tts with JSON: {"text": "...", "language": "en"}

    Parameters:
      text/message - text to synthesize (required)
      lang/language - language code (default: 'en')
    
    Returns high-quality MP3 audio via Google TTS
    """
    # Handle both GET and POST requests
    if request.method == 'GET':
        text = request.query.get('text', '').strip()
        lang = request.query.get('lang', 'en')
    else:  # POST
        try:
            data = await request.json()
            text = data.get('text', '').strip()
            lang = data.get('language') or data.get('lang', 'en')
        except Exception as e:
            return web.Response(status=400, text=f'Invalid JSON: {e}')
    
    if not text:
        return web.Response(status=400, text='missing text parameter')
    
    try:
        mp3_bytes = await synthesize_soundoftext(text, lang)
        resp = web.Response(body=mp3_bytes, content_type='audio/mpeg')
        # Add filename header for better browser handling
        resp.headers['Content-Disposition'] = 'inline; filename="tts_output.mp3"'
        return resp
    except Exception as e:
        logger.exception("Google TTS error")
        return web.Response(status=500, text=f"Google TTS failure: {e}")

async def voices(request: web.Request) -> web.Response:
    """Return list of available Google TTS voices/languages.
    
    GET /voices -> JSON list of supported languages
    """
    try:
        # Return supported languages for Google TTS
        supported_languages = {
            "en-US": "English (United States)",
            "en-GB": "English (United Kingdom)",
            "ja-JP": "Japanese (Japan)",
            "de-DE": "German (Germany)",
            "fr-FR": "French (France)",
            "es-ES": "Spanish (Spain)",
            "it-IT": "Italian (Italy)",
            "pt-BR": "Portuguese (Brazil)",
            "ru-RU": "Russian (Russia)",
            "ko-KR": "Korean (South Korea)",
            "zh-CN": "Chinese (Mandarin, Simplified)",
            "nl-NL": "Dutch (Netherlands)",
            "sv-SE": "Swedish (Sweden)",
            "nb-NO": "Norwegian (Norway)",
            "da-DK": "Danish (Denmark)",
            "fi-FI": "Finnish (Finland)",
            "pl-PL": "Polish (Poland)",
            "tr-TR": "Turkish (Turkey)",
            "ar-SA": "Arabic (Saudi Arabia)",
            "hi-IN": "Hindi (India)",
            "th-TH": "Thai (Thailand)",
            "vi-VN": "Vietnamese (Vietnam)"
        }
        
        return web.Response(
            text=f"Google TTS Supported Languages:\n\n" + 
                 "\n".join([f"{code}: {name}" for code, name in supported_languages.items()]),
            content_type='text/plain'
        )
    except Exception as e:
        logger.exception("Error listing voices")
        return web.Response(status=500, text=f"Failed to list voices: {e}")

# ------------------------------------------------------------
# Application Factory
# ------------------------------------------------------------

def create_app() -> web.Application:
    app = web.Application(middlewares=[cors_middleware])
    app.router.add_get('/translate', websocket_handler)
    app.router.add_get('/health', health)
    
    # Google TTS (primary TTS service)
    app.router.add_get('/tts', tts)
    app.router.add_post('/tts', tts)
    
    # Voice listings
    app.router.add_get('/voices', voices)
    
    # Pre-flight CORS for endpoints
    app.router.add_options('/tts', tts)
    app.router.add_options('/voices', voices)
    
    # Static file serving for client directory
    import os
    client_dir = os.path.join(os.path.dirname(__file__), 'client')
    app.router.add_static('/client/', path=client_dir, name='static')
    
    return app

# ------------------------------------------------------------
# Entrypoint
# ------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Starting server (pure in‑memory audio processing, no SSL)")
    web.run_app(create_app(), host='0.0.0.0', port=settings.PORT_NO)

