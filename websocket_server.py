import datetime
import logging
from typing import Tuple
from aiohttp import web
import base64
import asyncio
from asyncio import Queue
import time
import aiohttp

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

# Request queue system to prevent thundering herd with RVC - OPTIMIZED PIPELINE
audio_processing_queue: Queue = None
rvc_queue: Queue = None  # Separate queue for RVC-ready requests
max_concurrent_requests = 1  # RVC processing (bottleneck - only 1 at a time)
max_concurrent_preprocessing = 5  # Speech+Translation+TTS can run concurrently
processing_semaphore: asyncio.Semaphore = None  # Controls RVC bottleneck
preprocessing_semaphore: asyncio.Semaphore = None  # Controls preprocessing pipeline
queue_processor_task: asyncio.Task = None
rvc_processor_task: asyncio.Task = None

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("server")

# ------------------------------------------------------------
# Helper Functions
# ------------------------------------------------------------

async def initialize_queue_system():
    """Initialize the optimized pipeline queue system."""
    global audio_processing_queue, rvc_queue, processing_semaphore, preprocessing_semaphore, queue_processor_task, rvc_processor_task
    
    if audio_processing_queue is None:
        # Main queue for incoming requests
        audio_processing_queue = Queue(maxsize=50)  # Max 50 queued requests
        # RVC queue for requests ready for voice conversion
        rvc_queue = Queue(maxsize=20)  # Smaller buffer for RVC-ready requests
        
        # Semaphores for different stages
        processing_semaphore = asyncio.Semaphore(max_concurrent_requests)  # RVC: only 1 at a time
        preprocessing_semaphore = asyncio.Semaphore(max_concurrent_preprocessing)  # Pipeline: up to 5 concurrent
        
        # Start both processors
        queue_processor_task = asyncio.create_task(process_preprocessing_queue())
        rvc_processor_task = asyncio.create_task(process_rvc_queue())
        
        logger.info(f"Optimized pipeline initialized (preprocessing_concurrent={max_concurrent_preprocessing}, rvc_concurrent={max_concurrent_requests}, queue_size=50)")

async def process_preprocessing_queue():
    """Background task to process preprocessing pipeline (Speech + Translation + TTS)."""
    global audio_processing_queue
    
    logger.info("Preprocessing queue processor started")
    while True:
        try:
            # Get next request from main queue
            request_data = await audio_processing_queue.get()
            
            if request_data is None:  # Shutdown signal
                break
                
            # Process preprocessing with higher concurrency (up to 5 at a time)
            async with preprocessing_semaphore:
                await process_preprocessing_stage(request_data)
            
            # Mark preprocessing task as done
            audio_processing_queue.task_done()
            
        except Exception as e:
            logger.exception("Error in preprocessing queue processor: %s", e)
            await asyncio.sleep(0.1)

async def process_rvc_queue():
    """Background task to process RVC conversion (bottleneck stage)."""
    global rvc_queue
    
    logger.info("RVC queue processor started")
    while True:
        try:
            # Get next RVC-ready request
            request_data = await rvc_queue.get()
            
            if request_data is None:  # Shutdown signal
                break
                
            # Process RVC with strict concurrency (only 1 at a time)
            async with processing_semaphore:
                await process_rvc_stage(request_data)
            
            # Mark RVC task as done
            rvc_queue.task_done()
            
        except Exception as e:
            logger.exception("Error in RVC queue processor: %s", e)
            await asyncio.sleep(0.1)

async def process_preprocessing_stage(request_data):
    """Process preprocessing stages: Speech Recognition + Translation + TTS."""
    try:
        request_id = request_data['id']
        audio_blob = request_data['audio_blob']
        source_lang = request_data['source_lang']
        target_lang = request_data['target_lang']
        start_time = request_data['start_time']
        
        logger.info(f"Preprocessing request {request_id} (queued for {time.time() - start_time:.2f}s)")
        
        # Step 1: Extract text from original audio using speech recognition (~1s)
        original_text, detected_lang = await extract_text_from_original_audio(audio_blob)
        
        if not original_text or original_text == "No speech detected":
            request_data['future'].set_result({
                'error': 'No speech detected in audio',
                'status': 400
            })
            return

        # Step 2: Translate the extracted text (~0.5s)
        translated_text = await translate_text(original_text, detected_lang, target_lang)

        # Step 3: Generate TTS for the translated text (~0.8s)  
        translated_audio_blob = await synthesize_soundoftext(translated_text, target_lang)

        # Prepare data for RVC stage
        request_data.update({
            'original_text': original_text,
            'translated_text': translated_text,
            'detected_lang': detected_lang,
            'translated_audio_blob': translated_audio_blob,
            'preprocessing_time': time.time() - start_time
        })
        
        # Add to RVC queue for final processing
        await rvc_queue.put(request_data)
        logger.info(f"Request {request_id} preprocessing completed in {time.time() - start_time:.2f}s, queued for RVC")
        
    except Exception as e:
        logger.exception(f"Error in preprocessing stage for {request_data.get('id', 'unknown')}: %s", e)
        request_data['future'].set_result({
            'error': f"Preprocessing Error: {e}",
            'status': 500
        })

async def process_rvc_stage(request_data):
    """Process RVC conversion stage (the bottleneck)."""
    try:
        request_id = request_data['id']
        translated_audio_blob = request_data['translated_audio_blob']
        target_lang = request_data['target_lang']
        start_time = request_data['start_time']
        
        logger.info(f"RVC processing request {request_id}")
        
        # Step 4: RVC Voice Conversion (~10s) - THE BOTTLENECK
        final_audio_blob = await apply_rvc_conversion(translated_audio_blob, target_lang)

        # Encode audio blobs to Base64
        original_audio_base64 = base64.b64encode(request_data['audio_blob']).decode('utf-8')
        final_audio_base64 = base64.b64encode(final_audio_blob).decode('utf-8')

        # Return successful result
        result = {
            'original_audio_blob': original_audio_base64,
            'translated_audio_blob': final_audio_base64,  # Now contains RVC-processed audio
            'original_text': request_data['original_text'],
            'translated_text': request_data['translated_text'],
            'detected_language': request_data['detected_lang'],
            'processing_time': time.time() - start_time,
            'preprocessing_time': request_data['preprocessing_time'],
            'request_id': request_id
        }
        
        # Cache result for convert_status endpoint if this is a convert_new request
        if request_id.startswith('conv_'):
            if not hasattr(convert_status, 'results_cache'):
                convert_status.results_cache = {}
            convert_status.results_cache[request_id] = result
        
        request_data['future'].set_result(result)
        logger.info(f"Request {request_id} completed in {time.time() - start_time:.2f}s (preprocessing: {request_data['preprocessing_time']:.2f}s)")
        
    except Exception as e:
        logger.exception(f"Error in RVC stage for {request_data.get('id', 'unknown')}: %s", e)
        request_data['future'].set_result({
            'error': f"RVC Processing Error: {e}",
            'status': 500
        })

async def apply_rvc_conversion(audio_blob: bytes, target_lang: str) -> bytes:
    """Apply RVC voice conversion to the audio blob."""
    try:
        # Prepare the audio data for RVC API call
        # Convert audio blob to the format expected by RVC endpoint
        
        async with aiohttp.ClientSession() as session:
            # Create form data for the RVC API call
            data = aiohttp.FormData()
            data.add_field('audio', audio_blob, filename='audio.wav', content_type='audio/wav')
            
            # Make the RVC conversion request
            async with session.post('http://127.0.0.1:5000/convert', data=data) as response:
                if response.status == 200:
                    converted_audio = await response.read()
                    logger.info(f"RVC conversion successful ({len(converted_audio)} bytes)")
                    return converted_audio
                else:
                    error_text = await response.text()
                    logger.error(f"RVC conversion failed ({response.status}): {error_text}")
                    # Return original audio if RVC fails
                    return audio_blob
                    
    except Exception as e:
        logger.exception(f"Error in RVC conversion: {e}")
        # Return original audio if RVC fails
        return audio_blob

# Queue Monitoring Endpoints
async def get_queue_status(request: web.Request) -> web.Response:
    """Get current queue status and metrics for optimized pipeline."""
    await initialize_queue_system()
    
    queue_status = {
        'main_queue_size': audio_processing_queue.qsize(),
        'rvc_queue_size': rvc_queue.qsize() if rvc_queue else 0,
        'max_queue_size': 50,
        'main_queue_full': audio_processing_queue.full(),
        'main_queue_empty': audio_processing_queue.empty(),
        'max_concurrent_preprocessing': max_concurrent_preprocessing,
        'max_concurrent_rvc': max_concurrent_requests,
        'available_preprocessing_slots': preprocessing_semaphore.value if preprocessing_semaphore else 0,
        'available_rvc_slots': processing_semaphore.value if processing_semaphore else 0,
        'total_processed_requests': getattr(get_queue_status, 'processed_count', 0),
        'server_status': 'healthy',
        'pipeline_mode': 'optimized_dual_stage'
    }
    
    return web.json_response(queue_status)

async def get_queue_health(request: web.Request) -> web.Response:
    """Health check endpoint for queue system."""
    await initialize_queue_system()
    
    health_status = {
        'status': 'healthy',
        'queue_initialized': audio_processing_queue is not None,
        'semaphore_initialized': processing_semaphore is not None,
        'queue_size': audio_processing_queue.qsize() if audio_processing_queue else 0,
        'available_processing_slots': processing_semaphore.value if processing_semaphore else 0,
        'timestamp': time.time()
    }
    
    # Simple health check
    if audio_processing_queue is None or processing_semaphore is None:
        health_status['status'] = 'unhealthy'
        return web.json_response(health_status, status=503)
    
    return web.json_response(health_status)

def ensure_components() -> None:
    """Initialize heavy components once (lazy)."""
    global recognizer, translator
    if recognizer is None:
        logger.info("Loading SpeechRecognizer (model=%s, device=%s)", settings.DEVICE)
        recognizer = SpeechRecognizer(settings.TRANSLATION_TARGET_LANGUAGE, settings.DEVICE,settings.MODEL)
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

async def process_audio(request: web.Request) -> web.Response:
    """Process audio: speech-to-text, translate, TTS, and RVC using queue system."""
    await initialize_queue_system()  # Ensure queue is initialized
    
    try:
        # Parse input JSON
        data = await request.json()
        audio_blob_b64 = data.get('audio_blob')
        source_lang = data.get('source_lang', 'auto')  # auto-detect source language
        target_lang = data.get('target_lang', 'ja')

        if not audio_blob_b64:
            return web.Response(status=400, text='Missing audio_blob parameter')

        # Decode Base64 audio blob
        audio_blob = base64.b64decode(audio_blob_b64)
        
        # Generate unique request ID
        request_id = f"req_{int(time.time() * 1000)}_{id(request)}"
        
        # Check queue capacity
        if audio_processing_queue.full():
            logger.warning(f"Queue full, rejecting request {request_id}")
            return web.Response(
                status=503, 
                text='Server busy. Audio processing queue is full. Please try again later.'
            )
        
        # Create request data with future for async result
        future = asyncio.Future()
        request_data = {
            'id': request_id,
            'audio_blob': audio_blob,
            'source_lang': source_lang,
            'target_lang': target_lang,
            'future': future,
            'start_time': time.time()
        }
        
        # Add to queue
        await audio_processing_queue.put(request_data)
        queue_size = audio_processing_queue.qsize()
        logger.info(f"Request {request_id} queued (queue_size={queue_size}, target_lang={target_lang})")
        
        # Wait for processing to complete
        result = await future
        
        # Check for errors in processing
        if 'error' in result:
            return web.Response(status=result.get('status', 500), text=result['error'])
        
        # Return successful result
        return web.json_response(result)

    except asyncio.TimeoutError:
        return web.Response(status=408, text='Request timeout')
    except Exception as e:
        logger.exception("Error in process_audio API")
        return web.Response(status=500, text=f"Internal Server Error: {e}")

async def convert_status(request: web.Request) -> web.Response:
    """Check status of a queued convert request."""
    try:
        # Get request ID from query parameters
        request_id = request.query.get('request_id')
        if not request_id:
            return web.json_response({
                'error': 'Missing request_id parameter'
            }, status=400)
        
        # Check if we have results cached (simple in-memory cache)
        if not hasattr(convert_status, 'results_cache'):
            convert_status.results_cache = {}
        
        # Check cache for completed results
        if request_id in convert_status.results_cache:
            result = convert_status.results_cache[request_id]
            # Clean up old results (remove after retrieval)
            del convert_status.results_cache[request_id]
            return web.json_response({
                'status': 'completed',
                'request_id': request_id,
                'result': result
            })
        
        # If not in cache, request might still be processing
        current_queue_size = audio_processing_queue.qsize() if audio_processing_queue else 0
        
        return web.json_response({
            'status': 'processing',
            'request_id': request_id,
            'message': 'Request is still being processed',
            'queue_info': {
                'current_queue_size': current_queue_size,
                'estimated_remaining_seconds': current_queue_size * 12
            }
        })
        
    except Exception as e:
        logger.exception("Error in convert_status API")
        return web.json_response({
            'error': f"Internal Server Error: {e}",
            'status': 'error'
        }, status=500)

async def convert_new(request: web.Request) -> web.Response:
    """New convert endpoint with queue system and RVC integration."""
    await initialize_queue_system()  # Ensure queue is initialized
    
    try:
        # Parse input JSON
        data = await request.json()
        audio_blob_b64 = data.get('audio_blob')
        source_lang = data.get('source_lang', 'auto')  # auto-detect source language
        target_lang = data.get('target_lang', 'ja')

        if not audio_blob_b64:
            return web.Response(status=400, text='Missing audio_blob parameter')

        # Decode Base64 audio blob
        audio_blob = base64.b64decode(audio_blob_b64)
        
        # Generate unique request ID
        request_id = f"conv_{int(time.time() * 1000)}_{id(request)}"
        
        # Check queue capacity
        if audio_processing_queue.full():
            logger.warning(f"Queue full, rejecting request {request_id}")
            return web.json_response({
                'error': 'Server busy. Audio processing queue is full. Please try again later.',
                'queue_status': {
                    'queue_size': audio_processing_queue.qsize(),
                    'max_queue_size': 50,
                    'queue_full': True
                }
            }, status=503)
        
        # Create request data with future for async result
        future = asyncio.Future()
        request_data = {
            'id': request_id,
            'audio_blob': audio_blob,
            'source_lang': source_lang,
            'target_lang': target_lang,
            'future': future,
            'start_time': time.time()
        }
        
        # Add to queue
        await audio_processing_queue.put(request_data)
        queue_size = audio_processing_queue.qsize()
        logger.info(f"Request {request_id} queued (queue_size={queue_size}, target_lang={target_lang})")
        
        # Return immediate response with queue info
        return web.json_response({
            'status': 'queued',
            'request_id': request_id,
            'message': 'Request queued for processing',
            'queue_info': {
                'position': queue_size,
                'estimated_wait_seconds': queue_size * 12,  # ~12 seconds per request (pipeline + RVC)
                'queue_size': queue_size
            }
        })

    except Exception as e:
        logger.exception("Error in convert_new API")
        return web.json_response({
            'error': f"Internal Server Error: {e}",
            'status': 'error'
        }, status=500)

# ------------------------------------------------------------
# Helper Functions for Audio Processing
# ------------------------------------------------------------

async def extract_text_from_original_audio(audio_blob):
    """Extract text from audio blob using faster-whisper."""
    try:
        # Use the existing global recognizer instance
        global recognizer
        if recognizer is None:
            # Initialize recognizer if not available
            await initialize_recognizer()
            if recognizer is None:
                return "Speech recognizer not initialized", "unknown"
        
        # Use recognize_from_bytes method directly with audio blob
        result, language = recognizer.recognize_from_bytes(audio_blob)
        
        return (result if result else "No speech detected", language)
                
    except Exception as e:
        logger.exception("Error in extract_text_from_original_audio")
        return f"Speech recognition error: {e}", "unknown"

async def translate_text(text, source_lang, target_lang):
    """Translate text using the existing translator."""
    try:
        # Use the existing global translator instance
        global translator
        if translator is None:
            # Initialize translator if not available
            await initialize_translator()
            if translator is None:
                return f"Translator not initialized"
        
        # Use the translator's translate method
        translated = translator.translate(text, target_lang, source_lang)  # Note: target_lang first, then source_lang
        return translated if translated else text
                
    except Exception as e:
        logger.exception("Error in translate_text")
        return f"Translation error: {e}"

async def initialize_translator():
    """Initialize the translator if not already done."""
    global translator
    if translator is None:
        try:
            logger.info("Initializing Gemini translator")
            translator = Translator(settings.GEMINI_API_KEY)
        except Exception as e:
            logger.exception("Failed to initialize translator")
            translator = None

async def initialize_recognizer():
    """Initialize the speech recognizer if not already done."""
    global recognizer
    if recognizer is None:
        try:
            logger.info("Initializing SpeechRecognizer (model=tiny, device=%s)", settings.DEVICE)
            recognizer = SpeechRecognizer(settings.TRANSLATION_TARGET_LANGUAGE, settings.DEVICE,settings.MODEL)
        except Exception as e:
            logger.exception("Failed to initialize recognizer")
            recognizer = None

# ------------------------------------------------------------
# Application Factory
# ------------------------------------------------------------

# Application startup and cleanup handlers
async def startup_handler(app):
    """Initialize queue system on application startup."""
    logger.info("Initializing queue system on startup...")
    await initialize_queue_system()

async def cleanup_handler(app):
    """Cleanup queue system on application shutdown."""
    logger.info("Cleaning up optimized pipeline queue system...")
    # Cancel any remaining tasks
    if hasattr(cleanup_handler, 'queue_task') and not cleanup_handler.queue_task.done():
        cleanup_handler.queue_task.cancel()
        try:
            await cleanup_handler.queue_task
        except asyncio.CancelledError:
            pass
    if hasattr(cleanup_handler, 'rvc_task') and not cleanup_handler.rvc_task.done():
        cleanup_handler.rvc_task.cancel()
        try:
            await cleanup_handler.rvc_task
        except asyncio.CancelledError:
            pass

def create_app() -> web.Application:
    app = web.Application(middlewares=[cors_middleware])
    
    # Register startup and cleanup handlers
    app.on_startup.append(startup_handler)
    app.on_cleanup.append(cleanup_handler)
    
    app.router.add_get('/translate', websocket_handler)
    app.router.add_get('/health', health)
    
    # Google TTS (primary TTS service)
    app.router.add_get('/tts', tts)
    app.router.add_post('/tts', tts)
    
    # Voice listings
    app.router.add_get('/voices', voices)
    
    # Register the process_audio endpoint
    app.router.add_post('/process_audio', process_audio)
    
    # New convert endpoint with queue system
    app.router.add_post('/convert_new', convert_new)
    app.router.add_get('/convert_status', convert_status)
    
    # Queue monitoring endpoints
    app.router.add_get('/queue/status', get_queue_status)
    app.router.add_get('/queue/health', get_queue_health)
    
    # Pre-flight CORS for endpoints
    app.router.add_options('/tts', tts)
    app.router.add_options('/voices', voices)
    app.router.add_options('/process_audio', process_audio)
    app.router.add_options('/convert_new', convert_new)
    app.router.add_options('/convert_status', convert_status)
    
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

