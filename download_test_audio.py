import os
import urllib.request
import zipfile

# Create audio directory if it doesn't exist
os.makedirs("audio", exist_ok=True)

print("Downloading sample audio files...")
# Common Creative sample audio from Mozilla Voice dataset
url = "https://github.com/mozilla/DeepSpeech/raw/master/data/smoke_test/LDC93S1.wav"
sample_file = os.path.join("audio", "english_sample.wav")

try:
    print(f"Downloading from {url}...")
    urllib.request.urlretrieve(url, sample_file)
    print(f"Sample audio file downloaded to {sample_file}")
    
    print("\nDownloaded audio files:")
    for file in os.listdir("audio"):
        print(f"- {file}")
        
    print("\nYou can now run 'python manual_test.py' to test both translation and speech recognition.")
    
except Exception as e:
    print(f"Error downloading audio file: {e}")
    print("Please manually download a .wav file to the 'audio' directory to test speech recognition.")
