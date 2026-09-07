import math

import numpy as np


def pixel_to_camera_xyz(u: float, v: float, depth_m: float, camera_matrix) -> tuple[float, float, float]:
    if depth_m <= 0.0 or not math.isfinite(depth_m):
        raise ValueError("depth_m must be a positive finite value")

    fx = float(camera_matrix[0])
    fy = float(camera_matrix[4])
    cx = float(camera_matrix[2])
    cy = float(camera_matrix[5])
    if fx == 0.0 or fy == 0.0:
        raise ValueError("camera intrinsics fx/fy must be non-zero")

    x = (float(u) - cx) * depth_m / fx
    y = (float(v) - cy) * depth_m / fy
    z = depth_m
    return x, y, z


def median_depth_in_bbox(depth_image, bbox, crop_ratio: float = 0.35) -> tuple[float, float, float] | None:
    if depth_image is None:
        return None

    height, width = depth_image.shape[:2]
    x1, y1, x2, y2 = [float(value) for value in bbox]
    x1 = max(0.0, min(width - 1.0, x1))
    x2 = max(0.0, min(width - 1.0, x2))
    y1 = max(0.0, min(height - 1.0, y1))
    y2 = max(0.0, min(height - 1.0, y2))
    if x2 <= x1 or y2 <= y1:
        return None

    cx = (x1 + x2) / 2.0
    cy = (y1 + y2) / 2.0
    box_w = max(1.0, x2 - x1)
    box_h = max(1.0, y2 - y1)
    crop_w = max(1.0, box_w * crop_ratio)
    crop_h = max(1.0, box_h * crop_ratio)

    sx1 = int(max(0, round(cx - crop_w / 2.0)))
    sx2 = int(min(width, round(cx + crop_w / 2.0)))
    sy1 = int(max(0, round(cy - crop_h / 2.0)))
    sy2 = int(min(height, round(cy + crop_h / 2.0)))
    if sx2 <= sx1 or sy2 <= sy1:
        return None

    patch = np.asarray(depth_image[sy1:sy2, sx1:sx2], dtype=np.float32)
    valid = patch[np.isfinite(patch) & (patch > 0.0)]
    if valid.size == 0:
        return None

    depth = float(np.median(valid))
    if depth > 100.0:
        depth /= 1000.0
    return cx, cy, depth


def transform_point(point, transform) -> tuple[float, float, float]:
    translation = transform.transform.translation
    rotation = transform.transform.rotation
    matrix = _quaternion_to_matrix(rotation.x, rotation.y, rotation.z, rotation.w)
    translated = matrix @ np.asarray(point, dtype=np.float64)
    translated += np.array([translation.x, translation.y, translation.z], dtype=np.float64)
    return float(translated[0]), float(translated[1]), float(translated[2])


def _quaternion_to_matrix(x: float, y: float, z: float, w: float):
    norm = x * x + y * y + z * z + w * w
    if norm < 1e-12:
        return np.eye(3, dtype=np.float64)
    scale = 2.0 / norm
    xx = x * x * scale
    yy = y * y * scale
    zz = z * z * scale
    xy = x * y * scale
    xz = x * z * scale
    yz = y * z * scale
    wx = w * x * scale
    wy = w * y * scale
    wz = w * z * scale
    return np.array(
        [
            [1.0 - yy - zz, xy - wz, xz + wy],
            [xy + wz, 1.0 - xx - zz, yz - wx],
            [xz - wy, yz + wx, 1.0 - xx - yy],
        ],
        dtype=np.float64,
    )
