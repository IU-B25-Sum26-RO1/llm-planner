import numpy as np

from scene_analyzer.geometry import median_depth_in_bbox, pixel_to_camera_xyz, transform_point


class Transform:
    class TransformData:
        class Translation:
            x = 1.0
            y = 2.0
            z = 3.0

        class Rotation:
            x = 0.0
            y = 0.0
            z = 0.0
            w = 1.0

        translation = Translation()
        rotation = Rotation()

    transform = TransformData()


def test_pixel_to_camera_xyz():
    k = [100.0, 0.0, 50.0, 0.0, 100.0, 40.0, 0.0, 0.0, 1.0]

    assert pixel_to_camera_xyz(60.0, 30.0, 2.0, k) == (0.2, -0.2, 2.0)


def test_median_depth_in_bbox_converts_mm_to_meters():
    depth = np.full((100, 100), 1200, dtype=np.uint16)

    sample = median_depth_in_bbox(depth, [40, 40, 60, 60])

    assert sample == (50.0, 50.0, 1.2)


def test_transform_point_translation_only():
    assert transform_point((0.5, 0.25, 0.125), Transform()) == (1.5, 2.25, 3.125)
