import asyncio
import threading
import json
import time
import queue

import rclpy                                       # type: ignore
from rclpy.node import Node                        # type: ignore
from rclpy.action import ActionClient              # type: ignore
from std_msgs.msg import String                    # type: ignore
from sensor_msgs.msg import Image, CompressedImage # type: ignore

from robot_interfaces import BaseAction            # type: ignore

class TaskManagerNode(Node):
    def __init__(self):
        super().__init__('task_manager_node')
        
        json_command_topic = 'decomposer/json_output/command'

        base_action_topic = '/execute/base_action'
        gripper_control_topic = '/execute/gripper_control'

        self.cmd_sub = self.create_subscription(
            String,
            json_command_topic,
            self._command_callback,
            10
        )

        self.task_queue = None

        self.action_client = ActionClient(
            self, BaseAction, base_action_topic 
        )

        self.loop = None
        self.loop_tread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.loop_tread.start()
    
    def _run_async_loop(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.orchestrator())
        except Exception as e:
            self.get_logger().critical(f"Task Manager | Async loop has crashed with {str(e)}")
        finally:
            self.loop.close()
            self.get_logger().info(f"Async loop closed.")
    
    async def orchestrator(self):
        self.loop = asyncio.get_running_loop()
        self.task_queue = asyncio.PriorityQueue(maxsize=10)

        while rclpy.ok():
            self.action_client.wait_for_server()
            task = await self.task_queue.get()
            success = await self.send_task_to_robot(task)
        
            if success:
                self.get_logger().info("Task Manager | Task successfully completed")
            else:
                self.get_logger().warn("Task Manager | Task failed")

    async def send_task_to_robot(self, task):
        try:
            goal_msg = self.create_goal_msg(task)

            send_goal_future = await self.action_client.send_goal_async(goal_msg)
            goal_handle = send_goal_future

            if not goal_handle.accepted:
                self.get_logger().error(f"TaskM Manager | Robot rejected the task")
                return False
                        
            self.get_logger().info(f"Task Manager | Robot accepted the task. Waiting for result")

            get_result_future = await goal_handle.get_result_async()
            result = get_result_future.result

            return result.success
        
        except Exception as e:
            self.get_logger().info(f"Error while sending task: {str(e)}")
    
    def create_goal_msg(self, task: dict):
        goal_msg = BaseAction.Goal()
        
        goal_msg.x = 0.0
        goal_msg.y = 0.0
        goal_msg.z = 0.0

        goal_msg.task_type = task["action"]
        goal_msg.object_name = task["target"]["object"]["class"] or ""

        return goal_msg

    
    def _command_callback(self, msg: String) -> None:
        if self.task_queue is None:
            self.get_logger().warn("Task queue is not initialized yet. Dropping command")
            return

        try:
            cmd_obj = json.loads(msg.data)
            if cmd_obj['type'] == 'non_command' or cmd_obj['confidence'] < 0.5: 
                return
            
            self.get_logger().info(f'Manager received new command: {cmd_obj['text']}')

            for task in cmd_obj["tasks"]:
                priority = 0 if task["action"] in ("stop", "cancel") else 1
                timestamp = time.time()
                payload = (priority, timestamp, task)
                self.loop.call_soon_threadsafe(self.task_queue.put_nowait, payload)
        
        except json.JSONDecodeError:
            self.get_logger().error(f"Task Manager | Received invalid JSON string in command_callback: {msg.data}")
        except Exception as e:
            self.get_logger().error(f"Task Manager | Error in command_callback: {e}")

    def _create_task(self, action, **args) -> dict:
        if action == 'pick':
            pass

        return {
            'action': action,
        }

def main(args=None):
    rclpy.init(args=args)
    node = TaskManagerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()