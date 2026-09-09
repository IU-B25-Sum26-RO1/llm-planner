import importlib
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "ur10e_control_system"))


def _install_ros_stubs(monkeypatch):
    rclpy = types.ModuleType("rclpy")
    rclpy.spin_until_future_complete = lambda *args: None
    rclpy.action = types.ModuleType("rclpy.action")
    rclpy.action.ActionClient = type("ActionClient", (), {})
    rclpy.node = types.ModuleType("rclpy.node")
    rclpy.node.Node = type("Node", (), {})

    robot_interfaces = types.ModuleType("robot_interfaces")
    robot_interfaces.action = types.ModuleType("robot_interfaces.action")
    robot_interfaces.action.BaseAction = type("BaseAction", (), {})
    robot_interfaces.srv = types.ModuleType("robot_interfaces.srv")
    robot_interfaces.srv.GripperControl = type("GripperControl", (), {})

    monkeypatch.setitem(sys.modules, "rclpy", rclpy)
    monkeypatch.setitem(sys.modules, "rclpy.action", rclpy.action)
    monkeypatch.setitem(sys.modules, "rclpy.node", rclpy.node)
    monkeypatch.setitem(sys.modules, "robot_interfaces", robot_interfaces)
    monkeypatch.setitem(sys.modules, "robot_interfaces.action", robot_interfaces.action)
    monkeypatch.setitem(sys.modules, "robot_interfaces.srv", robot_interfaces.srv)


def test_cli_maps_home_and_gripper_commands_to_supported_interfaces(monkeypatch):
    _install_ros_stubs(monkeypatch)
    sys.modules.pop("ur10e_control_system.cli", None)
    cli = importlib.import_module("ur10e_control_system.cli")

    calls = []
    node = types.SimpleNamespace(
        send_action=lambda *args, **kwargs: calls.append(("action", args, kwargs)) or True,
        send_gripper_command=lambda **kwargs: calls.append(("gripper", (), kwargs)) or True,
        get_logger=lambda: types.SimpleNamespace(error=lambda *args: None),
    )

    assert cli._parse_and_run(node, ["home"])
    assert cli._parse_and_run(node, ["grasp"])
    assert cli._parse_and_run(node, ["release"])

    assert calls == [
        ("action", ("go_home",), {}),
        ("gripper", (), {"activate": True}),
        ("gripper", (), {"activate": False}),
    ]
