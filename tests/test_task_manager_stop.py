import asyncio
import importlib
import itertools
import json
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

    geometry_msgs = types.ModuleType("geometry_msgs")
    geometry_msgs.msg = types.ModuleType("geometry_msgs.msg")
    geometry_msgs.msg.PoseStamped = type("PoseStamped", (), {})

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
    monkeypatch.setitem(sys.modules, "geometry_msgs", geometry_msgs)
    monkeypatch.setitem(sys.modules, "geometry_msgs.msg", geometry_msgs.msg)
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


def test_stop_invalidates_goal_while_goal_acceptance_is_in_flight(monkeypatch):
    _install_ros_stubs(monkeypatch)
    sys.modules.pop("ur10e_control_system.task_manager_node", None)
    module = importlib.import_module("ur10e_control_system.task_manager_node")

    class GoalHandle:
        accepted = True

        def __init__(self):
            self.cancel_requested = False

        def cancel_goal_async(self):
            self.cancel_requested = True
            return "cancel"

    class Logger:
        info = warning = error = lambda self, *args: None

    async def run():
        node = object.__new__(module.TaskManagerNode)
        node.stop_generation = 0
        node.active_goal_handle = None
        node.get_logger = lambda: Logger()
        async def create_goal_msg(task, target_requested_at=None):
            return object()

        node.create_goal_msg = create_goal_msg
        goal_handle = GoalHandle()
        node.action_client = types.SimpleNamespace(
            send_goal_async=lambda goal: "accept"
        )

        async def await_ros_future(future):
            if future == "accept":
                node.stop_generation += 1
                return goal_handle
            return future

        node._async_ros_future = await_ros_future
        success = await node.send_task_to_robot(
            {"id": "tsk-1", "action": "pick"}, task_generation=0
        )
        return success, goal_handle

    success, goal_handle = asyncio.run(run())
    assert not success
    assert goal_handle.cancel_requested


def test_stop_invalidates_goal_while_perception_target_is_resolving(monkeypatch):
    _install_ros_stubs(monkeypatch)
    sys.modules.pop("ur10e_control_system.task_manager_node", None)
    module = importlib.import_module("ur10e_control_system.task_manager_node")

    class Logger:
        info = warning = error = lambda self, *args: None

    async def run():
        node = object.__new__(module.TaskManagerNode)
        node.stop_generation = 0
        node.active_goal_handle = None
        node.get_logger = lambda: Logger()
        send_attempts = []

        async def create_goal_msg(task, target_requested_at=None):
            node.stop_generation += 1
            return object()

        node.create_goal_msg = create_goal_msg
        node.action_client = types.SimpleNamespace(
            send_goal_async=lambda goal: send_attempts.append(goal)
        )

        success = await node.send_task_to_robot(
            {"id": "tsk-1", "action": "pick"}, task_generation=0
        )
        return success, send_attempts

    success, send_attempts = asyncio.run(run())
    assert not success
    assert send_attempts == []


def test_low_confidence_stop_is_not_filtered(monkeypatch):
    _install_ros_stubs(monkeypatch)
    sys.modules.pop("ur10e_control_system.task_manager_node", None)
    module = importlib.import_module("ur10e_control_system.task_manager_node")

    scheduled = []
    node = object.__new__(module.TaskManagerNode)
    node.stop_generation = 0
    node.queue_sequence = itertools.count()
    node.task_queue = asyncio.PriorityQueue()
    node.loop = types.SimpleNamespace(
        call_soon_threadsafe=lambda callback, *args: callback(*args)
    )
    node._schedule_stop = lambda: scheduled.append(True)
    node.get_logger = lambda: types.SimpleNamespace(
        info=lambda *args: None,
        warning=lambda *args: None,
        error=lambda *args: None,
    )

    msg = types.SimpleNamespace(
        data=json.dumps(
            {
                "type": "command",
                "confidence": 0.1,
                "text": "stop",
                "language": "en",
                "tasks": [
                    {
                        "action": "stop",
                        "target": None,
                        "placement": None,
                        "modifiers": None,
                        "confidence": 0.1,
                    }
                ],
            }
        )
    )
    node._command_callback(msg)

    assert node.stop_generation == 1
    assert scheduled == [True]


def test_execution_boundary_rejects_malformed_direct_ros_command(monkeypatch):
    _install_ros_stubs(monkeypatch)
    sys.modules.pop("ur10e_control_system.task_manager_node", None)
    module = importlib.import_module("ur10e_control_system.task_manager_node")

    scheduled = []
    node = object.__new__(module.TaskManagerNode)
    node.stop_generation = 0
    node.queue_sequence = itertools.count()
    node.task_queue = asyncio.PriorityQueue()
    node.loop = types.SimpleNamespace(
        call_soon_threadsafe=lambda callback, *args: scheduled.append((callback, args))
    )
    node.get_logger = lambda: types.SimpleNamespace(
        info=lambda *args: None,
        warning=lambda *args: None,
        error=lambda *args: None,
    )

    msg = types.SimpleNamespace(
        data=json.dumps(
            {
                "type": "command",
                "language": "en",
                "confidence": 0.9,
                "text": "unsafe",
                "tasks": [{"action": "pick", "confidence": 0.9}],
            }
        )
    )
    node._command_callback(msg)

    assert scheduled == []


def test_execution_boundary_accepts_valid_command_with_generated_ids(monkeypatch):
    _install_ros_stubs(monkeypatch)
    sys.modules.pop("ur10e_control_system.task_manager_node", None)
    module = importlib.import_module("ur10e_control_system.task_manager_node")

    node = object.__new__(module.TaskManagerNode)
    node.stop_generation = 0
    node.queue_sequence = itertools.count()
    node.task_queue = asyncio.PriorityQueue()
    node.loop = types.SimpleNamespace(
        call_soon_threadsafe=lambda callback, *args: callback(*args)
    )
    node.get_logger = lambda: types.SimpleNamespace(
        info=lambda *args: None,
        warning=lambda *args: None,
        error=lambda *args: None,
    )

    msg = types.SimpleNamespace(
        data=json.dumps(
            {
                "id": "cmd-1",
                "type": "command",
                "language": "en",
                "confidence": 0.9,
                "text": "pick the green cube",
                "tasks": [
                    {
                        "id": "tsk-1",
                        "action": "pick",
                        "target": {
                            "key": "trg-1",
                            "object": {
                                "key": "obj-1",
                                "class": "cube",
                                "attributes": {
                                    "color": "green",
                                    "size": None,
                                    "shape": None,
                                    "material": None,
                                    "state": None,
                                },
                                "prompt": "green cube",
                            },
                            "search_space": [],
                            "selection": None,
                        },
                        "placement": None,
                        "modifiers": None,
                        "confidence": 0.9,
                    }
                ],
            }
        )
    )
    node._command_callback(msg)

    _, _, generation, task = node.task_queue.get_nowait()
    assert generation == 0
    assert task["id"] == "tsk-1"


def test_command_is_rejected_atomically_when_queue_lacks_capacity(monkeypatch):
    _install_ros_stubs(monkeypatch)
    sys.modules.pop("ur10e_control_system.task_manager_node", None)
    module = importlib.import_module("ur10e_control_system.task_manager_node")

    node = object.__new__(module.TaskManagerNode)
    node.stop_generation = 0
    node.queue_sequence = itertools.count()
    node.task_queue = asyncio.PriorityQueue(maxsize=2)
    node.task_queue.put_nowait((1, 0, 0, {"action": "go_home"}))
    node.loop = types.SimpleNamespace(
        call_soon_threadsafe=lambda callback, *args: callback(*args)
    )
    node.get_logger = lambda: types.SimpleNamespace(
        info=lambda *args: None,
        warning=lambda *args: None,
        error=lambda *args: None,
    )

    msg = types.SimpleNamespace(
        data=json.dumps(
            {
                "type": "command",
                "language": "en",
                "confidence": 0.9,
                "text": "open, then close",
                "tasks": [
                    {
                        "action": action,
                        "target": None,
                        "placement": None,
                        "modifiers": None,
                        "confidence": 0.9,
                    }
                    for action in ("open_gripper", "close_gripper")
                ],
            }
        )
    )
    node._command_callback(msg)

    assert node.task_queue.qsize() == 1
    assert node.task_queue.get_nowait()[3]["action"] == "go_home"


def test_goal_message_preserves_validated_execution_modifiers(monkeypatch):
    _install_ros_stubs(monkeypatch)
    sys.modules.pop("ur10e_control_system.task_manager_node", None)
    module = importlib.import_module("ur10e_control_system.task_manager_node")
    module.BaseAction.Goal = type("Goal", (), {"__init__": lambda self: None})
    node = object.__new__(module.TaskManagerNode)

    goal = asyncio.run(
        node.create_goal_msg(
            {
                "action": "go_home",
                "modifiers": {"speed": "slow", "precision": "high"},
            }
        )
    )

    assert goal.speed == "slow"
    assert goal.precision == "high"


def test_goal_message_uses_fresh_perception_coordinates(monkeypatch):
    _install_ros_stubs(monkeypatch)
    sys.modules.pop("ur10e_control_system.task_manager_node", None)
    module = importlib.import_module("ur10e_control_system.task_manager_node")
    module.BaseAction.Goal = type("Goal", (), {"__init__": lambda self: None})
    node = object.__new__(module.TaskManagerNode)
    node.target_source_mode = "perception"
    node.get_logger = lambda: types.SimpleNamespace(info=lambda *args: None)
    requested_at = []

    async def wait_for_perception_pose(timestamp):
        requested_at.append(timestamp)
        return 0.25, -0.10, 0.90

    node._wait_for_perception_pose = wait_for_perception_pose
    goal = asyncio.run(
        node.create_goal_msg(
            {
                "action": "pick",
                "target": {
                    "object": {"prompt": "green cube"},
                },
                "modifiers": None,
            },
            target_requested_at=42.0,
        )
    )

    assert requested_at == [42.0]
    assert (goal.x, goal.y, goal.z) == (0.25, -0.10, 0.90)
    assert goal.object_name == ""
