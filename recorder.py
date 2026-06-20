import os
import time
import wave
import collections
import numpy as np
import pyaudio
import webrtcvad
import noisereduce as nr
from scipy.signal import resample_poly

# --- CONFIGURATION ---
FORMAT = pyaudio.paInt16
CHANNELS = 1

HARDWARE_RATE = 48000 
VAD_RATE = 16000      

FRAME_DURATION = 30   
HARDWARE_CHUNK = int(HARDWARE_RATE * FRAME_DURATION / 1000)
VAD_CHUNK = int(VAD_RATE * FRAME_DURATION / 1000)

VAD_AGGRESSIVENESS = 3 

# ⏳ CONVERSATION GAP FIXES
SILENCE_TIMEOUT = 16.0
MAX_RECORDING_DURATION = 300.0

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
        
        if 'usb' in dev_name and dev_info.get('maxInputChannels', 0) > 0:
            mic_device_index = i
            print(f"✅ Found USB Mic: '{dev_info['name']}' at Index {i}")
            break
    except Exception:
        continue

if mic_device_index is None:
    print("⚠️ USB naming not matched cleanly. Falling back to index 2.")
    mic_device_index = 2

# Open the stream dynamically using the index we discovered
stream = audio_interface.open(
    format=FORMAT, 
    channels=CHANNELS, 
    rate=HARDWARE_RATE,
    input=True, 
    frames_per_buffer=HARDWARE_CHUNK,
    input_device_index=mic_device_index
)

print("\n🕵️ Spy Voice Activation System Active...")
print("Listening for human speech...")

recording_frames = []
is_recording = False
silence_start_time = None

try:
    while True:
        frame_data = stream.read(HARDWARE_CHUNK, exception_on_overflow=False)
        
        signal_np = np.frombuffer(frame_data, dtype=np.int16)
        resampled_np = resample_poly(signal_np, 1, 3).astype(np.int16)
        vad_frame_bytes = resampled_np.tobytes()
        
        try:
            is_speech = vad.is_speech(vad_frame_bytes, VAD_RATE)
        except Exception:
            is_speech = False

        if is_speech:
            if not is_recording:
                print("\n🔊 Speech detected! Starting recording...")
                is_recording = True
            
            silence_start_time = None
            recording_frames.append(frame_data)
            print(".", end="", flush=True)
            
        else:
            if is_recording:
                recording_frames.append(frame_data)
                
                if silence_start_time is None:
                    silence_start_time = time.time()
                
                total_recording_time = len(recording_frames) * (FRAME_DURATION / 1000.0)
                reached_timeout = time.time() - silence_start_time >= SILENCE_TIMEOUT
                reached_max_limit = total_recording_time >= MAX_RECORDING_DURATION
                
                if reached_timeout or reached_max_limit:
                    if reached_max_limit:
                        print(f"\n🛑 Reached max file duration cap ({MAX_RECORDING_DURATION}s). Splitting file...")
                    else:
                        print(f"\n🤫 Silence detected for {SILENCE_TIMEOUT}s. Processing audio...")
                    
                    raw_audio = b"".join(recording_frames)
                    audio_np = np.frombuffer(raw_audio, dtype=np.int16)
                    
                    boost_factor = 4.5
                    audio_np = np.clip(audio_np * boost_factor, -32768, 32767).astype(np.int16)
                    
                    print("✨ Running digital noise filter...")
                    cleaned_audio_np = nr.reduce_noise(y=audio_np, sr=HARDWARE_RATE, stationary=True)
                    cleaned_audio_np = np.clip(cleaned_audio_np, -32768, 32767).astype(np.int16)
                    
                    # 📅 CREATE DYNAMIC YEAR/MONTH/DATE DIRECTORY PATH
                    current_time = time.localtime()
                    year = time.strftime("%Y", current_time)
                    month = time.strftime("%m", current_time)
                    day = time.strftime("%d", current_time)
                    
                    # Target path: recordings/2026/06/20/
                    target_dir = os.path.join("recordings", year, month, day)
                    os.makedirs(target_dir, exist_ok=True) # exist_ok=True ignores error if path already exists
                    
                    # Generate filename with just hours/minutes/seconds
                    hms_timestamp = time.strftime("%H%M%S", current_time)
                    filename = f"record_{hms_timestamp}.wav"
                    full_save_path = os.path.join(target_dir, filename)
                    
                    # Save the clean wave file inside the nested directory
                    with wave.open(full_save_path, 'wb') as wf:
                        wf.setnchannels(CHANNELS)
                        wf.setsampwidth(audio_interface.get_sample_size(FORMAT))
                        wf.setframerate(HARDWARE_RATE)
                        wf.writeframes(cleaned_audio_np.tobytes())
                        
                    print(f"💾 Saved cleanly to: {full_save_path}\n")
                    print("Listening for human speech...")
                    
                    is_recording = False
                    recording_frames = []
                    silence_start_time = None

except KeyboardInterrupt:
    print("\nShutting down recorder cleanly.")
    stream.stop_stream()
    stream.close()
    audio_interface.terminate()
