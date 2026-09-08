import asyncio
import os
import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from audio_processor.recorder import Recorder
from audio_processor.recognizer import Recognizer

DEFAULT_VOSK_MODEL = 'vosk-model-small-ru-0.22'
DEFAULT_MODELS_DIR = '/workspace/models'


def resolve_model_path(model: str, models_dir: str = DEFAULT_MODELS_DIR) -> str:
    """Resolve a model directory name while preserving explicit absolute paths."""
    return model if os.path.isabs(model) else os.path.join(models_dir, model)


class AudioProcessorNode(Node):
    def __init__(self):
        super().__init__('audio_processor_node')

        env_vosk_model = os.environ.get('VOSK_MODEL', DEFAULT_VOSK_MODEL)
        env_samplerate = int(os.environ.get('AUDIO_SAMPLERATE', 16000))
        env_block_size = int(os.environ.get('AUDIO_BLOCK_SIZE', 4000))

        self.declare_parameter('vosk_model', env_vosk_model)
        self.declare_parameter('samplerate', env_samplerate)
        self.declare_parameter('block_size', env_block_size)

        model_path = resolve_model_path(self.get_parameter('vosk_model').value)
        samplerate = int(self.get_parameter('samplerate').value)
        blocksize = int(self.get_parameter('block_size').value)
        if samplerate <= 0 or blocksize <= 0:
            raise ValueError('samplerate and block_size must be positive')
        
        self.text_publisher = self.create_publisher(String, '/recognized_text', 10)

        self.async_loop = asyncio.new_event_loop()
        self.is_running = True

        self.recorder = Recorder(loop=self.async_loop, samplerate=samplerate, blocksize=blocksize, logger=self.get_logger())
        self.recognizer = Recognizer(model_path=model_path, samplerate=samplerate)

        self.recorder.start_recording()

        self.worker_thread = threading.Thread(target=self.run_async_loop, daemon=True)
        self.worker_thread.start()

        self.get_logger().info("Audio Processor Node initialized.")
    
    def run_async_loop(self):
        asyncio.set_event_loop(self.async_loop)
        try:
            self.async_loop.run_until_complete(self._start_audio_processing())
        finally:
            self.async_loop.close()
    
    async def _start_audio_processing(self):
        self.get_logger().info("Starting audio processing loop...")

        while rclpy.ok() and self.is_running:
            try:
                chunk = await self.recorder.get_chunk()
                if chunk is None:
                    break
                result = self.recognizer.recognize_chunk(chunk)
                
                if result.get("text", ""):
                    final_text = result["text"]
                    self.get_logger().info(f"Recognized text: {final_text}")

                    msg = String()
                    msg.data = final_text
                    self.text_publisher.publish(msg)

                elif result.get("partial", ""):
                    partial_text = result["partial"]
                    self.get_logger().info(f"Listening...: {partial_text}")
            except Exception as e:
                self.get_logger().error(f"Error in audio processing loop: {e}")
                await asyncio.sleep(0.1)
    
    def destroy_node(self):
        self.get_logger().info("Shutting down audio processor...")
        self.is_running = False
        try:
            self.recorder.stop_recording()
            final_result = self.recognizer.finalize_recognition()
            if final_result.get("text", ""):
                final_text = final_result["text"]
                self.get_logger().info(f"Final recognized text: {final_text}")

                msg = String()
                msg.data = final_text
                self.text_publisher.publish(msg)
        except Exception as e:
            self.get_logger().error(f"Error during shutdown: {e}")
        
        if self.async_loop.is_running():
            self.async_loop.call_soon_threadsafe(
                self.recorder._enqueue_latest, None
            )
            self.worker_thread.join(timeout=2.0)
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = AudioProcessorNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
