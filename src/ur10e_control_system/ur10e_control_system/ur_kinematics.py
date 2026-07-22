import math

import numpy as np

try:
    from urdf_parser_py.urdf import URDF  # type: ignore
except ImportError:  # pragma: no cover
    from urdf_parser_py.urdf import Robot as URDF  # type: ignore


def rpy_to_matrix(rpy):
    r, p, y = rpy
    cr, sr = math.cos(r), math.sin(r)
    cp, sp = math.cos(p), math.sin(p)
    cy, sy = math.cos(y), math.sin(y)
    rz = np.array([[cy, -sy, 0.0], [sy, cy, 0.0], [0.0, 0.0, 1.0]])
    ry = np.array([[cp, 0.0, sp], [0.0, 1.0, 0.0], [-sp, 0.0, cp]])
    rx = np.array([[1.0, 0.0, 0.0], [0.0, cr, -sr], [0.0, sr, cr]])
    return rz @ ry @ rx


def axis_angle_matrix(axis, angle):
    axis = np.asarray(axis, dtype=float)
    norm = np.linalg.norm(axis)
    if norm < 1e-12:
        return np.eye(3)
    x, y, z = axis / norm
    c, s = math.cos(angle), math.sin(angle)
    t = 1.0 - c
    return np.array([
        [c + x * x * t, x * y * t - z * s, x * z * t + y * s],
        [y * x * t + z * s, c + y * y * t, y * z * t - x * s],
        [z * x * t - y * s, z * y * t + x * s, c + z * z * t],
    ])


def make_transform(rotation, translation):
    transform = np.eye(4)
    transform[:3, :3] = rotation
    transform[:3, 3] = translation
    return transform


def rotation_to_vector(rotation):
    cos_angle = (np.trace(rotation) - 1.0) / 2.0
    cos_angle = max(-1.0, min(1.0, cos_angle))
    angle = math.acos(cos_angle)
    if angle < 1e-9:
        return np.zeros(3)
    if abs(angle - math.pi) < 1e-6:
        diag = (np.diag(rotation) + 1.0) / 2.0
        diag = np.clip(diag, 0.0, None)
        axis = np.sqrt(diag)
        if rotation[0, 1] + rotation[1, 0] < 0:
            axis[1] = -axis[1]
        if rotation[0, 2] + rotation[2, 0] < 0:
            axis[2] = -axis[2]
        return axis * angle
    axis = np.array([
        rotation[2, 1] - rotation[1, 2],
        rotation[0, 2] - rotation[2, 0],
        rotation[1, 0] - rotation[0, 1],
    ]) / (2.0 * math.sin(angle))
    return axis * angle


class _ChainJoint:
    __slots__ = ("name", "jtype", "origin", "axis", "lower", "upper")

    def __init__(self, name, jtype, origin, axis, lower, upper):
        self.name = name
        self.jtype = jtype
        self.origin = origin
        self.axis = axis
        self.lower = lower
        self.upper = upper

    @property
    def movable(self):
        return self.jtype in ("revolute", "continuous", "prismatic")

    @property
    def continuous(self):
        return self.jtype == "continuous"


class URKinematics:
    def __init__(self, urdf_xml, root_link="world", tip_link="tool0"):
        robot = URDF.from_xml_string(urdf_xml)
        self.root_link = root_link
        self.tip_link = tip_link

        chain = []
        link = tip_link
        guard = 0
        while link != root_link:
            guard += 1
            if guard > 1000 or link not in robot.parent_map:
                raise ValueError(
                    f"Cannot build chain from '{root_link}' to '{tip_link}'"
                )
            joint_name, parent = robot.parent_map[link]
            chain.append(robot.joint_map[joint_name])
            link = parent
        chain.reverse()

        self.chain = []
        for joint in chain:
            xyz = [0.0, 0.0, 0.0]
            rpy = [0.0, 0.0, 0.0]
            if joint.origin is not None:
                if joint.origin.xyz is not None:
                    xyz = list(joint.origin.xyz)
                if joint.origin.rpy is not None:
                    rpy = list(joint.origin.rpy)
            origin = make_transform(rpy_to_matrix(rpy), np.array(xyz))
            axis = np.array(joint.axis if joint.axis is not None else [1.0, 0.0, 0.0])
            lower, upper = -math.pi, math.pi
            if joint.limit is not None and joint.type != "continuous":
                lower = joint.limit.lower
                upper = joint.limit.upper
            self.chain.append(
                _ChainJoint(joint.name, joint.type, origin, axis, lower, upper)
            )

        self.movable_names = [j.name for j in self.chain if j.movable]
        self.lower = np.array(
            [j.lower for j in self.chain if j.movable], dtype=float
        )
        self.upper = np.array(
            [j.upper for j in self.chain if j.movable], dtype=float
        )
        self.num_joints = len(self.movable_names)

    def fk(self, q):
        q = np.asarray(q, dtype=float)
        transform = np.eye(4)
        axes = []
        points = []
        idx = 0
        for joint in self.chain:
            after_origin = transform @ joint.origin
            if joint.movable:
                angle = q[idx]
                axis_world = after_origin[:3, :3] @ joint.axis
                axis_world = axis_world / (np.linalg.norm(axis_world) + 1e-12)
                axes.append(axis_world)
                points.append(after_origin[:3, 3].copy())
                if joint.jtype == "prismatic":
                    local = make_transform(np.eye(3), joint.axis * angle)
                else:
                    local = make_transform(axis_angle_matrix(joint.axis, angle), np.zeros(3))
                transform = after_origin @ local
                idx += 1
            else:
                transform = after_origin
        return transform, axes, points

    def jacobian(self, q):
        transform, axes, points = self.fk(q)
        p_end = transform[:3, 3]
        jac = np.zeros((6, self.num_joints))
        for i, joint in enumerate([j for j in self.chain if j.movable]):
            if joint.jtype == "prismatic":
                jac[:3, i] = axes[i]
            else:
                jac[:3, i] = np.cross(axes[i], p_end - points[i])
                jac[3:, i] = axes[i]
        return jac, transform

    def _clamp(self, q):
        clamped = q.copy()
        for i, joint in enumerate([j for j in self.chain if j.movable]):
            if joint.continuous:
                clamped[i] = math.atan2(math.sin(clamped[i]), math.cos(clamped[i]))
            else:
                clamped[i] = min(max(clamped[i], self.lower[i]), self.upper[i])
        return clamped

    def ik(
        self,
        target,
        q_seed,
        position_only=False,
        max_iters=300,
        pos_tol=2e-3,
        rot_tol=1e-2,
        damping=0.06,
        max_step=0.2,
    ):
        q = self._clamp(np.asarray(q_seed, dtype=float).copy())
        target_p = target[:3, 3]
        target_r = target[:3, :3]
        eye = np.eye(6)
        for _ in range(max_iters):
            jac, transform = self.jacobian(q)
            pos_err = target_p - transform[:3, 3]
            if position_only:
                err = pos_err
                jac_used = jac[:3, :]
                eye_used = np.eye(3)
                converged = np.linalg.norm(pos_err) < pos_tol
            else:
                rot_err = rotation_to_vector(target_r @ transform[:3, :3].T)
                err = np.concatenate([pos_err, rot_err])
                jac_used = jac
                eye_used = eye
                converged = (
                    np.linalg.norm(pos_err) < pos_tol
                    and np.linalg.norm(rot_err) < rot_tol
                )
            if converged:
                return self._clamp(q), True
            jjt = jac_used @ jac_used.T + (damping ** 2) * eye_used
            dq = jac_used.T @ np.linalg.solve(jjt, err)
            norm = np.linalg.norm(dq)
            if norm > max_step:
                dq = dq * (max_step / norm)
            q = self._clamp(q + dq)
        _, transform = self.jacobian(q)
        pos_err = np.linalg.norm(target_p - transform[:3, 3])
        if position_only:
            return q, pos_err < pos_tol
        rot_err = np.linalg.norm(rotation_to_vector(target_r @ transform[:3, :3].T))
        return q, (pos_err < pos_tol and rot_err < rot_tol)
