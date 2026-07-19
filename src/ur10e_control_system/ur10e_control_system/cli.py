"""Console command sender for the UR10e basic policies.

Examples
--------
    ros2 run ur10e_control_system cli move_to_object green_cube
    ros2 run ur10e_control_system cli home
    ros2 run ur10e_control_system cli forward 0.1
    ros2 run ur10e_control_system cli move_to 0.3 0.2 1.05
    ros2 run ur10e_control_system cli grasp
    ros2 run ur10e_control_system cli release
    ros2 run ur10e_control_system cli pick green_cube
    ros2 run ur10e_control_system cli place white_tray
"""

import sys

import rclpy  # type: ignore
from rclpy.action import ActionClient  # type: ignore
from rclpy.node import Node  # type: ignore

from robot_interfaces.action import BaseAction  # type: ignore


DIRECTIONS = {"forward", "backward", "left", "right", "up", "down"}
USAGE = (
    "Usage:\n"
    "  cli move_to_object <name>\n"
    "  cli move_to <x> <y> <z>\n"
    "  cli pick <name>\n"
    "  cli place <name> | place <x> <y> <z>\n"
    "  cli home\n"
    "  cli <forward|backward|left|right|up|down> [distance]\n"
    "  cli grasp | release\n"
)


class CommandSender(Node):
    def __init__(self):
        super().__init__("ur10e_cli")
        self._action_client = ActionClient(self, BaseAction, "/execute/base_action")

    def send_action(self, task_type, object_name="", x=0.0, y=0.0, z=0.0):
        if not self._action_client.wait_for_server(timeout_sec=10.0):
            self.get_logger().error("Action server /execute/base_action unavailable")
            return False

        goal = BaseAction.Goal()
        goal.task_type = task_type
        goal.object_name = object_name
        goal.x, goal.y, goal.z = float(x), float(y), float(z)

        self.get_logger().info(f"Sending goal: {task_type} {object_name} ({x}, {y}, {z})")
        send_future = self._action_client.send_goal_async(
            goal, feedback_callback=self._feedback_cb
        )
        rclpy.spin_until_future_complete(self, send_future)
        goal_handle = send_future.result()
        if not goal_handle.accepted:
            self.get_logger().error("Goal rejected")
            return False

        result_future = goal_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        result = result_future.result().result
        self.get_logger().info(
            f"Result: success={result.success} error='{result.error_message}'"
        )
        return result.success

    def _feedback_cb(self, feedback_msg):
        self.get_logger().info(f"Feedback: {feedback_msg.feedback.current_state}")


def _parse_and_run(node: CommandSender, argv):
    command = argv[0]

    if command in ("grasp", "release"):
        return node.send_action(command)

    if command == "home":
        return node.send_action("home")

    if command == "move_to_object":
        if len(argv) < 2:
            node.get_logger().error("move_to_object requires an object name")
            return False
        return node.send_action("move_to_object", object_name=argv[1])

    if command == "move_to":
        if len(argv) < 4:
            node.get_logger().error("move_to requires x y z")
            return False
        return node.send_action("move_to", x=argv[1], y=argv[2], z=argv[3])

    if command == "pick":
        if len(argv) < 2:
            node.get_logger().error("pick requires an object name")
            return False
        return node.send_action("pick", object_name=argv[1])

    if command == "place":
        if len(argv) == 2:
            return node.send_action("place", object_name=argv[1])
        if len(argv) >= 4:
            return node.send_action("place", x=argv[1], y=argv[2], z=argv[3])
        node.get_logger().error("place requires a name or x y z")
        return False

    if command in DIRECTIONS:
        distance = float(argv[1]) if len(argv) > 1 else 0.0
        return node.send_action(command, x=distance)

    node.get_logger().error(f"Unknown command '{command}'\n{USAGE}")
    return False


def main(args=None):
    rclpy.init(args=args)
    node = CommandSender()

    argv = sys.argv[1:]
    if not argv:
        node.get_logger().info(USAGE)
        node.destroy_node()
        rclpy.shutdown()
        return

    try:
        success = _parse_and_run(node, argv)
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
