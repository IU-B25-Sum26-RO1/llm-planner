import asyncio
import os
import sounddevice as sd


class Recorder:
    def __init__(self, loop: asyncio.AbstractEventLoop, samplerate=16000, blocksize=4000, channels=1):
        self.loop = loop
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.channels = channels
        self.recording = False

        self.audio_queue = asyncio.Queue()
        self.stream = sd.RawInputStream(
            samplerate=self.samplerate,
            blocksize=self.blocksize,
            channels=self.channels,
            dtype='int16',
            callback=self._callback,
            device=os.environ.get('AUDIO_DEVICE')
        )

    def _callback(self, indata, frames, time, status):
        if status:
            print(f"[Recording error]: {status}")
        self.loop.call_soon_threadsafe(
            self.audio_queue.put_nowait, bytes(indata)
        )

    def start_recording(self):
        if not self.recording:
            self.recording = True
            self.stream.start()
            print("Recording started...")
    
    def stop_recording(self):
        if self.recording:
            self.recording = False
            self.stream.stop()
            self.stream.close()
            print("Recording stopped.")
    
    async def get_chunk(self):
        return await self.audio_queue.get()