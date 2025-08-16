// process_audio_script.js - Audio Translation with Sequential Playback

// ------------------------------------------------------------
// Global Variables
// ------------------------------------------------------------
let mediaRecorder;
let audioChunks = [];
let mediaStream;
let recording = false;
let recordStartTime = null;

// Audio analysis variables
let audioContext, analyser, microphone, javascriptNode;

// Voice Activity Detection (VAD) constants and state
const MAX_RECORDING_TIME = 7000; // 7s hard segment cap
let waitForNextSilenceAfterMax = false;
let noiseRMS = 0.005; // adaptive noise floor estimate
let lastSpeechTime = 0;
const SILENCE_HOLD_MS = 150; // silence threshold duration
let pendingSilenceStart = null;

// Legacy threshold variables (for UI compatibility)
var startThreshold = 5;
var stopThreshold = 35;
let silenceTime = 200;
let stopStartTime = null;
const MIN_RECORDING_TIME = 3000;

// Audio playback queue for sequential audio playback
let audioQueue = [];
let isPlayingAudio = false;

// ------------------------------------------------------------
// Audio Recording Functions
// ------------------------------------------------------------
function startRecording() {
    if (mediaStream) {
        initializeMediaRecorder(mediaStream);
    } else {
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(stream => {
                mediaStream = stream;
                initializeMediaRecorder(stream);
            })
            .catch(error => {
                console.error("Error accessing the microphone:", error);
                error_message("Error accessing the microphone: " + error);
            });
    }
}

function stopRecording() {
    if (mediaRecorder) {
        mediaRecorder.stop();
    }
}

function on_start_recording() {
    document.getElementById('start').disabled = true;
    document.getElementById('stop').disabled = false;
}

function on_stop_recording() {
    document.getElementById('start').disabled = false;
    document.getElementById('stop').disabled = true;
    // Reset max-wait state
    waitForNextSilenceAfterMax = false;
    pendingSilenceStart = null;
}

function initializeMediaRecorder(stream) {
    updateVolume(stream);

    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = event => {
        audioChunks.push(event.data);
    };
    mediaRecorder.onstop = () => {
        let audioBlob = new Blob(audioChunks, { type: 'audio/wav' });
        processAudio(audioBlob);
        audioChunks = [];
        on_stop_recording();
    };
    mediaRecorder.start();
    on_start_recording();
}

// ------------------------------------------------------------
// Audio Analysis and Voice Activity Detection
// ------------------------------------------------------------
function updateVolume(stream) {
    audioContext = new AudioContext();
    analyser = audioContext.createAnalyser();
    microphone = audioContext.createMediaStreamSource(stream);
    javascriptNode = audioContext.createScriptProcessor(2048, 1, 1);

    analyser.smoothingTimeConstant = 0.8;
    analyser.fftSize = 1024;

    microphone.connect(analyser);
    analyser.connect(javascriptNode);
    javascriptNode.connect(audioContext.destination);
    
    javascriptNode.onaudioprocess = function() {
        var freqArray = new Uint8Array(analyser.frequencyBinCount);
        analyser.getByteFrequencyData(freqArray);
        var values = 0;
        for (var i = 0; i < freqArray.length; i++) values += freqArray[i];
        var average = values / freqArray.length; // legacy average magnitude

        // Time-domain RMS for Voice Activity Detection
        let timeData = new Uint8Array(analyser.fftSize);
        analyser.getByteTimeDomainData(timeData);
        let sumSq = 0;
        for (let i = 0; i < timeData.length; i++) {
            let centered = (timeData[i] - 128) / 128.0; // [-1,1]
            sumSq += centered * centered;
        }
        let rms = Math.sqrt(sumSq / timeData.length); // 0..1 approx

        // Adaptive noise floor update
        const speechMargin = 0.015; // margin above noise to count as speech
        if (!recording || rms < noiseRMS + speechMargin * 2) {
            noiseRMS = noiseRMS * 0.95 + rms * 0.05; // slow adapt
        }
        // Clamp very low noise
        if (noiseRMS < 0.001) noiseRMS = 0.001;

        // Derived thresholds
        const speechThreshold = noiseRMS + speechMargin;
        const silenceThreshold = noiseRMS + speechMargin * 0.4;

        const isSpeech = rms > speechThreshold;
        const isSilence = rms < silenceThreshold;
        const now = Date.now();

        if (isSpeech) {
            lastSpeechTime = now;
            pendingSilenceStart = null; // reset potential silence window
        } else if (isSilence) {
            if (!pendingSilenceStart) pendingSilenceStart = now;
        } else {
            // mid region: neither definite speech nor silence
            pendingSilenceStart = null;
        }

        processRecordingState(rms, isSpeech, isSilence, now);

        // Update UI elements
        updateVolumeUI(average, rms);
    }
}

function processRecordingState(rms, isSpeech, isSilence, now) {
    let status = '';

    // Start condition (speech onset)
    if (!recording && isSpeech) {
        startRecording();
        recording = true;
        recordStartTime = now;
        lastSpeechTime = now;
        status += '↑';
    }

    if (recording) {
        const elapsed = now - recordStartTime;
        // If we exceeded max and haven't flagged waiting yet, set wait flag
        if (elapsed > MAX_RECORDING_TIME && !waitForNextSilenceAfterMax) {
            waitForNextSilenceAfterMax = true;
            status += ' [MAX>7s waiting silence]';
        }
        // Normal early-stop logic (before hitting max)
        if (!waitForNextSilenceAfterMax) {
            if (pendingSilenceStart) {
                const silenceDur = now - pendingSilenceStart;
                if (silenceDur > silenceTime && (now - recordStartTime) >= MIN_RECORDING_TIME) {
                    stopRecording();
                    recording = false;
                    status += ' ↓(silence stop)';
                }
            }
        } else {
            // After exceeding max: wait for a clear silence dip
            if (pendingSilenceStart) {
                const silenceDur = now - pendingSilenceStart;
                if (silenceDur > SILENCE_HOLD_MS) {
                    stopRecording();
                    recording = false;
                    status += ' ↓(post-max stop)';
                }
            }
        }
    }

    setStatusText(status);
}

function updateVolumeUI(average, rms) {
    if (document.getElementById('volume')) {
        document.getElementById('volume').value = average;
    }
    if (document.getElementById('volume-level-value')) {
        document.getElementById('volume-level-value').innerHTML = 
            average.toFixed(2) + ` / RMS:${rms.toFixed(3)} N:${noiseRMS.toFixed(3)}`;
    }
}

function setStatusText(text) {
    const el = document.getElementById('status-text');
    if (el) el.textContent = text;
}

// ------------------------------------------------------------
// Audio Processing and API Functions
// ------------------------------------------------------------
async function processAudio(audioBlob) {
    try {
        addMessage("• Processing audio...");
        
        const response = await fetch('http://localhost:9090/process_audio', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                audio_blob: await blobToBase64(audioBlob),
                source_lang: 'auto', // auto-detect
                target_lang: 'ja'    // translate to Japanese
            })
        });

        if (!response.ok) {
            console.error('Error processing audio:', response.statusText);
            error_message(`Error processing audio: ${response.statusText}`);
            return;
        }

        const result = await response.json();
        console.log('Processed audio:', result);
        
        // Display the results
        addMessage(`- Original: "${result.original_text}" (${result.detected_language})`);
        addMessage(`- Translated: "${result.translated_text}"`);
        
        // Add translated audio to queue for sequential playback
        if (result.translated_audio_blob) {
            addAudioToQueue(result.translated_audio_blob);
        }
        
    } catch (error) {
        console.error('Error processing audio:', error);
        error_message(`Error: ${error.message}`);
    }
}

// ------------------------------------------------------------
// Sequential Audio Playback System
// ------------------------------------------------------------
function addAudioToQueue(base64Audio) {
    audioQueue.push(base64Audio);
    if (!isPlayingAudio) {
        playNextAudio();
    }
}

async function playNextAudio() {
    if (audioQueue.length === 0) {
        isPlayingAudio = false;
        return;
    }

    isPlayingAudio = true;
    const base64Audio = audioQueue.shift();
    
    try {
        addMessage("• Playing translated audio...");
        await playAudioFromBase64(base64Audio);
    } catch (error) {
        console.error('Error playing audio:', error);
        error_message(`Audio playback error: ${error.message}`);
    } finally {
        // Play next audio in queue after current one finishes
        setTimeout(() => playNextAudio(), 100); // Small delay between audio clips
    }
}

function playAudioFromBase64(base64Audio) {
    return new Promise((resolve, reject) => {
        try {
            // Convert base64 to blob
            const audioData = atob(base64Audio);
            const audioArray = new Uint8Array(audioData.length);
            for (let i = 0; i < audioData.length; i++) {
                audioArray[i] = audioData.charCodeAt(i);
            }
            const audioBlob = new Blob([audioArray], { type: 'audio/mpeg' });
            
            // Create and play audio
            const audioUrl = URL.createObjectURL(audioBlob);
            const audio = new Audio(audioUrl);
            
            audio.onended = () => {
                URL.revokeObjectURL(audioUrl);
                resolve();
            };
            
            audio.onerror = (error) => {
                URL.revokeObjectURL(audioUrl);
                reject(error);
            };
            
            audio.play().catch(reject);
            
        } catch (error) {
            reject(error);
        }
    });
}

// ------------------------------------------------------------
// Utility Functions
// ------------------------------------------------------------
async function blobToBase64(blob) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onloadend = () => resolve(reader.result.split(',')[1]);
        reader.onerror = reject;
        reader.readAsDataURL(blob);
    });
}

function addMessage(message) {
    const messagesDiv = document.getElementById('messages');
    messagesDiv.innerHTML += `<div>${message}</div>`;
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function error_message(message) {
    console.error(message);
    addMessage(`<span style="color: red;">• ERROR: ${message}</span>`);
}

function clear_messages() {
    const el = document.getElementById('messages');
    if (el) el.innerHTML = '';
}

function save_messages() {
    var htmlContent = document.getElementById('messages')?.innerHTML || '';
    var textContent = htmlContent.replace(/<\/div>|<\/p>|<br>/gi, '\n').replace(/<[^>]+>/g, '');
    var blob = new Blob([textContent], {type: 'text/plain'});
    var anchor = document.createElement('a');
    anchor.download = 'process_audio_messages.txt';
    anchor.href = window.URL.createObjectURL(blob);
    anchor.click();
    window.URL.revokeObjectURL(anchor.href);
}

// ------------------------------------------------------------
// UI Event Handlers and Settings
// ------------------------------------------------------------
function loadSilenceTime() {
    const savedSilenceTime = localStorage.getItem('silenceTime');
    if (savedSilenceTime) {
        silenceTime = parseInt(savedSilenceTime, 10);
        const inp = document.getElementById('silence-time-input');
        if (inp) inp.value = silenceTime;
    }
}

function loadSilenceThreshold() {
    const savedSilenceThreshold = localStorage.getItem('silenceThreshold');
    if (savedSilenceThreshold) {
        startThreshold = parseInt(savedSilenceThreshold, 10);
        setSliderValue(startThreshold);
    }
}

function setSliderValue(value) {
    const el = document.getElementById('recording-level-slider');
    if (el) el.value = value;
    const valEl = document.getElementById('recording-level-value');
    if (valEl) valEl.textContent = value;
    startThreshold = value;
}

// ------------------------------------------------------------
// Event Listeners Setup
// ------------------------------------------------------------
document.addEventListener('DOMContentLoaded', () => {
    // Button event listeners
    document.getElementById('start')?.addEventListener('click', startRecording);
    document.getElementById('stop')?.addEventListener('click', stopRecording);
    document.getElementById('clear')?.addEventListener('click', clear_messages);
    document.getElementById('save')?.addEventListener('click', save_messages);
    
    // Slider event listeners
    const recordingSlider = document.getElementById('recording-level-slider');
    if (recordingSlider) {
        recordingSlider.addEventListener('input', function() {
            const level = this.value;
            document.getElementById('recording-level-value').textContent = level;
            startThreshold = level;
        });
    }
    
    const stopSlider = document.getElementById('stop-level-slider');
    if (stopSlider) {
        stopSlider.addEventListener('input', function() {
            const level = this.value;
            document.getElementById('stop-level-value').textContent = level;
            stopThreshold = level;
        });
    }
    
    // Settings save button
    document.getElementById('save-silence-time')?.addEventListener('click', function() {
        const inputVal = document.getElementById('silence-time-input')?.value;
        if (inputVal) {
            silenceTime = parseInt(inputVal, 10);
            localStorage.setItem('silenceTime', silenceTime);
            addMessage('• Silence time saved: ' + silenceTime + 'ms');
        }
        const inputVal2 = document.getElementById('recording-level-slider')?.value;
        if (inputVal2) {
            startThreshold = parseInt(inputVal2, 10);
            localStorage.setItem('silenceThreshold', startThreshold);
            addMessage(' Recording threshold saved: ' + startThreshold);
        }
    });
    
    // Load saved settings
    loadSilenceTime();
    loadSilenceThreshold();
    
    addMessage('• Audio Translation System Ready');
});

// Cleanup on page unload
window.onbeforeunload = () => {
    if (mediaStream) {
        const tracks = mediaStream.getTracks();
        tracks.forEach(track => track.stop());
    }
};
