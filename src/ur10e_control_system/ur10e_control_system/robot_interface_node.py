"""UR10e robot interface node.

Exposes a small set of *basic policies* for the anchored UR10e in Gazebo and
wires them to the ``/execute/base_action`` action and ``/execute/gripper_control``
service defined in ``robot_interfaces``.

Supported ``task_type`` values (see :meth:`UR10eInterface.execute_callback`):

* ``move_to``        - move the tool to a world (x, y, z) point, gripper down.
* ``move_to_object`` - look up ``object_name`` pose in Gazebo, hover above it.
* ``pick``           - hover -> descend -> close gripper -> lift.
* ``place``          - hover over target -> descend -> open gripper -> lift.
* ``home``           - go to the predefined ready posture.
* ``forward`` / ``backward`` / ``left`` / ``right`` / ``up`` / ``down`` -
  Cartesian jog of the tool by a fixed step (world frame). Optional custom
  distance can be passed through the ``x`` field of the goal.
* ``grasp`` / ``release`` - close / open the gripper.

Directions are expressed in the Gazebo *world* frame:
``forward`` = +X, ``backward`` = -X, ``left`` = +Y, ``right`` = -Y,
``up`` = +Z, ``down`` = -Z.
"""

import math
import threading
import time

import numpy as np
import rclpy  # type: ignore
from rclpy.action import ActionServer, CancelResponse, GoalResponse  # type: ignore
from rclpy.callback_groups import ReentrantCallbackGroup  # type: ignore
from rclpy.executors import MultiThreadedExecutor  # type: ignore
from rclpy.node import Node  # type: ignore
from rclpy.qos import QoSDurabilityPolicy, QoSProfile, QoSReliabilityPolicy  # type: ignore

from gazebo_msgs.msg import EntityState, ModelStates  # type: ignore
from gazebo_msgs.srv import SetEntityState  # type: ignore
from sensor_msgs.msg import JointState  # type: ignore
from std_msgs.msg import Float64MultiArray, String  # type: ignore
from trajectory_msgs.msg import JointTrajectory, JointTrajectoryPoint  # type: ignore

from robot_interfaces.action import BaseAction  # type: ignore
from robot_interfaces.srv import GripperControl  # type: ignore

from ur10e_control_system.ur_kinematics import URKinematics, make_transform


# Order expected by joint_trajectory_controller (see ur10e_scene/config/controllers.yaml).
ARM_JOINTS = [
    "shoulder_pan_joint",
    "shoulder_lift_joint",
    "elbow_joint",
    "wrist_1_joint",
    "wrist_2_joint",
    "wrist_3_joint",
]

# Ready posture: elbow up, tool pointing down over the table. Used as a safe
# starting configuration and as an IK seed.
HOME_POSITION = {
    "shoulder_pan_joint": 0.0,
    "shoulder_lift_joint": -1.2,
    "elbow_joint": 1.6,
    "wrist_1_joint": -1.95,
    "wrist_2_joint": -1.57,
    "wrist_3_joint": 0.0,
}

# Tool pointing straight down (tool0 Z axis -> world -Z), used for top-down grasps.
DOWN_ORIENTATION = np.array([
    [1.0, 0.0, 0.0],
    [0.0, -1.0, 0.0],
    [0.0, 0.0, -1.0],
])

DIRECTION_VECTORS = {
    "forward": np.array([1.0, 0.0, 0.0]),
    "backward": np.array([-1.0, 0.0, 0.0]),
    "left": np.array([0.0, 1.0, 0.0]),
    "right": np.array([0.0, -1.0, 0.0]),
    "up": np.array([0.0, 0.0, 1.0]),
    "down": np.array([0.0, 0.0, -1.0]),
}


class UR10eInterface(Node):
    def __init__(self):
        super().__init__("ur10e_interface")

        # ---- Tunable parameters ---------------------------------------------
        self.declare_parameter("hover_height", 0.25)      # tool height above object top
        self.declare_parameter("grasp_height", 0.135)     # tool height for closing on object (grip face centers)
        self.declare_parameter("place_height", 0.24)      # tool height when releasing into a tray
        self.declare_parameter("jog_step", 0.05)          # default Cartesian jog (m)
        # Gripper jaw positions. Two-finger grasping of a rigid body is unstable
        # in Gazebo Classic (ODE), so the jaws only provide the visual grasp while
        # the object is actually held by a kinematic attach (see _attach).
        self.declare_parameter("gripper_open", 0.0)       # jaw position, open
        self.declare_parameter("gripper_closed", 0.045)   # jaw position, closed onto object
        self.declare_parameter("gripper_hold", 0.04)      # jaw position while carrying (just off the object)
        self.declare_parameter("move_speed", 0.6)         # rad/s used to time trajectories
        self.declare_parameter("tip_link", "tool0")

        self.hover_height = self.get_parameter("hover_height").value
        self.grasp_height = self.get_parameter("grasp_height").value
        self.place_height = self.get_parameter("place_height").value
        self.jog_step = self.get_parameter("jog_step").value
        self.gripper_open = self.get_parameter("gripper_open").value
        self.gripper_closed = self.get_parameter("gripper_closed").value
        self.gripper_hold = self.get_parameter("gripper_hold").value
        self.move_speed = self.get_parameter("move_speed").value
        self.tip_link = self.get_parameter("tip_link").value

        # ---- State ----------------------------------------------------------
        self._lock = threading.Lock()
        self._joint_positions = {}
        self._model_poses = {}
        self.kin = None

        cb_group = ReentrantCallbackGroup()

        # ---- Subscriptions --------------------------------------------------
        self.create_subscription(
            JointState, "/joint_states", self._joint_state_cb, 10, callback_group=cb_group
        )
        self.create_subscription(
            ModelStates, "/gazebo/model_states", self._model_states_cb, 10,
            callback_group=cb_group,
        )
        # robot_description is published as a latched (transient local) topic.
        latched_qos = QoSProfile(
            depth=1,
            reliability=QoSReliabilityPolicy.RELIABLE,
            durability=QoSDurabilityPolicy.TRANSIENT_LOCAL,
        )
        self.create_subscription(
            String, "/robot_description", self._robot_description_cb, latched_qos,
            callback_group=cb_group,
        )

        # ---- Publishers -----------------------------------------------------
        self._traj_pub = self.create_publisher(
            JointTrajectory, "/joint_trajectory_controller/joint_trajectory", 10
        )
        self._gripper_pub = self.create_publisher(
            Float64MultiArray, "/gripper_controller/commands", 10
        )
        # Continuously re-publish the current jaw command so the controller keeps
        # holding it throughout the whole carry motion (robust to latching).
        self._gripper_cmd = [self.gripper_open, self.gripper_open]
        self.create_timer(0.1, self._republish_gripper, callback_group=cb_group)

        # Kinematic grasp: while an object is "held", keep teleporting it to
        # follow the tool frame (robust against ODE grasp instability).
        self._set_state_cli = self.create_client(
            SetEntityState, "/gazebo/set_entity_state", callback_group=cb_group
        )
        self._held = None
        self._held_offset = np.zeros(3)
        self._set_future = None
        self.create_timer(0.01, self._follow_held, callback_group=cb_group)

        # ---- Action server & service ---------------------------------------
        self._action_server = ActionServer(
            self,
            BaseAction,
            "/execute/base_action",
            execute_callback=self.execute_callback,
            goal_callback=self.goal_callback,
            cancel_callback=self.cancel_callback,
            callback_group=cb_group,
        )
        self.gripper_srv = self.create_service(
            GripperControl, "/execute/gripper_control", self.gripper_callback,
            callback_group=cb_group,
        )

        self.get_logger().info("UR10e Interface | Robot Interface has launched")

    # ------------------------------------------------------------------ #
    # Subscription callbacks
    # ------------------------------------------------------------------ #
    def _joint_state_cb(self, msg: JointState):
        with self._lock:
            for name, position in zip(msg.name, msg.position):
                self._joint_positions[name] = position

    def _model_states_cb(self, msg: ModelStates):
        with self._lock:
            self._model_poses = {
                name: pose for name, pose in zip(msg.name, msg.pose)
            }

    def _robot_description_cb(self, msg: String):
        if self.kin is not None:
            return
        try:
            self.kin = URKinematics(msg.data, root_link="world", tip_link=self.tip_link)
            self.get_logger().info(
                f"UR10e Interface | Kinematics ready ({self.kin.num_joints} DOF): "
                f"{self.kin.movable_names}"
            )
        except Exception as exc:  # pragma: no cover - defensive
            self.get_logger().error(f"UR10e Interface | Failed to parse URDF: {exc}")

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _current_arm_q(self):
        with self._lock:
            missing = [j for j in self.kin.movable_names if j not in self._joint_positions]
            if missing:
                return None
            return np.array(
                [self._joint_positions[j] for j in self.kin.movable_names], dtype=float
            )

    def _get_object_position(self, name, timeout=5.0):
        """Return the world position of a Gazebo model, waiting briefly for it."""
        deadline = time.time() + timeout
        while True:
            with self._lock:
                pose = self._model_poses.get(name)
            if pose is not None:
                return np.array([pose.position.x, pose.position.y, pose.position.z])
            if time.time() >= deadline:
                return None
            time.sleep(0.1)

    def _wait_for_prerequisites(self, timeout=10.0):
        """Block until kinematics, joint states and model states are available."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.kin is not None and self._current_arm_q() is not None:
                return True
            time.sleep(0.1)
        return False

    def _solve_ik(self, target_transform, position_only=False):
        """Try several seeds and return the best joint solution or None."""
        current = self._current_arm_q()
        seeds = []
        if current is not None:
            seeds.append(current)
        seeds.append(np.array([HOME_POSITION[j] for j in self.kin.movable_names]))
        # A couple of perturbed seeds to escape poor local minima.
        rng = np.random.default_rng(0)
        base_seed = seeds[0]
        for _ in range(4):
            seeds.append(base_seed + rng.uniform(-0.6, 0.6, size=self.kin.num_joints))

        best_q = None
        best_cost = float("inf")
        for seed in seeds:
            q, ok = self.kin.ik(target_transform, seed, position_only=position_only)
            if not ok:
                continue
            cost = float(np.linalg.norm(q - (current if current is not None else q)))
            if cost < best_cost:
                best_cost = cost
                best_q = q
        return best_q

    def _send_arm_trajectory(self, target_q, min_time=2.0):
        """Publish a single-point trajectory and block until it should finish."""
        current = self._current_arm_q()
        q_map = dict(zip(self.kin.movable_names, target_q))
        positions = [q_map[j] for j in ARM_JOINTS]

        if current is not None:
            cur_map = dict(zip(self.kin.movable_names, current))
            max_delta = max(abs(q_map[j] - cur_map[j]) for j in ARM_JOINTS)
        else:
            max_delta = math.pi
        duration = max(min_time, max_delta / max(self.move_speed, 1e-3))

        traj = JointTrajectory()
        traj.joint_names = ARM_JOINTS
        point = JointTrajectoryPoint()
        point.positions = [float(p) for p in positions]
        point.time_from_start.sec = int(duration)
        point.time_from_start.nanosec = int((duration - int(duration)) * 1e9)
        traj.points = [point]

        self._traj_pub.publish(traj)
        time.sleep(duration + 0.5)

    def _republish_gripper(self):
        msg = Float64MultiArray()
        msg.data = [float(v) for v in self._gripper_cmd]
        self._gripper_pub.publish(msg)

    def _attach(self, name):
        """Kinematically attach a Gazebo model to the tool frame."""
        obj = self._get_object_position(name)
        tool = self._tool_pose()
        if obj is None or tool is None:
            self.get_logger().warn(
                f"UR10e Interface | Attach failed: '{name}' or tool pose unavailable"
            )
            return False
        # Record the object position relative to the tool frame at grasp time.
        self._held_offset = tool[:3, :3].T @ (obj - tool[:3, 3])
        self._held = name
        # Back the jaws slightly off the object so contact does not fight the
        # kinematic hold (removes residual jitter while carrying).
        self._gripper_cmd = [self.gripper_hold, self.gripper_hold]
        self._republish_gripper()
        self.get_logger().info(f"UR10e Interface | Attached '{name}' to gripper")
        return True

    def _attach_nearest(self, max_dist=0.15):
        tool = self._tool_pose()
        if tool is None:
            return False
        p = tool[:3, 3]
        with self._lock:
            items = [(n, po) for n, po in self._model_poses.items()]
        best, best_d = None, max_dist
        for name, pose in items:
            if name in ("ground_plane", "table", "white_tray", "ur10e"):
                continue
            d = np.linalg.norm(
                [pose.position.x - p[0], pose.position.y - p[1], pose.position.z - p[2]]
            )
            if d < best_d:
                best, best_d = name, d
        if best is not None:
            return self._attach(best)
        self.get_logger().warn("UR10e Interface | No object near the gripper to grasp")
        return False

    def _detach(self):
        if self._held is not None:
            self.get_logger().info(f"UR10e Interface | Detached '{self._held}'")
        self._held = None

    def _follow_held(self):
        if self._held is None or self.kin is None:
            return
        tool = self._tool_pose()
        if tool is None or not self._set_state_cli.service_is_ready():
            return
        # Skip if the previous call has not completed yet (avoid piling up).
        if self._set_future is not None and not self._set_future.done():
            return
        world_pos = tool[:3, 3] + tool[:3, :3] @ self._held_offset
        state = EntityState()
        state.name = self._held
        state.pose.position.x = float(world_pos[0])
        state.pose.position.y = float(world_pos[1])
        state.pose.position.z = float(world_pos[2])
        state.pose.orientation.w = 1.0  # keep the object upright
        state.reference_frame = "world"
        request = SetEntityState.Request()
        request.state = state
        self._set_future = self._set_state_cli.call_async(request)

    def _command_gripper(self, closed: bool):
        # Ramp the position command slowly so the jaws squeeze gently instead of
        # snapping shut (a hard step command ejects the cube). Both jaws move
        # toward the center (order matches gripper_controller joints: left, right).
        target = self.gripper_closed if closed else self.gripper_open
        with self._lock:
            start = self._joint_positions.get("left_jaw_joint", self._gripper_cmd[0])

        steps = 30
        duration = 1.5
        for i in range(1, steps + 1):
            value = start + (target - start) * (i / steps)
            self._gripper_cmd = [value, value]
            self._republish_gripper()
            time.sleep(duration / steps)
        self._gripper_cmd = [target, target]
        self._republish_gripper()

        self.get_logger().info(
            f"UR10e Interface | Gripper {'closed' if closed else 'opened'} "
            f"(pos={target:.3f})"
        )

    def _tool_pose(self):
        """Current tool transform (world) from FK, or None."""
        q = self._current_arm_q()
        if q is None:
            return None
        transform, _, _ = self.kin.fk(q)
        return transform

    def _move_tool_to(self, position, orientation=None, position_only=False, min_time=2.0):
        """IK to a world pose and execute. Returns (ok, message)."""
        if orientation is None:
            orientation = DOWN_ORIENTATION
        target = make_transform(orientation, np.asarray(position, dtype=float))
        target_q = self._solve_ik(target, position_only=position_only)
        if target_q is None:
            return False, f"IK failed for target {np.round(position, 3).tolist()}"
        self._send_arm_trajectory(target_q, min_time=min_time)
        return True, ""

    # ------------------------------------------------------------------ #
    # Policies
    # ------------------------------------------------------------------ #
    def _go_home(self):
        target_q = np.array([HOME_POSITION[j] for j in self.kin.movable_names])
        self._send_arm_trajectory(target_q, min_time=3.0)
        return True, ""

    def _move_to(self, position):
        return self._move_tool_to(position)

    def _move_to_object(self, name):
        obj = self._get_object_position(name)
        if obj is None:
            return False, f"Object '{name}' not found in Gazebo model states"
        target = np.array([obj[0], obj[1], obj[2] + self.hover_height])
        self.get_logger().info(
            f"UR10e Interface | '{name}' at {np.round(obj, 3).tolist()}, "
            f"hovering at {np.round(target, 3).tolist()}"
        )
        # Start from the ready posture for a predictable, well-conditioned motion.
        self._go_home()
        return self._move_tool_to(target)

    def _pick(self, name):
        obj = self._get_object_position(name)
        if obj is None:
            return False, f"Object '{name}' not found in Gazebo model states"
        hover = np.array([obj[0], obj[1], obj[2] + self.hover_height])
        grasp = np.array([obj[0], obj[1], obj[2] + self.grasp_height])
        self._command_gripper(closed=False)
        # self._go_home()
        ok, msg = self._move_tool_to(hover)
        if not ok:
            return ok, msg
        ok, msg = self._move_tool_to(grasp, min_time=2.0)
        if not ok:
            return ok, msg
        self._command_gripper(closed=True)
        self._attach(name)
        return self._move_tool_to(hover, min_time=2.0)

    def _place(self, name, position):
        if position is not None:
            base = np.asarray(position, dtype=float)
        else:
            obj = self._get_object_position(name)
            if obj is None:
                return False, f"Place target '{name}' not found in Gazebo model states"
            base = obj
        hover = np.array([base[0], base[1], base[2] + self.hover_height])
        # Release above the tray opening so the gripper does not push into it.
        release = np.array([base[0], base[1], base[2] + self.place_height])
        ok, msg = self._move_tool_to(hover)
        if not ok:
            return ok, msg
        ok, msg = self._move_tool_to(release, min_time=2.0)
        if not ok:
            return ok, msg
        # Release the held object at the current pose, then open the jaws.
        self._detach()
        self._command_gripper(closed=False)
        return self._move_tool_to(hover, min_time=2.0)

    def _jog(self, direction, distance):
        pose = self._tool_pose()
        if pose is None:
            return False, "Current tool pose unavailable"
        step = distance if distance and distance > 0.0 else self.jog_step
        target_pos = pose[:3, 3] + DIRECTION_VECTORS[direction] * step
        # Keep the current orientation while jogging in a straight line.
        return self._move_tool_to(target_pos, orientation=pose[:3, :3], min_time=1.5)

    # ------------------------------------------------------------------ #
    # Action / service plumbing
    # ------------------------------------------------------------------ #
    def goal_callback(self, goal_request):
        return GoalResponse.ACCEPT

    def cancel_callback(self, cancel_request):
        self.get_logger().warn("UR10e Interface | Got emergency cancel command.")
        return CancelResponse.ACCEPT

    def _publish_feedback(self, goal_handle, state):
        feedback = BaseAction.Feedback()
        feedback.current_state = state
        goal_handle.publish_feedback(feedback)

    def execute_callback(self, goal_handle):
        request = goal_handle.request
        task = request.task_type
        result = BaseAction.Result()

        self.get_logger().info(
            f"UR10e Interface | Executing '{task}' object='{request.object_name}' "
            f"xyz=({request.x:.3f}, {request.y:.3f}, {request.z:.3f})"
        )

        if not self._wait_for_prerequisites():
            goal_handle.abort()
            result.success = False
            result.error_message = "Kinematics or joint states not available yet"
            return result

        self._publish_feedback(goal_handle, f"running:{task}")

        try:
            if task == "go_home":
                ok, msg = self._go_home()
            elif task == "move_to":
                ok, msg = self._move_to([request.x, request.y, request.z])
            elif task == "move_to_object":
                ok, msg = self._move_to_object(request.object_name)
            elif task == "pick":
                ok, msg = self._pick(request.object_name)
            elif task == "place":
                position = None
                if request.x or request.y or request.z:
                    position = [request.x, request.y, request.z]
                ok, msg = self._place(request.object_name, position)
            elif task in DIRECTION_VECTORS:
                ok, msg = self._jog(task, request.x)
            # elif task == "close_gripper":  # Not using now 
            #     self._command_gripper(closed=True)
            #     self._attach_nearest()
            #     ok, msg = True, ""
            # elif task == "open_gripper":
            #     self._detach()
            #     self._command_gripper(closed=False)
            #     ok, msg = True, ""
            else:
                ok, msg = False, f"Unexpected task: {task}"
                self.get_logger().warn(f"UR10e Interface | {msg}")
        except Exception as exc:  # pragma: no cover - defensive
            ok, msg = False, f"Exception during '{task}': {exc}"
            self.get_logger().error(f"UR10e Interface | {msg}")

        if goal_handle.is_cancel_requested:
            goal_handle.canceled()
            result.success = False
            result.error_message = "Canceled"
            self.get_logger().info("UR10e Interface | Robot stopped (canceled).")
            return result

        if ok:
            goal_handle.succeed()
            result.success = True
            result.error_message = ""
            self._publish_feedback(goal_handle, f"done:{task}")
            self.get_logger().info(f"UR10e Interface | Task '{task}' finished.")
        else:
            goal_handle.abort()
            result.success = False
            result.error_message = msg
            self.get_logger().error(f"UR10e Interface | Task '{task}' failed: {msg}")
        return result

    def gripper_callback(self, request, response):
        try:
            if request.activate:
                self._attach_nearest(max_dist=0.03)
            else:
                self._detach()
            self._command_gripper(closed=bool(request.activate))
        except Exception as exc:  # pragma: no cover - defensive
            self.get_logger().error(f"UR10e Interface | Unexpected gripper error: {exc}")
            response.success = False
            return response
        response.success = True
        return response


def main(args=None):
    rclpy.init(args=args)
    node = UR10eInterface()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
