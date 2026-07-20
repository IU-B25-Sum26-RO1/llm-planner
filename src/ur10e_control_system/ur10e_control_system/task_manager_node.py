import asyncio
import threading
import json
import time
import queue

import rclpy                                       # type: ignore
from rclpy.node import Node                        # type: ignore
from rclpy.action import ActionClient              # type: ignore
from rclpy.executors import MultiThreadedExecutor  # type: ignore
from std_msgs.msg import String                    # type: ignore
from sensor_msgs.msg import Image, CompressedImage # type: ignore

from robot_interfaces.action import BaseAction     # type: ignore
from robot_interfaces.srv import GripperControl    # type: ignore

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

        self.gripper_client = self.create_client(
            GripperControl,
            gripper_control_topic
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
        self.task_queue = asyncio.PriorityQueue(maxsize=10)

        self.get_logger().info("Task Manager | Waiting for Action Server...")
        await asyncio.to_thread(self.action_client.wait_for_server)
        self.get_logger().info("Task Manager | Action Server is ready!")

        self.get_logger().info("Task Manager | Waiting for Gripper Service...")
        await asyncio.to_thread(self.gripper_client.wait_for_service)
        self.get_logger().info("Task Manager | Gripper Service is ready!")

        while rclpy.ok():
            try:
                items = await self.task_queue.get()
                task = items[2]
                action = task["action"]
                success = False
                
                if action == "open_gripper":
                    success = await self.send_gripper_command(activate=False)
                elif action == "close_gripper":
                    success = await self.send_gripper_command(activate=True)
                else:
                    success = await self.send_task_to_robot(task)
            
                if success:
                    self.get_logger().info("Task Manager | Task successfully completed")
                else:
                    self.get_logger().warn("Task Manager | Task failed")
                
                self.task_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.get_logger().error(f"Task Manager | Error in orchestrator loop: {e}")
    
    async def send_gripper_command(self, activate: bool) -> bool:
        try:
            self.get_logger().info(f"Task Manager | Received gripper command: {'close' if activate else 'open'}")
            request = GripperControl.Request()
            request.activate = activate

            srv_future = self.gripper_client.call_async(request)

            response = await self._async_ros_future(srv_future)

            return response.success
        
        except Exception as e:
            self.get_logger().error(f"Task Manager | Error while sending gripper command: {str(e)}")
            return False

    async def send_task_to_robot(self, task):
        try:
            self.get_logger().info(f"Task Manager | Received task: {task['id']} ({task['action']})")
            goal_msg = self.create_goal_msg(task)

            send_goal_future = self.action_client.send_goal_async(goal_msg)
            
            goal_handle = await self._async_ros_future(send_goal_future)

            if not goal_handle.accepted:
                self.get_logger().error("Task Manager | Robot rejected the task")
                return False
                        
            self.get_logger().info("Task Manager | Robot accepted the task. Waiting for result...")

            get_result_future = goal_handle.get_result_async()
            result_response = await self._async_ros_future(get_result_future)

            return result_response.result.success
        
        except Exception as e:
            self.get_logger().error(f"Error while sending task: {str(e)}")
            return False

    def _wait_for_rclpy_future(self, rclpy_future):
        rclpy.spin_until_future_complete(self, rclpy_future)
        return rclpy_future.result()
    
    def create_goal_msg(self, task: dict):
        goal_msg = BaseAction.Goal()
        
        goal_msg.x = 0.0
        goal_msg.y = 0.0
        goal_msg.z = 0.0

        goal_msg.task_type = task["action"]
        task_type = task["action"]

        if task_type == "place":
            object_name = "_".join(task["placement"]["reference"]["object"]["prompt"].split())
        elif task_type == "pick":
            object_name = "_".join(task["target"]["object"]["prompt"].split())
        else: 
            object_name = ""
        goal_msg.object_name = object_name

        return goal_msg
    
    async def _async_ros_future(self, rclpy_future):
        """Конвертирует rclpy.task.Future в честный asyncio.Future, 
        который не блокирует Executor ноды."""
        loop = asyncio.get_running_loop()
        asyncio_future = loop.create_future()

        def cb(fut):
            if not asyncio_future.done():
                loop.call_soon_threadsafe(asyncio_future.set_result, fut.result())

        rclpy_future.add_done_callback(cb)
        return await asyncio_future
    
    def _command_callback(self, msg: String) -> None:
        if self.task_queue is None:
            self.get_logger().warn("Task queue is not initialized yet. Dropping command")
            return

        try:
            cmd_obj = json.loads(msg.data)
            if cmd_obj['type'] == 'non_command' or cmd_obj['confidence'] < 0.5: 
                return
            
            self.get_logger().info(f"Manager received new command: {cmd_obj['text']}")

            for task in cmd_obj["tasks"]:
                priority = 0 if task["action"] in ("stop", "cancel") else 1
                timestamp = time.time()
                payload = (priority, timestamp, task)
                self.loop.call_soon_threadsafe(self.task_queue.put_nowait, payload)
        
        except json.JSONDecodeError:
            self.get_logger().error(f"Task Manager | Received invalid JSON string in command_callback: {msg.data}")
        except Exception as e:
            self.get_logger().error(f"Task Manager | Error in command_callback: {e}")


def main(args=None):
    rclpy.init(args=args)
    node = TaskManagerNode()

    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()