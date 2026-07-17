import os

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
import cv2
from cv_bridge import CvBridge

class CameraDriver(Node):
    def __init__(self):
        super().__init__('camera_publisher_node')

        env_fps = os.environ.get('VIDEO_FPS', 30)

        self.declare_parameter('fps', env_fps)

        fps = self.get_parameter('fps').value

        self.publisher_ = self.create_publisher(Image, 'camera/image_raw', 10)
        self.cap = cv2.VideoCapture(0)
        self.bridge = CvBridge()

        timeout = 1.0 / fps
        self.timer = self.create_timer(timeout, self.timer_callback)

    def timer_callback(self):
        ret, frame = self.cap.read()
        if ret:
            msg = self.bridge.cv2_to_imgmsg(frame, encoding='bgr8')
            self.publisher_.publish(msg)


        
