import sounddevice as sd
import numpy as np
import whisper
import torch
import queue
import soundfile as sf  # Ensure you have this installed: pip install soundfile

# Load Whisper model
model = whisper.load_model("base")

# Constants
SAMPLE_RATE = 16000  # Whisper expects 16kHz audio
BLOCKSIZE = 4000  # Number of frames per block
AUDIO_QUEUE = queue.Queue()  # Queue to store audio chunks

def callback(indata, frames, time, status):
    """Processes live microphone input and queues it for Whisper."""
    if status:
        print(f"Audio error: {status}")

    # Convert indata to NumPy array
    indata = np.array(indata, dtype=np.float32)

    # Ensure mono audio
    if indata.ndim > 1:  # Stereo input (2D array)
        mono_audio = np.mean(indata, axis=1)  # Convert stereo to mono
    else:  # Mono input (1D array)
        mono_audio = indata

    # Save audio as a temporary WAV file using `soundfile`
    sf.write("temp.wav", mono_audio, SAMPLE_RATE, format="WAV")

    # Add filename to queue for transcription
    AUDIO_QUEUE.put("temp.wav")

# Start real-time microphone stream
with sd.InputStream(samplerate=48000, channels=2, dtype="float32",
                    blocksize=BLOCKSIZE, callback=callback):
    print("Listening... Speak now!")

    while True:
        if not AUDIO_QUEUE.empty():
            filename = AUDIO_QUEUE.get()
            
            # Transcribe using Whisper
            result = model.transcribe(filename, fp16=torch.cuda.is_available())
            print("Transcript:", result["text"])
