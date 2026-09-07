import asyncio
import threading
import json
import time
import queue
import os

import rclpy                                       # type: ignore
from rclpy.node import Node                        # type: ignore
from rclpy.action import ActionClient              # type: ignore
from rclpy.executors import MultiThreadedExecutor  # type: ignore
from std_msgs.msg import String                    # type: ignore
from geometry_msgs.msg import PoseStamped          # type: ignore
from sensor_msgs.msg import Image, CompressedImage # type: ignore

from robot_interfaces.action import BaseAction     # type: ignore
from robot_interfaces.srv import GripperControl    # type: ignore
from ur10e_control_system.scene_object_resolver import resolve_target_model_name

class TaskManagerNode(Node):
    def __init__(self):
        super().__init__('task_manager_node')
        
        json_command_topic = 'decomposer/json_output/command'
        target_tracker_topic = '/to_track/target'
        target_pose_topic = os.environ.get(
            'PERCEPTION_TARGET_POSE_TOPIC',
            '/perception/target_pose'
        )

        base_action_topic = '/execute/base_action'
        gripper_control_topic = '/execute/gripper_control'

        self.target_source_mode = os.environ.get('TARGET_SOURCE_MODE', 'auto').strip().lower()
        if self.target_source_mode not in ('auto', 'perception', 'simulation'):
            self.get_logger().warn(
                f"Task Manager | Invalid TARGET_SOURCE_MODE='{self.target_source_mode}', using 'auto'"
            )
            self.target_source_mode = 'auto'
        self.perception_target_timeout = float(
            os.environ.get('PERCEPTION_TARGET_TIMEOUT', '5.0')
        )
        self.target_pose_topic = target_pose_topic
        self._target_pose_lock = threading.Lock()
        self._latest_target_pose = None
        self._latest_target_pose_received_at = 0.0

        self.cmd_sub = self.create_subscription(
            String,
            json_command_topic,
            self._command_callback,
            10
        )

        self.current_target_pub = self.create_publisher(
            String,
            target_tracker_topic,
            1
        )

        self.target_pose_sub = self.create_subscription(
            PoseStamped,
            target_pose_topic,
            self._target_pose_callback,
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

        self.state = {
            "held": None,
            "in_fault": False
        }

        self.executing_task = None
        self.current_target = None

        self.loop = None
        self.loop_tread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.loop_tread.start()

        self.get_logger().info(
            "Task Manager | Target source mode: "
            f"{self.target_source_mode}; perception pose topic: {target_pose_topic}; "
            f"timeout: {self.perception_target_timeout:.1f}s"
        )
    
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

                self.executing_task = task
                self._select_target(task=self.executing_task)

                target_msg = String()
                target_msg.data = json.dumps(self.current_target)
                target_requested_at = time.monotonic()
                self.current_target_pub.publish(target_msg)
                
                if action == "open_gripper":
                    success = await self.send_gripper_command(activate=False)
                elif action == "close_gripper":
                    success = await self.send_gripper_command(activate=True)
                else:
                    success = await self.send_task_to_robot(task, target_requested_at)
            
                if success:
                    self.get_logger().info("Task Manager | Task successfully completed")
                else:
                    self.get_logger().warn("Task Manager | Task failed")
                
                self._update_state(success)
                self.executing_task = None
                
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

    async def send_task_to_robot(self, task, target_requested_at=None):
        try:
            self.get_logger().info(f"Task Manager | Received task: {task['id']} ({task['action']})")
            goal_msg = await self.create_goal_msg(task, target_requested_at)
            if goal_msg is None:
                return False

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
    
    async def create_goal_msg(self, task: dict, target_requested_at=None):
        goal_msg = BaseAction.Goal()
        
        goal_msg.x = 0.0
        goal_msg.y = 0.0
        goal_msg.z = 0.0

        goal_msg.task_type = task["action"]
        task_type = task["action"]

        if task_type == "place":
            target = task["placement"]["reference"]
            object_name = await self._fill_goal_target(goal_msg, target, target_requested_at)
            if object_name is None:
                return None
        elif task_type == "pick":
            target = task["target"]
            object_name = await self._fill_goal_target(goal_msg, target, target_requested_at)
            if object_name is None:
                return None
        else: 
            object_name = ""
        goal_msg.object_name = object_name
        if object_name:
            self.get_logger().info(
                f"Task Manager | Using simulation target object name: {object_name}"
            )

        return goal_msg

    async def _fill_goal_target(self, goal_msg, target, target_requested_at):
        if not isinstance(target, dict) or not isinstance(target.get("object"), dict):
            self.get_logger().error("Task Manager | Task target is missing or malformed")
            return None

        if self.target_source_mode != "simulation":
            pose = await self._wait_for_perception_pose(target_requested_at)
            if pose is not None:
                goal_msg.x = pose[0]
                goal_msg.y = pose[1]
                goal_msg.z = pose[2]
                self.get_logger().info(
                    "Task Manager | Using perception target pose: "
                    f"x={pose[0]:.3f}, y={pose[1]:.3f}, z={pose[2]:.3f}"
                )
                return ""

            if self.target_source_mode == "perception":
                self.get_logger().error(
                    "Task Manager | No fresh perception target pose received; "
                    "simulation fallback is disabled"
                )
                return None

        fallback = "_".join(target["object"]["prompt"].split())
        object_name = resolve_target_model_name(target, fallback=fallback)
        self.get_logger().info(
            "Task Manager | Using simulation fallback via scene_object_resolver: "
            f"{object_name}"
        )
        return object_name

    async def _wait_for_perception_pose(self, target_requested_at):
        if self.target_source_mode == "auto" and self.count_publishers(self.target_pose_topic) == 0:
            return None

        if target_requested_at is None:
            target_requested_at = time.monotonic()

        deadline = time.monotonic() + self.perception_target_timeout
        while time.monotonic() < deadline and rclpy.ok():
            with self._target_pose_lock:
                pose = self._latest_target_pose
                received_at = self._latest_target_pose_received_at
            if pose is not None and received_at >= target_requested_at:
                return pose
            await asyncio.sleep(0.05)

        return None
    
    async def _async_ros_future(self, rclpy_future):
        loop = asyncio.get_running_loop()
        asyncio_future = loop.create_future()

        def cb(fut):
            if not asyncio_future.done():
                loop.call_soon_threadsafe(asyncio_future.set_result, fut.result())

        rclpy_future.add_done_callback(cb)
        return await asyncio_future
    
    def _command_callback(self, msg: String) -> None:
        if self.loop is None:
            self.get_logger().warn("Executing loop is not initialized yet. Dropping command")
            return 
        
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

    def _target_pose_callback(self, msg: PoseStamped) -> None:
        position = msg.pose.position
        with self._target_pose_lock:
            self._latest_target_pose = (
                float(position.x),
                float(position.y),
                float(position.z),
            )
            self._latest_target_pose_received_at = time.monotonic()
    
    def _update_state(self, success: bool) -> None:
        """Update robot's state."""
        if not success:
            self.state["in_fault"] = True
        else:
            if self.executing_task is None:
                self.get_logger().warn(f"Executing command is None. Cannot update state")
                return 
            if self.executing_task["action"] == "pick":
                self.state["held"] = self.executing_task["target"]["object"]
            
        
    def _select_target(self, task: dict) -> None:
        if task["action"] == "pick":
            target = task["target"]
        elif task["action"] == "place":
            target = task["placement"]["reference"]
        else:
            target = None 
        
        self.current_target = target
        if self.current_target is not None:
            target_key = self.current_target['key']
            target_prompt = self.current_target['object']['prompt']
            self.get_logger().info(
                f"Task Manager | Selected target: {target_key} ({target_prompt})"
            )
        else: 
            self.get_logger().info(f"Task Manager | Selected target: null")



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
