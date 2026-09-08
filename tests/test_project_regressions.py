import importlib
import json
import sys
import types
import xml.etree.ElementTree as ET
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src" / "decomposer"))

from decomposer.json_utils import validate_command_dict  # noqa: E402


def _prompt_output_examples(text):
    position = 0
    while True:
        marker = text.find("Output:", position)
        if marker < 0:
            return
        start = text.find("{", marker)
        if start < 0:
            raise AssertionError("Output section has no JSON object")

        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            character = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif character == "\\":
                    escaped = True
                elif character == '"':
                    in_string = False
            elif character == '"':
                in_string = True
            elif character == "{":
                depth += 1
            elif character == "}":
                depth -= 1
                if depth == 0:
                    end = index + 1
                    break
        else:
            raise AssertionError("Output JSON object has unmatched braces")

        yield text[start:end]
        position = end


def test_every_prompt_output_example_is_valid_json():
    prompt = (ROOT / "prompts" / "decomposer_system_prompt.txt").read_text()
    examples = list(_prompt_output_examples(prompt))

    assert len(examples) >= 5
    for example in examples:
        validate_command_dict(json.loads(example))


def test_documented_demo_objects_exist_in_gazebo_world():
    world = ET.parse(ROOT / "src" / "ur10e_scene" / "worlds" / "station.world")
    model_names = {model.attrib["name"] for model in world.findall(".//model")}

    assert {"green_cube", "white_tray"} <= model_names


def test_audio_model_path_supports_names_and_absolute_paths(monkeypatch):
    rclpy = types.ModuleType("rclpy")
    rclpy.node = types.ModuleType("rclpy.node")
    rclpy.node.Node = type("Node", (), {})
    std_msgs = types.ModuleType("std_msgs")
    std_msgs.msg = types.ModuleType("std_msgs.msg")
    std_msgs.msg.String = type("String", (), {})
    recorder = types.ModuleType("audio_processor.recorder")
    recorder.Recorder = type("Recorder", (), {})
    recognizer = types.ModuleType("audio_processor.recognizer")
    recognizer.Recognizer = type("Recognizer", (), {})

    monkeypatch.setitem(sys.modules, "rclpy", rclpy)
    monkeypatch.setitem(sys.modules, "rclpy.node", rclpy.node)
    monkeypatch.setitem(sys.modules, "std_msgs", std_msgs)
    monkeypatch.setitem(sys.modules, "std_msgs.msg", std_msgs.msg)
    monkeypatch.setitem(sys.modules, "audio_processor.recorder", recorder)
    monkeypatch.setitem(sys.modules, "audio_processor.recognizer", recognizer)
    sys.path.insert(0, str(ROOT / "src" / "audio_processor"))
    sys.modules.pop("audio_processor.audio_processor_node", None)
    module = importlib.import_module("audio_processor.audio_processor_node")

    assert module.resolve_model_path("vosk-model") == "/workspace/models/vosk-model"
    assert module.resolve_model_path("/models/custom") == "/models/custom"


def test_docker_build_uses_pinned_uv_and_checked_lockfile():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")

    assert "ghcr.io/astral-sh/uv:latest" not in dockerfile
    assert "uv export --locked --no-dev --no-emit-project" in dockerfile


def test_python_and_vosk_targets_match_ros_humble_linux_runtime():
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert (ROOT / ".python-version").read_text(encoding="utf-8").strip() == "3.10"
    assert 'requires-python = ">=3.10,<3.11"' in pyproject
    assert '"vosk>=0.3.45; sys_platform == \'linux\'"' in pyproject


def test_base_action_carries_validated_execution_modifiers():
    action_definition = (
        ROOT / "src" / "robot_interfaces" / "action" / "BaseAction.action"
    ).read_text(encoding="utf-8")

    goal_definition = action_definition.split("---", 1)[0]
    assert "string speed" in goal_definition
    assert "string precision" in goal_definition
