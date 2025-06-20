# Faster Whisper Server

Fork from https://github.com/takatronix/faster_whisper_server , tweaked it to work with gemini and added in memory handling IOBytes to not create a new file every time 

[*faster*-*whisper*](https://github.com/guillaumekln/faster-whisper) is a faster version of OpenAI's speech recognition model Whisper. It works quickly even on CPU, and with GPU it's even faster for real-time speech recognition with good accuracy.

Combined this with Google Gemini (AI translation) to create a real-time translator 

The client side is made with javascript, detects breaks in the audio, sends the audio data to the server, and displays the recognition and translation results.






## Server Startup Method

```
python websocket_server.py
```

Works on CPU, but GPU with CUDA will provide faster results if available. Run on the same computer as the client. (Only tested with localhost connection)

### Testing and Verification

You can test the translation and speech recognition components separately:

```
python manual_test.py
```

This will run tests for both Gemini translation and speech recognition using sample audio files from the `audio` directory.



## Configuration

Configure your Gemini API key in settings.py. You can also specify the target language.

```
DEVICE = "cpu"  # or "cuda" if using GPU
GEMINI_API_KEY = "Your Gemini API Key"  # Gemini API key
TRANSLATION_TARGET_LANGUAGE = "JA" # Language code of the target language (e.g. 'en', 'ja', 'es')
TRANSLATION_SOURCE_LANGUAGE = "EN" # Source language code (e.g. 'en', 'ja', 'es')
```

By default, the system uses the "tiny" model (fastest, smallest size) for speech recognition. For higher accuracy, you can change `"tiny"` to `"base"`, `"small"`, `"medium"`, or `"large-v3"` in `speech_recognizer.py`.



## Execution Method

Open **/client/index.html** in a web browser. Since the connection destination is fixed to localhost, run on the same computer as the server.
Once connected to the server, it will automatically continue translating the sound from the microphone.

![image-20231105041802180](assets/image-20231105041802180.png)

When the volume is above Start Level, it records, and when the volume is below Stop Level and Silent Detection (milliseconds) has elapsed, it determines that the voice has been interrupted, and the data is sent to Recognition & Translation. Try changing the setting while watching the volume level.



### StartRecording button

Press this button once for the first time to allow authorization, and once the voice is recognized, it will automatically continue translating.

### StopRecording button

Press this button when you want to stop recording and start translation.

### Volume Level

Current microphone input level.

### Start Level

Start recording automatically when the volume level is higher than this level.

### Stop Level

When the volume level becomes lower than this level, recording will automatically stop and recognition will begin.

### Clear Button

Clear history.

### Save button

Download the translated text.




## License

MIT
