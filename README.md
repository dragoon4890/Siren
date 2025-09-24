# MITB_25LAI04MITB_Live_translation_with_emotions
SRIB-PRISM Program

## System Architecture

### High-Level Overview
The system implements an audio translation pipeline with voice cloning and emotion preservation using the following core components:

- **Client Side**: Involves audio device processing, implementation of a queue management system, and features like Silence Detection (VAD)

- **Server**: Speech-to-Text (STT module), Text-to-Text (Translation Module), Text-to-Speech Module (TTS), and Seed Voice Conversion (RVC augmented with audio inputs)

    ### STT
    - Uses OpenAI's [Faster Whisper](https://github.com/guillaumekln/faster-whisper) implementation to get almost real-time transcription.

    ### Translation Module
    - Uses LLMs instead of traditional translation services, as LLMs are very good for languages where the meaning changes with context.

    ### TTS
    - This implementation uses Google Translate to get a neutral voice (no particular emotion).

    ### [Seed-VC](https://github.com/Plachtaa/seed-vc)
    - Uses the original audio as a reference and the neutral translated voice as the source to add emotions and clone voice characteristics from the speaker.

- This architecture leads to very low coupling, as the modules can be swapped as per requirements and audio conversion isn't bound by language. Theoretically and practically, any language can be converted to any other language we want.

- Main bottleneck is the Seed-VC implementation, which requires a powerful GPU.

### Component Flow
1. **Audio Capture**: Browser captures microphone input with [VAD](https://en.wikipedia.org/wiki/Voice_activity_detection)-based segmentation
2. **Speech Recognition**: [Faster-Whisper](https://github.com/guillaumekln/faster-whisper) converts audio segments to text
3. **Translation**: Google Gemini translates text to target language
4. **Text-to-Speech**: Server generates audio for translated text
5. **Voice Cloning & Emotion**: [Seed-VC (RVC)](https://github.com/Plachtaa/seed-vc) clones original speaker's voice and preserves emotions using both original audio and translated TTS as inputs
6. **Sequential Playback**: Client queues and plays voice-cloned translated audio in order

### Key Features
- **Real-time Processing**: Sub-second latency for voice activity detection
- **Adaptive [VAD](https://en.wikipedia.org/wiki/Voice_activity_detection)**: Dynamic noise floor adjustment for various environments
- **Voice Cloning**: [Seed-VC](https://github.com/Plachtaa/seed-vc) preserves original speaker's voice characteristics in translated audio
- **Emotion Preservation**: [RVC](https://en.wikipedia.org/wiki/Real-time_voice_conversion) maintains emotional context from original speech
- **Sequential Audio**: [FIFO](https://en.wikipedia.org/wiki/FIFO_(computing_and_electronics)) queue ensures proper audio playback order
- **WebSocket Communication**: Bidirectional real-time data exchange
- **Modular Architecture**: Separate services for speech, translation, TTS, and voice conversion

## Technical Innovation & Differentiation

### Real-time Processing Advantages
Unlike traditional batch-processing systems, our architecture provides:

- **Streaming Audio Processing**: True real-time translation with VAD-based segmentation
- **Adaptive Noise Floor**: Dynamic adjustment to environmental conditions (`noiseRMS = noiseRMS × 0.95 + currentRMS × 0.05`)
- **Intelligent Segmentation**: 3-7 second chunks with silence detection for optimal processing
- **Sub-second Latency**: Voice activity detection with minimal delay

### Advanced Voice Conversion
- **[Seed-VC](https://github.com/Plachtaa/seed-vc) Integration**: State-of-the-art voice conversion using dual inputs (original audio + translated TTS)
- **Emotion Preservation**: Implicit emotion transfer through voice characteristics rather than explicit emotion classification
- **Service-Based Architecture**: Standalone voice conversion service with HTTP API and model caching

### Modern Translation Pipeline
- **LLM-Powered Translation**: Uses Google Gemini for context-aware translation vs. traditional neural machine translation
- **Sequential Audio Management**: FIFO queue system ensures proper playback order with automatic memory cleanup
- **WebSocket Communication**: Real-time bidirectional data exchange for streaming applications

### Demo

English to Hindi Happy -->

https://github.ecodesamsung.com/SRIB-PRISM/MITB_25LAI04MITB_Live_translation_with_emotions/assets/36530/f8ddf200-c787-482c-95dc-15688b28edd6

Hindi to English -->

https://github.ecodesamsung.com/SRIB-PRISM/MITB_25LAI04MITB_Live_translation_with_emotions/assets/36530/4ff70ab0-522b-4ea6-88a2-21af4333f0f1

English to Hindi Sad -->

https://github.ecodesamsung.com/SRIB-PRISM/MITB_25LAI04MITB_Live_translation_with_emotions/assets/36530/9d21314e-d45f-4cd0-8682-c4f2f5b0ab7c

https://github.ecodesamsung.com/SRIB-PRISM/MITB_25LAI04MITB_Live_translation_with_emotions/assets/36530/a3e3c26d-50c0-419c-925c-20fc5b4e3d16

English to Hindi Angry -->

https://github.ecodesamsung.com/SRIB-PRISM/MITB_25LAI04MITB_Live_translation_with_emotions/assets/36530/e649d6d4-0530-44b9-ba31-503d70829b40

Demo for differences with the TTS:

Original Clip:

https://github.ecodesamsung.com/SRIB-PRISM/MITB_25LAI04MITB_Live_translation_with_emotions/assets/36530/b4f93ed2-c8b6-4e30-b172-1a42dbb8d993

Translation to Telegu with Google Translate TTS:

https://github.ecodesamsung.com/SRIB-PRISM/MITB_25LAI04MITB_Live_translation_with_emotions/assets/36530/6e2177ef-3490-4328-ab97-7445ddfb26a5

Translation to Telegu with Indic TTS:

https://github.ecodesamsung.com/SRIB-PRISM/MITB_25LAI04MITB_Live_translation_with_emotions/assets/36530/23f87228-6b8e-4361-9b61-1b53eb04f299

Original Clip:

https://github.ecodesamsung.com/SRIB-PRISM/MITB_25LAI04MITB_Live_translation_with_emotions/assets/36530/519448b6-b091-48fc-aa7a-d4f0264dad7f

Translation to Telegu with Google Translate TTS:

https://github.ecodesamsung.com/SRIB-PRISM/MITB_25LAI04MITB_Live_translation_with_emotions/assets/36530/0dbfad69-18d0-4af8-b066-fdf41aecf28b

Transaltion to Telegu with Indic TTS:

https://github.ecodesamsung.com/SRIB-PRISM/MITB_25LAI04MITB_Live_translation_with_emotions/assets/36530/364eb17b-bb34-49b3-ae41-73b000903cf5

## Setup Instructions

### 1. Environment Setup
```bash
# Copy the environment template
cp .env.example .env

# Edit .env file and add your Gemini API key
GEMINI_API_KEY=your_actual_api_key_here
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Run the Server
```bash
python websocket_server.py
```

The server will start on `http://localhost:9090`

## Techniques Used

## [VAD (Voice Activity Detection)](https://en.wikipedia.org/wiki/Voice_activity_detection) Module

### Overview
The system implements a sophisticated Voice Activity Detection system using [RMS (Root Mean Square)](https://en.wikipedia.org/wiki/Root_mean_square) analysis for real-time audio processing and automatic speech segmentation.

### Core Components

#### [RMS](https://en.wikipedia.org/wiki/Root_mean_square)-based Audio Analysis
- **[Time-domain](https://en.wikipedia.org/wiki/Time_domain) RMS calculation**: Converts audio samples to RMS values for speech detection
- **[Adaptive noise floor](https://en.wikipedia.org/wiki/Adaptive_filter)**: Dynamically adjusts to ambient noise levels using exponential smoothing
- **Speech/Silence thresholds**: Uses adaptive thresholds based on noise floor estimation

#### VAD Algorithm Features
- **Adaptive Noise Estimation**: `noiseRMS = noiseRMS * 0.95 + currentRMS * 0.05`
- **Speech Detection Threshold**: `speechThreshold = noiseRMS + speechMargin (0.015)`
- **Silence Detection Threshold**: `silenceThreshold = noiseRMS + speechMargin * 0.4`
- **Minimum Recording Time**: 3 seconds to avoid false triggers
- **Maximum Recording Time**: 7 seconds hard cap to prevent overly long segments

#### Recording State Logic
1. **Start Condition**: RMS > speechThreshold triggers recording
2. **Normal Stop**: Silence sustained for configured duration (200ms default) after minimum recording time
3. **Max Duration Stop**: After 7 seconds, waits for next silence dip (150ms) to stop
4. **Adaptive Behavior**: Adjusts to environmental noise automatically

### Configuration Parameters
- `MAX_RECORDING_TIME`: 7000ms (hard segment cap)
- `MIN_RECORDING_TIME`: 3000ms (minimum before silence detection)
- `SILENCE_HOLD_MS`: 150ms (silence duration after max time)
- `speechMargin`: 0.015 (RMS margin above noise floor for speech detection)
- `silenceTime`: 200ms (configurable silence duration for normal stops)

### Audio Processing Pipeline
1. **Real-time [RMS](https://en.wikipedia.org/wiki/Root_mean_square) Calculation**: Continuous analysis of microphone input
2. **Noise Floor Adaptation**: Updates noise baseline during non-recording periods
3. **Speech Onset Detection**: Triggers recording when speech threshold exceeded
4. **Silence Detection**: Monitors for sustained silence to end recording
5. **Automatic Segmentation**: Handles long utterances with intelligent break detection

## Audio Queue System (Sequential Playback)

### Overview
The client implements a sophisticated audio queue system for sequential playback of translated audio responses, ensuring proper ordering and smooth audio experience.

### Core Components

#### Queue Management
- **[FIFO](https://en.wikipedia.org/wiki/FIFO_(computing_and_electronics)) Queue**: First-in, first-out audio playback queue using JavaScript array
- **State Management**: Tracks playback status to prevent overlapping audio
- **Automatic Processing**: Queues are processed automatically when audio is added

#### Sequential Playback Logic
```javascript
// Audio queue state
let audioQueue = [];
let isPlayingAudio = false;

// Queue management functions
function addAudioToQueue(base64Audio)    // Adds audio to queue
async function playNextAudio()           // Processes queue sequentially  
function playAudioFromBase64(base64Audio) // Handles individual audio playback
```

#### Audio Processing Pipeline
1. **Audio Reception**: Translated audio received as [base64](https://en.wikipedia.org/wiki/Base64) from server
2. **Queue Addition**: Audio added to playback queue automatically
3. **Sequential Processing**: Queue processes one audio at a time
4. **[Base64](https://en.wikipedia.org/wiki/Base64) Conversion**: Converts base64 to audio blob for playback
5. **Cleanup**: URL objects revoked after playback completion

### Queue Features
- **Non-blocking Addition**: New audio can be queued while others are playing
- **Error Handling**: Failed audio doesn't stop the queue processing
- **Memory Management**: Automatic cleanup of audio URLs after playback
- **Status Tracking**: Visual feedback for audio playback status
- **Delay Buffer**: 100ms delay between audio clips for smooth transitions

### Integration with Translation Pipeline
- **Automatic Queuing**: All translated audio automatically enters the queue
- **User Feedback**: Visual messages indicate when audio is being played
- **Error Recovery**: Queue continues processing even if individual audio fails
