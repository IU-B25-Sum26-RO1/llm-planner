import json
import os
import re
import sys
import time
from pathlib import Path

import cv2
import rclpy
from cv_bridge import CvBridge
from rclpy.node import Node
from sensor_msgs.msg import Image

from scene_analyzer.detection_utils import detections_from_yolo_result, select_best_detection


class ImageCapture(Node):
    def __init__(self, image_topic: str):
        super().__init__("yolo_world_probe")
        self.bridge = CvBridge()
        self.frame = None
        self.header = None
        self.create_subscription(Image, image_topic, self.image_callback, 1)

    def image_callback(self, msg: Image) -> None:
        if self.frame is not None:
            return
        self.frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        self.header = msg.header


def main(args=None):
    if args is None:
        args = sys.argv[1:]

    queries = [arg.strip() for arg in args if arg.strip() and not arg.startswith("__")]
    if not queries:
        queries = ["green cube", "blue cube", "red cube", "ball"]

    image_topic = os.environ.get("PERCEPTION_IMAGE_TOPIC", "/camera/camera/image_raw")
    model_name = os.environ.get("YOLO_WORLD_MODEL", "yolov8s-worldv2.pt")
    device = os.environ.get("PERCEPTION_DEVICE", "cpu")
    conf = float(os.environ.get("YOLO_CONF", "0.1"))
    timeout = float(os.environ.get("PERCEPTION_PROBE_TIMEOUT", "15.0"))
    output_dir = Path(os.environ.get("PERCEPTION_PROBE_OUTPUT_DIR", "/workspace/models/perception_probe"))
    output_dir.mkdir(parents=True, exist_ok=True)

    rclpy.init(args=None)
    node = ImageCapture(image_topic)
    deadline = time.monotonic() + timeout
    try:
        while node.frame is None and time.monotonic() < deadline and rclpy.ok():
            rclpy.spin_once(node, timeout_sec=0.2)

        if node.frame is None:
            node.get_logger().error(f"FAIL no image received from {image_topic}")
            return 1

        raw_path = output_dir / "scene_raw.png"
        cv2.imwrite(str(raw_path), node.frame)

        from ultralytics import YOLOWorld

        model = YOLOWorld(model_name)
        summary = {
            "image_topic": image_topic,
            "model": model_name,
            "device": device,
            "confidence_threshold": conf,
            "raw_image": str(raw_path),
            "queries": [],
        }

        for query in queries:
            model.set_classes([query])
            result = model.predict(
                node.frame,
                conf=conf,
                device=device,
                verbose=False,
            )[0]
            detections = detections_from_yolo_result(result)
            best = select_best_detection(detections, conf)
            annotated = _draw_detections(node.frame.copy(), detections, conf)
            slug = _slugify(query)
            image_path = output_dir / f"{slug}.png"
            json_path = output_dir / f"{slug}.json"
            cv2.imwrite(str(image_path), annotated)

            query_result = {
                "query": query,
                "detections": detections,
                "best": best,
                "debug_image": str(image_path),
            }
            json_path.write_text(
                json.dumps(query_result, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            summary["queries"].append(query_result)

            if best is None:
                node.get_logger().warn(f"YOLO probe | '{query}': no detections >= {conf}")
            else:
                node.get_logger().info(
                    "YOLO probe | '%s': best %s %.3f bbox=%s image=%s"
                    % (
                        query,
                        best.get("class"),
                        float(best.get("confidence", 0.0)),
                        [round(float(value), 1) for value in best.get("bbox", [])],
                        image_path,
                    )
                )

        summary_path = output_dir / "summary.json"
        summary_path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        node.get_logger().info(f"PASS probe outputs saved to {output_dir}")
        return 0
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


def _draw_detections(frame, detections: list[dict], conf: float):
    for detection in detections:
        if float(detection.get("confidence", 0.0)) < conf:
            continue
        x1, y1, x2, y2 = [int(round(value)) for value in detection["bbox"]]
        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = "%s %.2f" % (
            detection.get("class", "object"),
            float(detection.get("confidence", 0.0)),
        )
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
    return frame


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-zA-Zа-яА-Я0-9]+", "_", value.strip().lower()).strip("_")
    return slug or "query"


if __name__ == "__main__":
    raise SystemExit(main())
