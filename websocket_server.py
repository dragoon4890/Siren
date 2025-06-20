import datetime
from aiohttp import web
import settings
from speech_recognizer import SpeechRecognizer
from translator import Translator
import ssl

recognizer = SpeechRecognizer(settings.TRANSLATION_TARGET_LANGUAGE, settings.DEVICE)
translator = Translator(settings.GEMINI_API_KEY)


async def websocket_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    print("websocket connection open")
    await ws.send_str("connected")
    async for msg in ws:
        if msg.type == web.WSMsgType.BINARY:
            print("Received audio data")
            received_time = datetime.datetime.now()
            
            # Process audio data completely in-memory (no disk I/O)
            print("Processing audio data in-memory (no temporary files)")
            result, lang = recognizer.recognize_from_bytes(msg.data)

            if result == "":
                continue
                
            # Translate with Gemini
            translated = ""
            if lang == "ja":
                translated = translator.translate(result, settings.TRANSLATION_SOURCE_LANGUAGE, "")
            else:
                translated = translator.translate(result, settings.TRANSLATION_TARGET_LANGUAGE, "")

            ret = "(" + lang + ")" + result + "(" + translated + ")"
            ret = f"{received_time.strftime('%Y/%m/%d %H:%M:%S')} {ret}"

            print(ret)
            await ws.send_str(ret)

    return ws


# Processing is now completely in-memory with no disk I/O
print("Starting server with pure in-memory audio processing - no files saved or temporary files created.")

app = web.Application()
app.router.add_get('/translate', websocket_handler)

if settings.USE_SSL:
    ssl_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_context.load_cert_chain(settings.SSL_CERT, settings.SSL_KEY)
    web.run_app(app, host='0.0.0.0', port=settings.PORT_NO, ssl_context=ssl_context)
else:
    web.run_app(app, host='0.0.0.0', port=settings.PORT_NO)

