import os

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import CompressedImage
import cv2
from cv_bridge import CvBridge

class PreprocessorNode(Node):
    def __init__(self):
        super().__init__('preprocessor_node')
        
        env_sub_topic = os.environ.get('CAMERA_RAW_TOPIC')
        env_target_fps = os.environ.get('TARGET_VIDEO_FPS')
        env_target_width = os.environ.get('TARGET_VIDEO_WIDTH')
        env_target_height = os.environ.get('TARGET_VIDEO_HEIGHT')

        pub_topic = 'camera/color/image_raw/processed'
        
        self.declare_parameter('sub_topic', env_sub_topic)
        self.declare_parameter('target_fps', env_target_fps)
        self.declare_parameter('target_width', env_target_width)
        self.declare_parameter('target_height', env_target_height)
        self.declare_parameter('pub_topic', pub_topic)

        sub_topic = self.get_parameter('sub_topic').value
        target_fps = self.get_parameter('target_fps').value
        target_width = self.get_parameter('target_width').value
        target_height = self.get_parameter('target_height').value

        self.sub = self.create_subscription(CompressedImage, sub_topic, self.callback, 10)
        self.pub = self.create_publisher(CompressedImage, pub_topic, 10)

        self.get_logger().info(f"PreprocessorNode | Node has started and is listening to {sub_topic}.")

    def callback(self, msg: CompressedImage) -> None:
        try:
            # self.get_logger().info('Image received.')
            self.pub.publish(msg)
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
