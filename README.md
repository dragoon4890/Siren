# MITB_25LAI04MITB_Live_translation_with_emotions
SRIB-PRISM Program

## STT Module

- Uses Faster Whisper , to get realtime Speech to text data
- Faster Whisper features many modules , including tiny , large-v2
- Tested this locally with cpu , where tiny was 64 times faster than large model although slightly inaccurate

- Combined this with Google Gemini (AI translation) to create a real-time translator

- It works by detecting breaks , then processing , as a result , if there is almost little to no break , it will take a while to process  ( planning to change it to chunks of equal size)

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
