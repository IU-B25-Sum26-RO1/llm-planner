import importlib
import sys
import types
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src" / "audio_processor"))


def _load_module(monkeypatch):
    rclpy = types.ModuleType("rclpy")
    rclpy.node = types.ModuleType("rclpy.node")
    rclpy.node.Node = type("Node", (), {})
    std_msgs = types.ModuleType("std_msgs")
    std_msgs.msg = types.ModuleType("std_msgs.msg")
    std_msgs.msg.String = type("String", (), {"__init__": lambda self: None})

    monkeypatch.setitem(sys.modules, "rclpy", rclpy)
    monkeypatch.setitem(sys.modules, "rclpy.node", rclpy.node)
    monkeypatch.setitem(sys.modules, "std_msgs", std_msgs)
    monkeypatch.setitem(sys.modules, "std_msgs.msg", std_msgs.msg)
    sys.modules.pop("audio_processor.text_replay_node", None)
    return importlib.import_module("audio_processor.text_replay_node")


def test_versioned_transcript_has_ordered_microphone_free_inputs(monkeypatch):
    module = _load_module(monkeypatch)

    commands = module.load_transcript(
        ROOT / "evaluation" / "recognized_text_smoke.txt"
    )

    assert len(commands) >= 4
    assert commands[0] == "Возьми зелёный куб."
    assert commands[-1] == "Остановись."


def test_transcript_rejects_missing_or_empty_input(monkeypatch, tmp_path):
    module = _load_module(monkeypatch)
    empty = tmp_path / "empty.txt"
    empty.write_text("\n# only a comment\n", encoding="utf-8")

    with pytest.raises(ValueError, match="contains no commands"):
        module.load_transcript(empty)
    with pytest.raises(ValueError, match="Cannot read transcript"):
        module.load_transcript(tmp_path / "missing.txt")


def test_replay_waits_for_subscriber_and_stops_after_last_entry(monkeypatch):
    module = _load_module(monkeypatch)

    class Publisher:
        def __init__(self):
            self.subscribers = 0
            self.messages = []

        def get_subscription_count(self):
            return self.subscribers

        def publish(self, message):
            self.messages.append(message.data)

    class Timer:
        canceled = False

        def cancel(self):
            self.canceled = True

    node = object.__new__(module.TextReplayNode)
    node.commands = ["first", "second"]
    node.index = 0
    node.repeat = False
    node.publisher = Publisher()
    node.timer = Timer()
    node.get_logger = lambda: types.SimpleNamespace(info=lambda *args: None)

    node._publish_next()
    assert node.index == 0

    node.publisher.subscribers = 1
    node._publish_next()
    node._publish_next()

    assert node.publisher.messages == ["first", "second"]
    assert node.timer.canceled
