"""Regression checks for the camera-to-SAM3 hand-off without ROS installed."""

import asyncio
import importlib
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
for package in ('camera_driver', 'sam3_preprocessor', 'sam3_bridge'):
    sys.path.insert(0, str(ROOT / 'src' / package))


def _install_ros_stubs(monkeypatch):
    class FakeNode:
        def __init__(self, *args):
            self.parameters = {}

        def declare_parameter(self, name, value):
            self.parameters[name] = value

        def get_parameter(self, name):
            return types.SimpleNamespace(value=self.parameters[name])

        def create_publisher(self, message_type, topic, depth):
            return types.SimpleNamespace(topic=topic)

        def create_subscription(self, *args):
            return types.SimpleNamespace()

        def create_timer(self, *args):
            return types.SimpleNamespace()

        def get_logger(self):
            return types.SimpleNamespace(info=lambda *args: None, error=lambda *args: None)

    rclpy = types.ModuleType('rclpy')
    rclpy.ok = lambda: True
    rclpy.node = types.ModuleType('rclpy.node')
    rclpy.node.Node = FakeNode
    sensor_msgs = types.ModuleType('sensor_msgs')
    sensor_msgs.msg = types.ModuleType('sensor_msgs.msg')
    sensor_msgs.msg.Image = type('Image', (), {})
    sensor_msgs.msg.CompressedImage = type('CompressedImage', (), {})
    std_msgs = types.ModuleType('std_msgs')
    std_msgs.msg = types.ModuleType('std_msgs.msg')
    std_msgs.msg.String = type('String', (), {})
    cv_bridge = types.ModuleType('cv_bridge')
    cv_bridge.CvBridge = type('CvBridge', (), {})
    cv2 = types.ModuleType('cv2')
    monkeypatch.setitem(sys.modules, 'rclpy', rclpy)
    monkeypatch.setitem(sys.modules, 'rclpy.node', rclpy.node)
    monkeypatch.setitem(sys.modules, 'sensor_msgs', sensor_msgs)
    monkeypatch.setitem(sys.modules, 'sensor_msgs.msg', sensor_msgs.msg)
    monkeypatch.setitem(sys.modules, 'std_msgs', std_msgs)
    monkeypatch.setitem(sys.modules, 'std_msgs.msg', std_msgs.msg)
    monkeypatch.setitem(sys.modules, 'cv_bridge', cv_bridge)
    monkeypatch.setitem(sys.modules, 'cv2', cv2)


def test_camera_and_preprocessor_use_the_same_default_topic(monkeypatch):
    _install_ros_stubs(monkeypatch)
    monkeypatch.delenv('CAMERA_RAW_TOPIC', raising=False)
    driver = importlib.import_module('camera_driver.camera_publisher_node')
    preprocessor = importlib.import_module('sam3_preprocessor.preprocessor_node')

    assert driver.DEFAULT_CAMERA_RAW_TOPIC == '/camera/color/image_raw'
    assert preprocessor.DEFAULT_CAMERA_RAW_TOPIC == driver.DEFAULT_CAMERA_RAW_TOPIC
    assert callable(driver.main)

    node = preprocessor.PreprocessorNode()
    assert isinstance(node.bridge, sys.modules['cv_bridge'].CvBridge)
    assert node.sub is not None


def test_bridge_replaces_stale_frame_without_queue_overflow(monkeypatch):
    _install_ros_stubs(monkeypatch)
    bridge = importlib.import_module('sam3_bridge.sam3_bridge_node')
    node = object.__new__(bridge.SAM3BridgeNode)
    node.frame_queue = asyncio.Queue(maxsize=1)
    node.frame_queue.put_nowait('old')

    node._enqueue_latest_frame('new')

    assert node.frame_queue.get_nowait() == 'new'


def test_send_loop_sends_the_frame_that_completed_the_get(monkeypatch):
    _install_ros_stubs(monkeypatch)
    bridge = importlib.import_module('sam3_bridge.sam3_bridge_node')

    class WebSocket:
        def __init__(self):
            self.closed = False
            self.sent = []

        async def send_bytes(self, payload):
            self.sent.append(payload)
            self.closed = True

    class Logger:
        info = warning = warn = error = lambda self, *args: None

    class Clock:
        def now(self):
            return object()

    async def run():
        node = object.__new__(bridge.SAM3BridgeNode)
        node.frame_queue = asyncio.Queue()
        node.target_queue = asyncio.Queue()
        node.latency_tracker = {}
        node.get_logger = lambda: Logger()
        node.get_clock = lambda: Clock()
        message = types.SimpleNamespace(
            data=b'first-frame',
            header=types.SimpleNamespace(stamp=types.SimpleNamespace(sec=1, nanosec=2)),
        )
        await node.frame_queue.put(message)
        ws = WebSocket()
        await node.send_loop(ws)
        return ws.sent

    assert asyncio.run(run()) == [b'first-frame']
