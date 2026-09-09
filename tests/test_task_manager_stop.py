import asyncio
import importlib
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src" / "ur10e_control_system"))


def _install_ros_stubs(monkeypatch):
    rclpy = types.ModuleType("rclpy")
    rclpy.action = types.ModuleType("rclpy.action")
    rclpy.action.ActionClient = type("ActionClient", (), {})
    rclpy.executors = types.ModuleType("rclpy.executors")
    rclpy.executors.MultiThreadedExecutor = type("MultiThreadedExecutor", (), {})
    rclpy.node = types.ModuleType("rclpy.node")
    rclpy.node.Node = type("Node", (), {})

    std_msgs = types.ModuleType("std_msgs")
    std_msgs.msg = types.ModuleType("std_msgs.msg")
    std_msgs.msg.String = type("String", (), {})

    robot_interfaces = types.ModuleType("robot_interfaces")
    robot_interfaces.action = types.ModuleType("robot_interfaces.action")
    robot_interfaces.action.BaseAction = type("BaseAction", (), {})
    robot_interfaces.srv = types.ModuleType("robot_interfaces.srv")
    robot_interfaces.srv.GripperControl = type("GripperControl", (), {})

    monkeypatch.setitem(sys.modules, "rclpy", rclpy)
    monkeypatch.setitem(sys.modules, "rclpy.action", rclpy.action)
    monkeypatch.setitem(sys.modules, "rclpy.executors", rclpy.executors)
    monkeypatch.setitem(sys.modules, "rclpy.node", rclpy.node)
    monkeypatch.setitem(sys.modules, "std_msgs", std_msgs)
    monkeypatch.setitem(sys.modules, "std_msgs.msg", std_msgs.msg)
    monkeypatch.setitem(sys.modules, "robot_interfaces", robot_interfaces)
    monkeypatch.setitem(sys.modules, "robot_interfaces.action", robot_interfaces.action)
    monkeypatch.setitem(sys.modules, "robot_interfaces.srv", robot_interfaces.srv)


def test_stop_cancels_active_goal_and_clears_pending_tasks(monkeypatch):
    _install_ros_stubs(monkeypatch)
    sys.modules.pop("ur10e_control_system.task_manager_node", None)
    module = importlib.import_module("ur10e_control_system.task_manager_node")

    class GoalHandle:
        is_active = True

        def __init__(self):
            self.cancel_requested = False

        def cancel_goal_async(self):
            self.cancel_requested = True
            return object()

    class Logger:
        info = warning = error = lambda self, *args: None

    async def run():
        node = object.__new__(module.TaskManagerNode)
        node.task_queue = asyncio.PriorityQueue()
        node.task_queue.put_nowait((1, 1.0, {"action": "pick"}))
        node.task_queue.put_nowait((1, 2.0, {"action": "place"}))
        node.active_goal_handle = GoalHandle()
        node.get_logger = lambda: Logger()

        async def await_ros_future(future):
            return future

        node._async_ros_future = await_ros_future
        await node._stop_active_task()
        return node

    node = asyncio.run(run())
    assert node.active_goal_handle.cancel_requested
    assert node.task_queue.empty()
