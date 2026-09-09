import asyncio
import os
import time
import sounddevice as sd


class Recorder:
    def __init__(self, loop: asyncio.AbstractEventLoop, samplerate=16000, blocksize=4000, channels=1, logger=None):
        self.loop = loop
        self.samplerate = samplerate
        self.blocksize = blocksize
        self.channels = channels
        self.recording = False
        self.logger = logger

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
            self.logger.error(f"[RECORDER]: {status}")
        self.loop.call_soon_threadsafe(
            self.audio_queue.put_nowait, bytes(indata)
        )

    def start_recording(self):
        for attempt in range(1, 4):
            try:
                self.stream.start()
                self.recording = True
                self.logger.info(f"RECORDER | Audio Stream has started.")
                break
            except sd.PortAudioError as e:
                if "Wait timed out" in str(e) and attempt < 3:
                    self.logger.warning(f"RECORDER | Audio Server Timeout. Retrying in 2 seconds...")
                    time.sleep(2.0)
                else:
                    raise e

    def stop_recording(self):
        if self.recording:
            self.recording = False
            self.stream.stop()
            self.stream.close()
            self.logger.info(f"RECORDER | Recording stopped.")

    
    async def get_chunk(self):
        return await self.audio_queue.get()