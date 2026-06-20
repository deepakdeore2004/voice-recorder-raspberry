import os
import time
import wave
import collections
import numpy as np
import pyaudio
import webrtcvad
import noisereduce as nr
from scipy.signal import resample_poly  # Added for hardware rate conversion

# --- CONFIGURATION ---
FORMAT = pyaudio.paInt16
CHANNELS = 1

# Hardware config: Read at 48kHz which cheap USB mics natively love
HARDWARE_RATE = 48000 
# VAD config: WebRTC strictly needs 16kHz
VAD_RATE = 16000      

FRAME_DURATION = 30   # ms per frame
# Calculate chunk sizes based on both rates
HARDWARE_CHUNK = int(HARDWARE_RATE * FRAME_DURATION / 1000)
VAD_CHUNK = int(VAD_RATE * FRAME_DURATION / 1000)

VAD_AGGRESSIVENESS = 3 
SILENCE_TIMEOUT = 2.0 

# Initialize VAD and PyAudio
vad = webrtcvad.Vad(VAD_AGGRESSIVENESS)
audio_interface = pyaudio.PyAudio()

# --- DYNAMIC HARDWARE LOOKUP ---
mic_device_index = None
print("🔍 Scanning for your USB Microphone...")

for i in range(audio_interface.get_device_count()):
    try:
        dev_info = audio_interface.get_device_info_by_index(i)
        dev_name = dev_info.get('name', '').lower()

        # Look for USB audio device with input capabilities
        if 'usb' in dev_name and dev_info.get('maxInputChannels', 0) > 0:
            mic_device_index = i
            print(f"✅ Found USB Mic: '{dev_info['name']}' at Index {i}")
            break
    except Exception:
        continue

# Fallback clause if the string search fails
if mic_device_index is None:
    print("⚠️ USB naming not matched cleanly. Falling back to index 2.")
    mic_device_index = 2

# Open the stream using the microphone's native hardware rate
stream = audio_interface.open(
    format=FORMAT, channels=CHANNELS, rate=HARDWARE_RATE,
    input=True, frames_per_buffer=HARDWARE_CHUNK, input_device_index=mic_device_index
)

print("🕵️ Voice Activation System Active (Adaptive Hardware Mode)...")
print("Listening for human speech...")

recording_frames = []
is_recording = False
silence_start_time = None

try:
    while True:
        # Read raw data at native hardware speed (48000 Hz)
        frame_data = stream.read(HARDWARE_CHUNK, exception_on_overflow=False)
        
        # Convert bytes to numpy to downsample mathematically
        signal_np = np.frombuffer(frame_data, dtype=np.int16)
        
        # Resample from 48000 -> 16000 (Ratio 1:3 downsampling)
        resampled_np = resample_poly(signal_np, 1, 3).astype(np.int16)
        vad_frame_bytes = resampled_np.tobytes()
        
        # Validate using WebRTC VAD engine
        try:
            is_speech = vad.is_speech(vad_frame_bytes, VAD_RATE)
        except Exception:
            is_speech = False

        if is_speech:
            if not is_recording:
                print("\n🔊 Speech detected! Starting recording...")
                is_recording = True
            
            silence_start_time = None
            recording_frames.append(frame_data) # Keep the original high-quality audio
            print(".", end="", flush=True)
            
        else:
            if is_recording:
                recording_frames.append(frame_data)
                
                if silence_start_time is None:
                    silence_start_time = time.time()
                
                if time.time() - silence_start_time >= SILENCE_TIMEOUT:
                    print(f"\n🤫 Silence detected. Processing audio...")
                    
                    raw_audio = b"".join(recording_frames)
                    audio_np = np.frombuffer(raw_audio, dtype=np.int16)
                    
                    # Optional: Amplification boost for far away voice capture
                    boost_factor = 2.0
                    audio_np = np.clip(audio_np * boost_factor, -32768, 32767).astype(np.int16)
                    
                    print("✨ Running digital noise filter...")
                    cleaned_audio_np = nr.reduce_noise(y=audio_np, sr=HARDWARE_RATE, stationary=True)
                    cleaned_audio_np = np.clip(cleaned_audio_np, -32768, 32767).astype(np.int16)
                    
                    timestamp = time.strftime("%Y%m%d-%H%M%S")
                    filename = f"record_{timestamp}.wav"
                    
                    with wave.open(filename, 'wb') as wf:
                        wf.setnchannels(CHANNELS)
                        wf.setsampwidth(audio_interface.get_sample_size(FORMAT))
                        wf.setframerate(HARDWARE_RATE)
                        wf.writeframes(cleaned_audio_np.tobytes())
                        
                    print(f"💾 Saved cleanly as: {filename}\n")
                    print("Listening for human speech...")
                    
                    is_recording = False
                    recording_frames = []
                    silence_start_time = None

except KeyboardInterrupt:
    print("\nShutting down recorder cleanly.")
    stream.stop_stream()
    stream.close()
    audio_interface.terminate()

