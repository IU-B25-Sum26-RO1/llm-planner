import json
import os
import sys
import time

import rclpy
from geometry_msgs.msg import PoseStamped
from rclpy.node import Node
from std_msgs.msg import String


class PerceptionSmokeTest(Node):
    def __init__(self):
        super().__init__("perception_smoke_test")
        self.pose = None
        self.target_pub = self.create_publisher(String, "/to_track/target", 10)
        self.pose_sub = self.create_subscription(
            PoseStamped,
            "/perception/target_pose",
            self.pose_callback,
            10,
        )

    def pose_callback(self, msg: PoseStamped) -> None:
        self.pose = msg


def main(args=None):
    rclpy.init(args=args)
    node = PerceptionSmokeTest()
    target_prompt = "green cube"
    if args is None:
        args = sys.argv[1:]
    if args:
        target_prompt = " ".join(args)

    target = {
        "key": "smoke_target",
        "object": {
            "key": "smoke_object",
            "class": "cube",
            "attributes": {
                "color": "green" if "green" in target_prompt else None,
                "size": None,
                "shape": None,
                "material": None,
                "state": None,
            },
            "prompt": target_prompt,
        },
        "search_space": [],
        "selection": None,
    }

    msg = String()
    msg.data = json.dumps(target, ensure_ascii=False)
    deadline = time.monotonic() + float(os.environ.get("PERCEPTION_SMOKE_TIMEOUT", "60.0"))
    try:
        while time.monotonic() < deadline and rclpy.ok():
            node.target_pub.publish(msg)
            rclpy.spin_once(node, timeout_sec=0.2)
            if node.pose is not None:
                p = node.pose.pose.position
                node.get_logger().info(
                    "PASS target_pose=(%.3f, %.3f, %.3f) frame=%s"
                    % (p.x, p.y, p.z, node.pose.header.frame_id)
                )
                node.destroy_node()
                rclpy.shutdown()
                return 0
        node.get_logger().error("FAIL no /perception/target_pose received")
        return 1
    finally:
        if rclpy.ok():
            node.destroy_node()
            rclpy.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
