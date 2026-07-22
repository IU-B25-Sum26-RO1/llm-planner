import asyncio
import os
import base64
import time
import threading
import json

import aiohttp
import rclpy
import numpy as np
from rclpy.node import Node
from std_msgs.msg import String
from sensor_msgs.msg import CompressedImage, Image
import cv2
from cv_bridge import CvBridge


class SAM3BridgeNode(Node):
    def __init__(self):
        super().__init__('sam3_bridge_node')
        
        self.image_sub_topic = 'camera/color/image_raw/processed'
        self.target_sub_topic = '/decomposer/json_output/target'
        self.raw_mask_pub_topic = '/sam3/output/mask_raw'

        self.declare_parameter('image_sub_topic', self.image_sub_topic)
        self.declare_parameter('target_sub_topic', self.target_sub_topic)
        self.declare_parameter('raw_mask_pub_topic', self.raw_mask_pub_topic)

        env_server_url = os.environ.get('SAM3_SERVER_URL')
        self.declare_parameter('server_url', env_server_url)
        self.server_url = self.get_parameter('server_url').value

        self.image_sub = self.create_subscription(
            CompressedImage,
            self.image_sub_topic,
            self.image_callback,
            1
        )

        self.target_sub = self.create_subscription(
            String,
            self.target_sub_topic,
            self.target_callback,
            10
        )

        self.raw_mask_pub = self.create_publisher(
            Image, self.raw_mask_pub_topic, 3
        )

        self.bridge = CvBridge()

        self.frame_queue = None
        self.target_queue = None
        self.loop = None

        self.latency_tracker = {}

        self.loop_thread = threading.Thread(target=self._run_async_loop, daemon=True)
        self.loop_thread.start()

        self.get_logger().info('SAM3 Bridge Node | HTTP-client has started. Waiting server output')

    def _run_async_loop(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self.websocket_orchestrator())
        except Exception as e:
            self.get_logger().critical(f"Async event loop crashed with: {str(e)}")
        finally:
            self.loop.close()
            self.get_logger().info("Async event loop closed.")

    def image_callback(self, msg: CompressedImage) -> None:
        if self.frame_queue is None:
            return
        
        if self.frame_queue.full():
            try:
                self.loop.call_soon_threadsafe(self.frame_queue.get_nowait)
            except asyncio.QueueEmpty:
                pass
        
        self.loop.call_soon_threadsafe(self.frame_queue.put_nowait, msg)
    
    def target_callback(self, msg: String):
        if self.target_queue is None:
            self.get_logger().warn("Target queue is not initialized yet. Dropping target")
            return
        
        try:
            target_data = json.loads(msg.data)

            payload = {
                "type": "update_prompts",
                "target": target_data
            }

            self.loop.call_soon_threadsafe(self.target_queue.put_nowait, payload)
            self.get_logger().info(f"[TARGET] New target queued from ROS topic.")

        except json.JSONDecodeError:
            self.get_logger().error(f"Received invalid JSON string in target_callback: {msg.data}")
        except Exception as e:
            self.get_logger().error(f"Error in target_callback: {e}")

    async def websocket_orchestrator(self):
        self.loop = asyncio.get_running_loop()

        self.frame_queue = asyncio.Queue(maxsize=1)
        self.target_queue = asyncio.Queue()

        timeout = aiohttp.ClientTimeout(total=None, connect=10.0)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            while rclpy.ok():
                try:
                    self.get_logger().info('Attempting WebSocket connection...')
                    async with session.ws_connect(self.server_url, max_msg_size=1024*1024*16) as ws:
                        self.get_logger().info('WebSocket connected successfully!')

                        send_task = asyncio.create_task(self.send_loop(ws))
                        receive_task = asyncio.create_task(self.receive_loop(ws))

                        done, pending = await asyncio.wait(
                            [send_task, receive_task],
                            return_when=asyncio.FIRST_EXCEPTION
                        )

                        for task in pending:
                            task.cancel()

                        for task in done:
                            if task.exception():
                                self.get_logger().error(f'Task finished with exception: {task.exception()}')

                except aiohttp.ClientError as e:
                    self.get_logger().error(f'Connection failed: {e}. Retrying in 3 seconds...')
                    await asyncio.sleep(3.0)
                except Exception as e:
                    self.get_logger().error(f'Unexpected error: {e}. Retrying in 3 seconds...')
                    await asyncio.sleep(3.0)
    
    async def send_loop(self, ws):
        self.get_logger().info('Send loop initialized and running.')

        frame_task = asyncio.create_task(self.frame_queue.get())
        target_task = asyncio.create_task(self.target_queue.get())

        try:
            while True:
                
                if ws.closed:
                    self.get_logger().warn('[SEND] Websocket is closed. Exiting send loop.')
                    break

                done, _ = await asyncio.wait(
                    [frame_task, target_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                try:
                    if target_task in done:
                        target_msg = target_task.result()

                        self.get_logger().info(f'[SEND] Sending target to server...')
                        if not ws.closed:
                            await ws.send_str(json.dumps(target_msg))
                            self.get_logger().info(f'[SEND] Target sent.')

                        target_task = asyncio.create_task(self.target_queue.get())

                    elif frame_task in done:
                        msg: CompressedImage = await self.frame_queue.get()

                        frame_id = f"{msg.header.stamp.sec}_{msg.header.stamp.nanosec}"
                        
                        if not ws.closed:
                            await ws.send_bytes(bytes(msg.data))
                            self.latency_tracker[frame_id] = self.get_clock().now()

                        if len(self.latency_tracker) > 50:
                            first_key = next(iter(self.latency_tracker))
                            self.latency_tracker.pop(first_key, None)

                        frame_task = asyncio.create_task(self.frame_queue.get())
                
                except (RuntimeError, ConnectionResetError, aiohttp.ClientConnectionError) as write_err:
                    self.get_logger().error(f'[SEND] Failed to write data (Socket closing/broken): {write_err}')

        except Exception as e:
            self.get_logger().warn(f'Send loop stopped due to CRITICAL ERROR: {str(e)}')
        finally:
            frame_task.cancel()
            target_task.cancel()


    async def receive_loop(self, ws):
        self.get_logger().info('Receive loop initialized and running.')
        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:

                    self.get_logger().info(f'[RECEIVE] JSON string received: {msg.data[:200]}...')

                    data = json.loads(msg.data)

                    if isinstance(data, dict) and data.get("status") == "error":
                        self.get_logger().error(f"Server returned error: {data.get('error')}")
                        continue
                    
                    for item in data:
                        if item.get("status") == "success":
                            obj_id = item.get("obj_id")
                            b64_mask = item.get("mask")
                            
                            if not b64_mask:
                                continue

                            mask_bytes = base64.b64decode(b64_mask)
                            np_arr = np.frombuffer(mask_bytes, np.uint8)
                            mask_frame = cv2.imdecode(np_arr, cv2.IMREAD_GRAYSCALE)

                            if mask_frame is not None:
                                ros_mask_msg = self.bridge.cv2_to_imgmsg(mask_frame, encoding='mono8')
                                
                                self.raw_mask_pub.publish(ros_mask_msg)

                                self.get_logger().info(f'Mask published for target: {obj_id}')
                            else:
                                self.get_logger().error('Failed to decode image from Base64 string')
                
                elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSING, aiohttp.WSMsgType.CLOSED):
                    break
        except Exception as e:
            self.get_logger().warn(f'Receive loop stopped: {e}')


def main(args=None):
    rclpy.init(args=args)
    node = SAM3BridgeNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()