import json
import os

import rclpy
from cv_bridge import CvBridge
from geometry_msgs.msg import PoseStamped
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.time import Time
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import String
from tf2_ros import Buffer, TransformException, TransformListener

from scene_analyzer.detection_utils import select_best_detection
from scene_analyzer.geometry import median_depth_in_bbox, pixel_to_camera_xyz, transform_point


class ObjectPoseEstimatorNode(Node):
    def __init__(self):
        super().__init__("object_pose_estimator")

        self.depth_topic = os.environ.get("PERCEPTION_DEPTH_TOPIC", "/camera/camera/depth/image_raw")
        self.camera_info_topic = os.environ.get(
            "PERCEPTION_CAMERA_INFO_TOPIC",
            "/camera/camera/camera_info",
        )
        self.detections_topic = os.environ.get("PERCEPTION_DETECTIONS_TOPIC", "/perception/detections")
        self.target_pose_topic = os.environ.get("PERCEPTION_TARGET_POSE_TOPIC", "/perception/target_pose")
        self.world_frame = os.environ.get("PERCEPTION_WORLD_FRAME", "world")
        self.min_confidence = float(os.environ.get("YOLO_CONF", "0.15"))
        self.depth_crop_ratio = float(os.environ.get("PERCEPTION_DEPTH_CROP_RATIO", "0.35"))

        self.bridge = CvBridge()
        self.camera_info = None
        self.depth_image = None
        self.depth_header = None
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        self.depth_sub = self.create_subscription(Image, self.depth_topic, self.depth_callback, 1)
        self.camera_info_sub = self.create_subscription(
            CameraInfo,
            self.camera_info_topic,
            self.camera_info_callback,
            1,
        )
        self.detections_sub = self.create_subscription(
            String,
            self.detections_topic,
            self.detections_callback,
            10,
        )
        self.pose_pub = self.create_publisher(PoseStamped, self.target_pose_topic, 10)

        self.get_logger().info(
            "Object Pose Estimator | depth=%s camera_info=%s detections=%s pose=%s world_frame=%s"
            % (
                self.depth_topic,
                self.camera_info_topic,
                self.detections_topic,
                self.target_pose_topic,
                self.world_frame,
            )
        )

    def depth_callback(self, msg: Image) -> None:
        try:
            self.depth_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")
            self.depth_header = msg.header
        except Exception as exc:
            self.get_logger().error(f"Object Pose Estimator | Failed to decode depth image: {exc}")

    def camera_info_callback(self, msg: CameraInfo) -> None:
        self.camera_info = msg

    def detections_callback(self, msg: String) -> None:
        if self.depth_image is None or self.camera_info is None:
            self.get_logger().warn("Object Pose Estimator | Waiting for depth image and camera info")
            return

        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().error("Object Pose Estimator | Invalid detections JSON")
            return

        detections = payload.get("detections", [])
        if not isinstance(detections, list):
            self.get_logger().error("Object Pose Estimator | Detections payload must contain a list")
            return

        best = select_best_detection(detections, self.min_confidence)
        if best is None:
            self.get_logger().warn("Object Pose Estimator | No detection above confidence threshold")
            return

        depth_sample = median_depth_in_bbox(
            self.depth_image,
            best.get("bbox", []),
            crop_ratio=self.depth_crop_ratio,
        )
        if depth_sample is None:
            self.get_logger().warn("Object Pose Estimator | No valid depth inside detection bbox")
            return

        u, v, depth_m = depth_sample
        try:
            point_camera = pixel_to_camera_xyz(u, v, depth_m, self.camera_info.k)
        except ValueError as exc:
            self.get_logger().error(f"Object Pose Estimator | Invalid camera projection: {exc}")
            return

        source_frame = self.camera_info.header.frame_id or self.depth_header.frame_id
        try:
            transform = self.tf_buffer.lookup_transform(
                self.world_frame,
                source_frame,
                Time(),
                timeout=Duration(seconds=0.2),
            )
            point_world = transform_point(point_camera, transform)
            frame_id = self.world_frame
        except TransformException as exc:
            self.get_logger().warn(
                f"Object Pose Estimator | TF {source_frame}->{self.world_frame} unavailable: {exc}; "
                "publishing camera-frame pose"
            )
            point_world = point_camera
            frame_id = source_frame

        pose = PoseStamped()
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.header.frame_id = frame_id
        pose.pose.position.x = float(point_world[0])
        pose.pose.position.y = float(point_world[1])
        pose.pose.position.z = float(point_world[2])
        pose.pose.orientation.w = 1.0
        self.pose_pub.publish(pose)

        self.get_logger().info(
            "Object Pose Estimator | %s %.2f bbox=%s -> pose=(%.3f, %.3f, %.3f) frame=%s"
            % (
                best.get("class"),
                float(best.get("confidence", 0.0)),
                [round(float(value), 1) for value in best.get("bbox", [])],
                pose.pose.position.x,
                pose.pose.position.y,
                pose.pose.position.z,
                frame_id,
            )
        )


def main(args=None):
    rclpy.init(args=args)
    node = ObjectPoseEstimatorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
