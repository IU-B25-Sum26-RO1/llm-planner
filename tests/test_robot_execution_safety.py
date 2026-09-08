import importlib
import sys
import types
from pathlib import Path

import numpy as np
import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "ur10e_control_system"))


def _message_type(name):
    return type(name, (), {"__init__": lambda self: None})


def _install_ros_stubs(monkeypatch):
    rclpy = types.ModuleType("rclpy")
    rclpy.action = types.ModuleType("rclpy.action")
    rclpy.action.ActionServer = type("ActionServer", (), {})
    rclpy.action.CancelResponse = types.SimpleNamespace(ACCEPT="accept")
    rclpy.action.GoalResponse = types.SimpleNamespace(ACCEPT="accept", REJECT="reject")
    rclpy.callback_groups = types.ModuleType("rclpy.callback_groups")
    rclpy.callback_groups.ReentrantCallbackGroup = type("ReentrantCallbackGroup", (), {})
    rclpy.executors = types.ModuleType("rclpy.executors")
    rclpy.executors.MultiThreadedExecutor = type("MultiThreadedExecutor", (), {})
    rclpy.node = types.ModuleType("rclpy.node")
    rclpy.node.Node = type("Node", (), {})
    rclpy.qos = types.ModuleType("rclpy.qos")
    rclpy.qos.QoSDurabilityPolicy = types.SimpleNamespace(TRANSIENT_LOCAL="transient")
    rclpy.qos.QoSReliabilityPolicy = types.SimpleNamespace(RELIABLE="reliable")
    rclpy.qos.QoSProfile = type("QoSProfile", (), {"__init__": lambda self, **kwargs: None})

    gazebo_msgs = types.ModuleType("gazebo_msgs")
    gazebo_msgs.msg = types.ModuleType("gazebo_msgs.msg")
    gazebo_msgs.msg.EntityState = _message_type("EntityState")
    gazebo_msgs.msg.ModelStates = _message_type("ModelStates")
    gazebo_msgs.srv = types.ModuleType("gazebo_msgs.srv")
    gazebo_msgs.srv.SetEntityState = type("SetEntityState", (), {})

    sensor_msgs = types.ModuleType("sensor_msgs")
    sensor_msgs.msg = types.ModuleType("sensor_msgs.msg")
    sensor_msgs.msg.JointState = _message_type("JointState")
    std_msgs = types.ModuleType("std_msgs")
    std_msgs.msg = types.ModuleType("std_msgs.msg")
    std_msgs.msg.Float64MultiArray = _message_type("Float64MultiArray")
    std_msgs.msg.String = _message_type("String")
    trajectory_msgs = types.ModuleType("trajectory_msgs")
    trajectory_msgs.msg = types.ModuleType("trajectory_msgs.msg")
    trajectory_msgs.msg.JointTrajectory = _message_type("JointTrajectory")
    trajectory_msgs.msg.JointTrajectoryPoint = type(
        "JointTrajectoryPoint",
        (),
        {
            "__init__": lambda self: setattr(
                self, "time_from_start", types.SimpleNamespace(sec=0, nanosec=0)
            )
        },
    )

    robot_interfaces = types.ModuleType("robot_interfaces")
    robot_interfaces.action = types.ModuleType("robot_interfaces.action")
    robot_interfaces.action.BaseAction = type("BaseAction", (), {})
    robot_interfaces.srv = types.ModuleType("robot_interfaces.srv")
    robot_interfaces.srv.GripperControl = type("GripperControl", (), {})

    kinematics = types.ModuleType("ur10e_control_system.ur_kinematics")
    kinematics.URKinematics = type("URKinematics", (), {})
    kinematics.make_transform = lambda orientation, position: (orientation, position)

    modules = {
        "rclpy": rclpy,
        "rclpy.action": rclpy.action,
        "rclpy.callback_groups": rclpy.callback_groups,
        "rclpy.executors": rclpy.executors,
        "rclpy.node": rclpy.node,
        "rclpy.qos": rclpy.qos,
        "gazebo_msgs": gazebo_msgs,
        "gazebo_msgs.msg": gazebo_msgs.msg,
        "gazebo_msgs.srv": gazebo_msgs.srv,
        "sensor_msgs": sensor_msgs,
        "sensor_msgs.msg": sensor_msgs.msg,
        "std_msgs": std_msgs,
        "std_msgs.msg": std_msgs.msg,
        "trajectory_msgs": trajectory_msgs,
        "trajectory_msgs.msg": trajectory_msgs.msg,
        "robot_interfaces": robot_interfaces,
        "robot_interfaces.action": robot_interfaces.action,
        "robot_interfaces.srv": robot_interfaces.srv,
        "ur10e_control_system.ur_kinematics": kinematics,
    }
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)


def _robot_module(monkeypatch):
    _install_ros_stubs(monkeypatch)
    sys.modules.pop("ur10e_control_system.robot_interface_node", None)
    return importlib.import_module("ur10e_control_system.robot_interface_node")


def test_cancellation_holds_the_current_joint_positions(monkeypatch):
    module = _robot_module(monkeypatch)
    published = []
    interface = object.__new__(module.UR10eInterface)
    interface.kin = types.SimpleNamespace(movable_names=list(module.ARM_JOINTS))
    interface._current_arm_q = lambda: np.arange(6, dtype=float)
    interface._traj_pub = types.SimpleNamespace(publish=published.append)

    with pytest.raises(module.ActionCanceled):
        interface._raise_if_cancel_requested(
            types.SimpleNamespace(is_cancel_requested=True)
        )

    assert published[0].joint_names == module.ARM_JOINTS
    assert published[0].points[0].positions == [0.0, 1.0, 2.0, 3.0, 4.0, 5.0]


def test_pick_reports_failure_when_virtual_attachment_fails(monkeypatch):
    module = _robot_module(monkeypatch)
    interface = object.__new__(module.UR10eInterface)
    interface._held = None
    interface.hover_height = 0.25
    interface.grasp_height = 0.135
    interface._detach = lambda: None
    interface._get_object_position = lambda name, **kwargs: np.array([0.1, 0.2, 0.3])
    interface._command_gripper = lambda **kwargs: None
    interface._move_tool_to = lambda *args, **kwargs: (True, "")
    interface._attach = lambda name: False

    success, error = interface._pick("green_cube")

    assert not success
    assert "Failed to attach" in error


def test_action_server_rejects_invalid_goal_requests(monkeypatch):
    module = _robot_module(monkeypatch)
    interface = object.__new__(module.UR10eInterface)
    interface.get_logger = lambda: types.SimpleNamespace(warning=lambda *args: None)

    accepted = interface.goal_callback(
        types.SimpleNamespace(
            task_type="pick", object_name="green_cube", x=0.0, y=0.0, z=0.0
        )
    )
    unknown = interface.goal_callback(
        types.SimpleNamespace(
            task_type="press_button", object_name="", x=0.0, y=0.0, z=0.0
        )
    )
    missing_object = interface.goal_callback(
        types.SimpleNamespace(task_type="pick", object_name="", x=0.0, y=0.0, z=0.0)
    )
    non_finite = interface.goal_callback(
        types.SimpleNamespace(
            task_type="go_home", object_name="", x=float("nan"), y=0.0, z=0.0
        )
    )
    invalid_modifiers = interface.goal_callback(
        types.SimpleNamespace(
            task_type="go_home",
            object_name="",
            x=0.0,
            y=0.0,
            z=0.0,
            speed="unbounded",
            precision="",
        )
    )

    assert accepted == "accept"
    assert unknown == "reject"
    assert missing_object == "reject"
    assert non_finite == "reject"
    assert invalid_modifiers == "reject"


def test_cartesian_target_outside_workspace_is_rejected_before_ik(monkeypatch):
    module = _robot_module(monkeypatch)
    interface = object.__new__(module.UR10eInterface)
    interface.workspace_min = module.DEFAULT_WORKSPACE_MIN
    interface.workspace_max = module.DEFAULT_WORKSPACE_MAX

    success, error = interface._move_tool_to([100.0, 0.0, 1.0])

    assert not success
    assert "outside configured workspace" in error


def test_place_requires_a_held_object(monkeypatch):
    module = _robot_module(monkeypatch)
    interface = object.__new__(module.UR10eInterface)
    interface._held = None

    success, error = interface._place("white_tray", None)

    assert not success
    assert "not holding" in error


def test_execution_modifiers_are_bounded_and_affect_motion_checks(monkeypatch):
    module = _robot_module(monkeypatch)
    interface = object.__new__(module.UR10eInterface)
    interface.move_speed = 0.8
    interface.max_move_speed = 1.0
    interface.joint_goal_tolerance = 0.05
    interface._active_speed = "fast"
    interface._active_precision = "high"

    assert interface._effective_move_speed() == pytest.approx(0.9)
    assert interface._effective_joint_tolerance() == pytest.approx(0.025)

    interface._active_precision = "low"
    assert interface._effective_move_speed() == pytest.approx(1.0)
    assert interface._effective_joint_tolerance() == pytest.approx(0.1)
