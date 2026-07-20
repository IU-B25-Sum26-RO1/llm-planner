import asyncio
import threading
import json
import os
import rclpy
import secrets

from rclpy.node import Node
from std_msgs.msg import String

from decomposer.llm_client import LLMClient
from decomposer.sys_prompt_collector import get_system_prompt

# from schemas.output_cmd import OutputCommandSchema, TaskSchema, TargetSchema, ObjectSchema

class DecomposerNode(Node):
    def __init__(self):
        super().__init__('decomposer_node')

        env_url = os.environ.get('LLM_API_URL')
        env_key = os.environ.get('LLM_API_KEY')
        env_model = os.environ.get('LLM_MODEL')
        env_sys_prompt_file_path = os.environ.get('SYS_PROMPT_PATH', '')

        system_prompt = get_system_prompt(env_sys_prompt_file_path, logger=self.get_logger())

        self.get_logger().info(f"System prompt loaded from {env_sys_prompt_file_path}: {system_prompt[:50]}...")

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

        self.json_topic = '/decomposer/json_output/command'
        self.task_topic = '/decomposer/json_output/task'
        self.object_topic = '/decomposer/json_output/object'
        self.target_topic = '/decomposer/json_output/target'

        self.declare_parameter('json_topic', self.json_topic)
        self.declare_parameter('task_topic', self.task_topic)
        self.declare_parameter('object_topic', self.object_topic)
        self.declare_parameter('target_topic', self.target_topic)

        self.json_publisher = self.create_publisher(String, self.json_topic, 10)
        self.task_publisher = self.create_publisher(String, self.task_topic, 20)
        self.object_publisher = self.create_publisher(String, self.object_topic, 50)
        self.target_publisher = self.create_publisher(String, self.target_topic, 30)
        self.text_subscriber = self.create_subscription(
            String, 
            '/recognized_text',
            self.text_callback,
            10
        )

        self.objects = {} # object key -> object
        
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
<<<<<<< Updated upstream
            self.identify_output(result_dict)
=======

            if "error" in result_dict:
                self.get_logger().error(
                    f"LLM decomposition failed for '{text}': {result_dict['error']}"
                )
                return

            if result_dict.get("type") == "non_command":
                self.get_logger().info(f"Ignored non-command utterance: '{text}'")
                return

            if result_dict.get("type") != "command":
                self.get_logger().warning(
                    f"Unexpected command type '{result_dict.get('type')}' for '{text}'"
                )
                return

            self._parse_and_identify(result_dict)
>>>>>>> Stashed changes
            self.publish_cmd(result_dict)

        except Exception as e:
            self.get_logger().error(f"Failed to process or publish decomposition: {str(e)}")

    def _parse_and_identify(self, cmd_obj):
        """ Parses command_object and assign if for each object and task. """
        cmd_obj["id"] = self.generate_prefixed_id("cmd")
        for task in cmd_obj["tasks"]:
            task["id"] = self.generate_prefixed_id("tsk")

            placement = task.get("placement", None)
            placement_target = None if placement is None else placement["reference"]
            main_target = task["target"]

            for target in (placement_target, main_target):
                if target is None:
                    continue

                target["key"] = self.generate_prefixed_id("trg")

                objects = []
                objects.append(target["object"])
                
                for space in target["search_space"]:
                    objects.append(space["reference"])
                
                for obj in objects:
                    self._resolve_object_key(obj)
    
    def _resolve_object_key(self, obj: dict) -> str:
        """ Resolving object duplicating problem. Updating existing objects info.

        Args:
            obj (`dict`): Object (see schemas/output_cmd.py).

        Returns: 
            Unique object key (existing or new) (`str`).
        """
        for existing_obj in self.objects.values():
            if existing_obj["class"] != obj["class"]:
                continue

            has_contradiction = False
            for key, new_val in obj["attributes"].items():
                existing_val = existing_obj["attributes"].get(key)

                if existing_val is not None and new_val is not None and existing_val != new_val:
                    has_contradiction = True
                    break

            if not has_contradiction:
                for key, new_val in obj["attributes"].items():
                    if key in ("color", "material", "shape", "size"):
                        if existing_obj["attributes"].get(key) is None and new_val is not None:
                            existing_obj["attributes"][key] = new_val 
                return existing_obj["key"]
            
        new_key = self.generate_prefixed_id("obj")
        self.objects[new_key] = {
            "key": new_key,
            "class": obj["class"],
            "attributes": obj["attributes"].copy()
        }

        return new_key

    
    def destroy_node(self):
        self.async_loop.call_soon_threadsafe(self.async_loop.stop)
        super().destroy_node()
    
    def publish_cmd(self, cmd_obj: dict):
        self.get_logger().info(f"Published command: {cmd_obj['id']}")
        json_string = json.dumps(cmd_obj, ensure_ascii=False)
        out_msg = String()
        out_msg.data = json_string
        self.json_publisher.publish(out_msg)

        for task in cmd_obj["tasks"]:
            self.publish_task(task)

    def publish_task(self, task: dict):
        self.get_logger().info(f"Publishing task: {task['id']}")
        task_string = json.dumps(task, ensure_ascii=False)
        out_msg = String()
        out_msg.data = task_string
        self.task_publisher.publish(out_msg)

        placement = task.get("placement", None)
        placement_target = None if placement is None else placement["reference"]

        if placement_target is not None:
            self.publish_target(placement_target)
        
        main_target = task["target"]

        if main_target is not None:
            self.publish_target(main_target)

    def publish_target(self, target: dict):
        self.get_logger().info(f"Publishing target: {target['key']}")
        target_string = json.dumps(target, ensure_ascii=False)
        out_msg = String()
        out_msg.data = target_string
        self.target_publisher.publish(out_msg)

    
    def publish_object(self, obj: dict):
        obj["key"] = self.generate_prefixed_id("obj")
        self.get_logger().info(f"Published object: {obj['key']}")
        obj_string = json.dumps(obj, ensure_ascii=False)
        out_msg = String()
        out_msg.data = obj_string
        self.object_publisher.publish(out_msg)
    
    def generate_prefixed_id(self, prefix):
        random_part = secrets.token_urlsafe(16)
        return f"{prefix}_{random_part}"


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