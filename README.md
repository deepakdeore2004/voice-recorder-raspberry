# 🕵️ Smart Edge Voice Recorder

An automated, local voice-activated audio recorder designed to run efficiently on resource-constrained hardware like the Raspberry Pi. 

Using **Google WebRTC Voice Activity Detection (VAD)**, the system listens via a USB microphone, triggers a recording only when human speech is verified, and automatically runs a **digital spectral gating noise filter** to eliminate hardware electrical hums before saving clean, timestamped `.wav` files.

---

## 🛠️ System Prerequisites

Before setting up the Python workspace, you must install the underlying Linux audio architecture and compilation libraries:

```bash
sudo apt-get update
sudo apt-get install -y portaudio19-dev python3-pyaudio python3-full

