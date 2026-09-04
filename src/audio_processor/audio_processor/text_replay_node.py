"""Replay a versioned text transcript onto the speech-recognition ROS topic."""

import os
from pathlib import Path

import rclpy
from rclpy.node import Node
from std_msgs.msg import String


DEFAULT_TRANSCRIPT_PATH = "/workspace/evaluation/recognized_text_smoke.txt"
DEFAULT_INTERVAL_SECONDS = 1.0


def load_transcript(path: str | Path) -> list[str]:
    """Load non-empty, non-comment transcript lines in source order."""
    transcript_path = Path(path)
    try:
        lines = transcript_path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ValueError(f"Cannot read transcript {transcript_path}: {exc}") from exc

    commands = [
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not commands:
        raise ValueError(f"Transcript {transcript_path} contains no commands")
    return commands


class TextReplayNode(Node):
    """Publish transcript entries after a downstream subscriber is available."""

    def __init__(self):
        super().__init__("recognized_text_replay")

        self.declare_parameter(
            "transcript_path",
            os.environ.get("TEXT_REPLAY_FILE", DEFAULT_TRANSCRIPT_PATH),
        )
        self.declare_parameter(
            "interval_seconds",
            float(os.environ.get("TEXT_REPLAY_INTERVAL_SECONDS", DEFAULT_INTERVAL_SECONDS)),
        )
        self.declare_parameter(
            "repeat",
            os.environ.get("TEXT_REPLAY_REPEAT", "false").lower()
            in {"1", "true", "yes"},
        )

        transcript_path = self.get_parameter("transcript_path").value
        interval_seconds = float(self.get_parameter("interval_seconds").value)
        self.repeat = bool(self.get_parameter("repeat").value)
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")

        self.commands = load_transcript(transcript_path)
        self.index = 0
        self.publisher = self.create_publisher(String, "/recognized_text", 10)
        self.timer = self.create_timer(interval_seconds, self._publish_next)
        self.get_logger().info(
            f"Loaded {len(self.commands)} transcript entries from {transcript_path}"
        )

    def _publish_next(self):
        if self.publisher.get_subscription_count() == 0:
            return

        message = String()
        message.data = self.commands[self.index]
        self.publisher.publish(message)
        self.get_logger().info(
            f"Replayed transcript entry {self.index + 1}/{len(self.commands)}: "
            f"{message.data}"
        )
        self.index += 1

        if self.index < len(self.commands):
            return
        if self.repeat:
            self.index = 0
            return

        self.timer.cancel()
        self.get_logger().info("Transcript replay completed")


def main(args=None):
    rclpy.init(args=args)
    node = TextReplayNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
