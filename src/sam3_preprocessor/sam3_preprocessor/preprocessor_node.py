import os
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage, Image
import cv2
from cv_bridge import CvBridge

class PreprocessorNode(Node):
    def __init__(self):
        super().__init__('preprocessor_node')
        
        env_sub_topic = os.environ.get('CAMERA_RAW_TOPIC')
        env_target_fps = int(os.environ.get('TARGET_VIDEO_FPS', 10))
        env_target_width = int(os.environ.get('TARGET_VIDEO_WIDTH', 640))
        env_target_height = int(os.environ.get('TARGET_VIDEO_HEIGHT', 480))

        pub_topic = 'camera/color/image_raw/processed'
        
        self.declare_parameter('sub_topic', env_sub_topic)
        self.declare_parameter('target_fps', env_target_fps)
        self.declare_parameter('target_width', env_target_width)
        self.declare_parameter('target_height', env_target_height)
        self.declare_parameter('pub_topic', pub_topic)

        sub_topic = self.get_parameter('sub_topic').value
        self.target_fps = int(self.get_parameter('target_fps').value)
        self.target_width = int(self.get_parameter('target_width').value)
        self.target_height = int(self.get_parameter('target_height').value)
        if self.target_fps <= 0 or self.target_width <= 0 or self.target_height <= 0:
            raise ValueError('target_fps, target_width, and target_height must be positive')
        self.frame_interval = 1.0 / self.target_fps
        self.last_publish_time = 0.0

        self.sub = self.create_subscription(Image, sub_topic, self.callback, 10)
        self.pub = self.create_publisher(CompressedImage, pub_topic, 10)

        self.get_logger().info(
            f"PreprocessorNode | Listening to {sub_topic}; publishing {self.target_width}x"
            f"{self.target_height} JPEG frames at up to {self.target_fps} FPS."
        )

    def callback(self, msg: Image) -> None:
        try:
            now = time.monotonic()
            if now - self.last_publish_time < self.frame_interval:
                return

            frame = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            resized = cv2.resize(
                frame,
                (self.target_width, self.target_height),
                interpolation=cv2.INTER_AREA,
            )
            encoded, buffer = cv2.imencode('.jpg', resized)
            if not encoded:
                self.get_logger().error('PreprocessorNode | Failed to JPEG-encode frame.')
                return

            output = CompressedImage()
            output.header = msg.header
            output.format = 'jpeg'
            output.data = buffer.tobytes()
            self.pub.publish(output)
            self.last_publish_time = now
        except Exception as e:
            self.get_logger().error(f'PreprocessorNode | Error while publishing image: {str(e)}')
    

def main(args=None):
    rclpy.init(args=args)
    node = PreprocessorNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
