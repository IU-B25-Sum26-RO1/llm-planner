import json
import os
import time

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String

from scene_analyzer.detection_utils import detections_from_yolo_result, select_best_detection
from scene_analyzer.target_utils import (
    parse_target_message,
    target_prompt,
    target_prompts,
)


class YoloWorldDetectorNode(Node):
    def __init__(self):
        super().__init__("yolo_world_detector")

        self.image_topic = os.environ.get("PERCEPTION_IMAGE_TOPIC", "/camera/camera/image_raw")
        self.target_topic = os.environ.get("PERCEPTION_TARGET_TOPIC", "/to_track/target")
        self.detections_topic = os.environ.get("PERCEPTION_DETECTIONS_TOPIC", "/perception/detections")
        self.debug_image_topic = os.environ.get("PERCEPTION_DEBUG_IMAGE_TOPIC", "/perception/debug_image")

        self.model_name = os.environ.get("YOLO_WORLD_MODEL", "yolov8s-worldv2.pt")
        self.device = os.environ.get("PERCEPTION_DEVICE", "cpu")
        self.confidence = float(os.environ.get("YOLO_CONF", "0.15"))
        self.max_fps = float(os.environ.get("PERCEPTION_MAX_FPS", "3.0"))
        self.publish_all = os.environ.get("PERCEPTION_PUBLISH_ALL", "0") == "1"

        self.bridge = CvBridge()
        self.model = None
        self.current_target = None
        self.current_prompts = []
        self.last_processed_at = 0.0

        self.target_sub = self.create_subscription(
            String,
            self.target_topic,
            self.target_callback,
            10,
        )
        self.image_sub = self.create_subscription(
            Image,
            self.image_topic,
            self.image_callback,
            1,
        )
        self.detections_pub = self.create_publisher(String, self.detections_topic, 10)
        self.debug_image_pub = self.create_publisher(Image, self.debug_image_topic, 3)

        self.get_logger().info(
            "YOLO-World Detector | image=%s target=%s detections=%s model=%s device=%s conf=%.2f"
            % (
                self.image_topic,
                self.target_topic,
                self.detections_topic,
                self.model_name,
                self.device,
                self.confidence,
            )
        )

    def target_callback(self, msg: String) -> None:
        target = parse_target_message(msg.data)
        prompts = target_prompts(target)
        if not prompts:
            self.get_logger().warn("YOLO-World Detector | Target has no usable prompt")
            self.current_target = None
            self.current_prompts = []
            return

        self.current_target = target
        self.current_prompts = prompts
        if self._ensure_model():
            self.model.set_classes(prompts)
        self.get_logger().info(
            f"YOLO-World Detector | New target prompts: {', '.join(prompts)}"
        )

    def image_callback(self, msg: Image) -> None:
        if not self.current_prompts:
            return
        if self.max_fps > 0.0 and time.monotonic() - self.last_processed_at < 1.0 / self.max_fps:
            return
        if not self._ensure_model():
            return

        self.last_processed_at = time.monotonic()
        try:
            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
            result = self.model.predict(
                frame,
                conf=self.confidence,
                device=self.device,
                verbose=False,
            )[0]
            detections = detections_from_yolo_result(result)
            best = select_best_detection(detections, self.confidence)
            payload = {
                "header": {
                    "stamp": {
                        "sec": int(msg.header.stamp.sec),
                        "nanosec": int(msg.header.stamp.nanosec),
                    },
                    "frame_id": msg.header.frame_id,
                },
                "target_prompt": target_prompt(self.current_target),
                "classes": self.current_prompts,
                "detections": detections if self.publish_all else ([best] if best else []),
            }
            out = String()
            out.data = json.dumps(payload, ensure_ascii=False)
            self.detections_pub.publish(out)
            self._publish_debug_image(frame, best, msg)
        except Exception as exc:
            self.get_logger().error(f"YOLO-World Detector | Detection failed: {exc}")

    def _ensure_model(self) -> bool:
        if self.model is not None:
            return True
        try:
            from ultralytics import YOLOWorld
        except Exception as exc:
            self.get_logger().error(
                "YOLO-World Detector | ultralytics is not installed or failed to import: "
                f"{exc}"
            )
            return False

        try:
            self.model = YOLOWorld(self.model_name)
            if self.current_prompts:
                self.model.set_classes(self.current_prompts)
            return True
        except Exception as exc:
            self.get_logger().error(
                f"YOLO-World Detector | Failed to load model '{self.model_name}': {exc}"
            )
            self.model = None
            return False

    def _publish_debug_image(self, frame, detection, source_msg: Image) -> None:
        if detection is not None:
            x1, y1, x2, y2 = [int(round(value)) for value in detection["bbox"]]
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            label = f"{detection['class']} {detection['confidence']:.2f}"
            cv2.putText(
                frame,
                label,
                (x1, max(20, y1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
                cv2.LINE_AA,
            )
        debug_msg = self.bridge.cv2_to_imgmsg(frame, encoding="bgr8")
        debug_msg.header = source_msg.header
        self.debug_image_pub.publish(debug_msg)


def main(args=None):
    rclpy.init(args=args)
    node = YoloWorldDetectorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
