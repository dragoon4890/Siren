// Removed client TTS module import

let mediaRecorder;
let audioChunks = [];
let socket;
let mediaStream; // グローバルスコープに追加

// --- New VAD / segmentation constants & state (added) ---
const MAX_RECORDING_TIME = 7000; // 7s hard segment cap before waiting for next silence dip
let waitForNextSilenceAfterMax = false; // once max exceeded, wait until silence to stop
let noiseRMS = 0.005; // adaptive noise floor estimate
let lastSpeechTime = 0; // track last time speech detected
const SILENCE_HOLD_MS = 150; // how long rms must stay below silence threshold to count as silence (after max)
let pendingSilenceStart = null; // timestamp when potential silence started

let url = 'ws://localhost:9090/translate';
let useSSL = false; // Set to false to use non-SSL connection
let urlSSL = 'wss://localhost:9090/translate';

var startThreshold = 5; // 録音を開始するボリュームレベル (legacy)
var stopThreshold = 35; // 録音を停止するボリュームレベル (legacy)
let silenceTime = 200; // 静けさが続くべきミリ秒数 (legacy)
let recording = false;
let stopStartTime = null; // legacy silence tracking
let recordStartTime = null;
// 最低録音時間
const MIN_RECORDING_TIME = 3000;

function startRecording() {

    if (mediaStream) {
        initializeMediaRecorder(mediaStream);
    } else {
        navigator.mediaDevices.getUserMedia({ audio: true })
            .then(stream => {
                mediaStream = stream; // mediaStream を保存
                initializeMediaRecorder(stream);
            })
            .catch(error => {
                console.error("Error accessing the microphone:", error);
                error_message("Error accessing the microphone: " + error);
            });
    }

}
function on_start_recording(){
    document.getElementById('start').disabled = true;
    document.getElementById('stop').disabled = false;
}
function on_stop_recording(){
    document.getElementById('start').disabled = false;
    document.getElementById('stop').disabled = true;
    // reset max-wait state
    waitForNextSilenceAfterMax = false;
    pendingSilenceStart = null;
}
function log_message(message){
    console.log(message);
    addMessage(message);
    var obj = document.getElementById("messages");
    obj.scrollTop = obj.scrollHeight;
}

function error_message(message){
    console.error(message);
    addMessageWithColor(message,"red");
}

function stopRecording() {
    if (mediaRecorder) {
        mediaRecorder.stop();
    }
}

function setupWebSocket() {
    if(useSSL)
        socket = new WebSocket(urlSSL);
    else
        socket = new WebSocket(url);

    socket.onopen = function(event) {
        addMessage("WebSocket is open now.");
    };

    socket.onmessage = function(event) {
        console.log("Message from server:", event.data);
        addMessage(event.data);
    };

    socket.onclose = function(event) {
        addMessage("WebSocket is closed now.");
    };

    socket.onerror = function(event) {
        addMessage("WebSocket error observed:", event);
    };
}

function addMessage(message) {
    const messagesDiv = document.getElementById('messages');
    messagesDiv.innerHTML += `<div>${message}</div>`;
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
    maybeSpeakServerTTS(message);
}
function addMessageWithColor(message,color){
    const messagesDiv = document.getElementById('messages');
    messagesDiv.innerHTML += `<div style="color:${color}">${message}</div>`;
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

function sendData(data) {

    if (socket && socket.readyState === WebSocket.OPEN) {
        socket.send(data);
    } else {
        console.error("WebSocket is not open. Data not sent.");
    }

}

// Event listeners for buttons
document.addEventListener('DOMContentLoaded', (event) => {
    document.getElementById('start').addEventListener('click', startRecording);
    document.getElementById('stop').addEventListener('click', stopRecording);
    document.getElementById('clear').addEventListener('click', clear_messages);
    document.getElementById('save').addEventListener('click', save_messages);
    setupWebSocket();
});

let audioContext, analyser, microphone, javascriptNode;

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

        // NEW: time-domain RMS for simple VAD
        let timeData = new Uint8Array(analyser.fftSize);
        analyser.getByteTimeDomainData(timeData);
        let sumSq = 0;
        for (let i=0;i<timeData.length;i++) {
            let centered = (timeData[i]-128)/128.0; // [-1,1]
            sumSq += centered*centered;
        }
        let rms = Math.sqrt(sumSq / timeData.length); // 0..1 approx

        // adaptive noise floor update (only adapt when below modest speech margin)
        const speechMargin = 0.015; // margin above noise to count as speech
        if (!recording || rms < noiseRMS + speechMargin*2) {
            noiseRMS = noiseRMS*0.95 + rms*0.05; // slow adapt
        }
        // clamp very low noise
        if (noiseRMS < 0.001) noiseRMS = 0.001;

        // Derived thresholds
        const speechThreshold = noiseRMS + speechMargin;
        const silenceThreshold = noiseRMS + speechMargin*0.4; // below this consider silence

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

        // UI updates (reuse existing volume bar with legacy average)
        document.getElementById('volume').value = average;
        document.getElementById('volume-level-value').innerHTML = average.toFixed(2) + ` / RMS:${rms.toFixed(3)} N:${noiseRMS.toFixed(3)}`;

        // COMMENTED OUT legacy logic call for rollback
        // checkVolumeLevel();
    }
}
function getVolumeLevel() {
    return document.getElementById('volume').value;
}

// --- New function: handles start/stop with 7s max + wait-for-next-silence ---
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
        // Normal early-stop logic (before hitting max) using legacy min length & silence hold
        if (!waitForNextSilenceAfterMax) {
            // If silence sustained (pendingSilenceStart) beyond configured silenceTime and min length satisfied
            if (pendingSilenceStart) {
                const silenceDur = now - pendingSilenceStart;
                if (silenceDur > silenceTime && (now - recordStartTime) >= MIN_RECORDING_TIME) {
                    stopRecording();
                    recording = false;
                    status += ' ↓(silence stop)';
                }
            }
        } else {
            // After exceeding max: wait for a clear silence dip (short SILENCE_HOLD_MS)
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

/*
==================== LEGACY LOGIC (commented for rollback) ====================
function checkVolumeLevel() {
    let volumeLevel = getVolumeLevel();
    let status = '';
    if (volumeLevel < stopThreshold) {
        status += "↓";
        if (!stopStartTime) stopStartTime = Date.now();
        var laps = Date.now() - stopStartTime;
        if (laps > silenceTime) {
            if (recording) {
                const recordTime = Date.now() - recordStartTime;
                if (recordTime < MIN_RECORDING_TIME) return;
                stopRecording();
                recording = false;
            }
        } else {
            if(laps > 0) status = status + "silenceTime:" + laps + "ms";
        }
    } else {
        stopStartTime = null;
    }
    if(volumeLevel > startThreshold) {
        status += "↑";
        if (!recording) {
            startRecording();
            recording = true;
            recordStartTime = Date.now();
        }
    }
    setStatusText(status);
}
================== END LEGACY LOGIC ==================
*/

// Sliders (legacy UI still retained for rollback / thresholds display)
document.addEventListener('DOMContentLoaded', function () {
    const slider = document.getElementById('recording-level-slider');
    if (slider) {
        slider.addEventListener('input', function() {
            const level = slider.value;
            document.getElementById('recording-level-value').textContent = level;
            startThreshold = level; // legacy var
        });
    }
});

document.addEventListener('DOMContentLoaded', function () {
    const slider = document.getElementById('stop-level-slider');
    if (slider) {
        slider.addEventListener('input', function() {
            const level = slider.value;
            document.getElementById('stop-level-value').textContent = level;
            stopThreshold = level; // legacy var
        });
    }
});
function setSliderValue(value) {
    const el = document.getElementById('recording-level-slider');
    if (el) el.value = value;
    const valEl = document.getElementById('recording-level-value');
    if (valEl) valEl.textContent = value;
    startThreshold = value;
}
function setStatusText(text) {
    const el = document.getElementById('status-text');
    if (el) el.textContent = text;
}

function loadSilenceTime() {
    const savedSilenceTime = localStorage.getItem('silenceTime');
    if (savedSilenceTime) {
        silenceTime = parseInt(savedSilenceTime, 10);
        const inp = document.getElementById('silence-time-input');
        if (inp) inp.value = silenceTime;
    }
}
function loadSilenceThreshold(){
    const savedSilenceThreshold = localStorage.getItem('silenceThreshold');
    if (savedSilenceThreshold) {
        startThreshold = parseInt(savedSilenceThreshold, 10);
        setSliderValue(startThreshold);
    }
}

document.getElementById('save-silence-time')?.addEventListener('click', function() {
    const inputVal = document.getElementById('silence-time-input')?.value;
    if (inputVal) {
        silenceTime = parseInt(inputVal, 10);
        localStorage.setItem('silenceTime', silenceTime);
        log_message('静寂時間が保存されました: ' + silenceTime + 'ミリ秒');
    }
    const inputVal2 = document.getElementById('recording-level-slider')?.value;
    if (inputVal2) {
        startThreshold = parseInt(inputVal2, 10);
        localStorage.setItem('silenceThreshold', startThreshold);
        log_message('静寂閾値が保存されました: ' + startThreshold);
    }
});

function clear_messages(){
    const el = document.getElementById('messages');
    if (el) el.innerHTML = '';
}

function save_messages(){
    var htmlContent = document.getElementById('messages')?.innerHTML || '';
    var textContent = htmlContent.replace(/<\/div>|<\/p>|<br>/gi, '\n').replace(/<[^>]+>/g, '');
    var blob = new Blob([textContent], {type: 'text/plain'});
    var anchor = document.createElement('a');
    anchor.download = 'messages.txt';
    anchor.href = window.URL.createObjectURL(blob);
    anchor.click();
    window.URL.revokeObjectURL(anchor.href);
}

window.onload = function() {
    log_message("onload")
    loadSilenceTime();
    loadSilenceThreshold();
};

// --- Server-side TTS playback (parse line & fetch /tts) ---
function parseLine(line){
    const regex = /^(\d{4}\/\d{2}\/\d{2} \d{2}:\d{2}:\d{2}) \(([A-Za-z-]+)\)(.*)\(([^()]*)\)$/;
    const m = line.trim().match(regex);
    if(!m) return null;
    console.log("Bombaclat ",m , regex)
    return { detected: m[2], original: m[3].trim(), translation: m[4].trim() };
}
async function maybeSpeakServerTTS(line){
    const p = parseLine(line);
    if(!p || !p.translation) return;
    try{
    const base = 'http://localhost:9090';
    const url = `${base}/tts?text=${encodeURIComponent(p.translation)}&lang=${encodeURIComponent(p.detected.toLowerCase() === 'ja' ? 'en' : 'ja')}`;
    const res = await fetch(url);
        if(!res.ok) return;
        const blob = await res.blob();
        const audioUrl = URL.createObjectURL(blob);
        const audio = new Audio(audioUrl);
        audio.play().finally(()=> URL.revokeObjectURL(audioUrl));
    }catch(e){ console.warn('TTS fetch error', e); }
}

function initializeMediaRecorder(stream) {
    updateVolume(stream);

    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = event => {
        audioChunks.push(event.data);
    };
    mediaRecorder.onstop = () => {
        let audioBlob = new Blob(audioChunks, { type: 'audio/wav' }); // NOTE: container may actually be webm; kept for backward compatibility
        sendData(audioBlob);
        audioChunks = [];
        on_stop_recording();
    };
    mediaRecorder.start();
    on_start_recording();
}

// ページを離れるときにストリームを停止する
window.onbeforeunload = () => {
    log_message("onbeforeunload")
    if (mediaStream) {
        const tracks = mediaStream.getTracks();
        tracks.forEach(track => track.stop());
    }
};