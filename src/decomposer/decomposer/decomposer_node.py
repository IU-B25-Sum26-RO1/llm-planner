import asyncio
import threading
import json
import os
import rclpy

from rclpy.node import Node
from std_msgs.msg import String

from decomposer.llm_client import LLMClient
from decomposer.sys_prompt_collector import get_system_prompt

class DecomposerNode(Node):
    def __init__(self):
        super().__init__('decomposer_node')

        env_url = os.environ.get('LLM_API_URL')
        env_key = os.environ.get('LLM_API_KEY')
        env_model = os.environ.get('LLM_MODEL')
        env_sys_prompt_file_path = os.environ.get('SYS_PROMPT_PATH')

        system_prompt = get_system_prompt(env_sys_prompt_file_path, logger=self.get_logger())

        self.get_logger().info(f"System prompt loaded from {env_sys_prompt_file_path}: {system_prompt[:100]}...")

        self.declare_parameter('base_url', env_url)
        self.declare_parameter('api_key', env_key)
        self.declare_parameter('model', env_model)
        self.declare_parameter('system_prompt', system_prompt)

        base_url = self.get_parameter('base_url').value
        api_key = self.get_parameter('api_key').value
        model = self.get_parameter('model').value
        system_prompt = self.get_parameter('system_prompt').value

        self.llm_client = LLMClient(
            base_url=base_url,
            model=model,
            api_key=api_key,
            system_prompt=system_prompt,
            logger=self.get_logger()
        )

        self.json_publisher = self.create_publisher(String, '/decomposed_json', 10)
        self.text_subscriber = self.create_subscription(
            String, 
            '/recognized_text',
            self.text_callback,
            10
        )
        
        self.async_loop = asyncio.new_event_loop()
        self.worker_thread = threading.Thread(target=self._start_async_loop, daemon=True)
        self.worker_thread.start()

        self.get_logger().info("Decomposer Node has started and is listening to /recognized_text...")
    
    def _start_async_loop(self):
        asyncio.set_event_loop(self.async_loop)
        self.async_loop.run_forever()
    
    def text_callback(self, msg: String):
        text_to_process = msg.data.strip()
        if not text_to_process:
            return 
        
        self.get_logger().info(f"Received speech text: '{text_to_process}'.")

        asyncio.run_coroutine_threadsafe(
            self._async_decompose_and_publish(text_to_process),
            self.async_loop
        )
    
    async def _async_decompose_and_publish(self, text: str):
        try:
            result_dict = await self.llm_client.decompose(text)
            json_string = json.dumps(result_dict, ensure_ascii=False)

            out_msg = String()
            out_msg.data = json_string
            self.json_publisher.publish(out_msg)

            self.get_logger().info(f"Successfully published JSON output to /decomposed_json:" + json_string)
        
        except Exception as e:
            self.get_logger().error(f"Failed to process or publish decomposition: {str(e)}")
    
    def destroy_node(self):
        self.async_loop.call_soon_threadsafe(self.async_loop.stop)
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = DecomposerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()