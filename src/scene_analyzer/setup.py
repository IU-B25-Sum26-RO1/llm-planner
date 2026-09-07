from setuptools import find_packages, setup


package_name = "scene_analyzer"

setup(
    name=package_name,
    version="0.0.0",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="idfc1",
    maintainer_email="idfc1200@gmail.com",
    description="Camera-based scene analysis for YOLO-World and 3D target pose estimation.",
    license="Apache-2.0",
    extras_require={
        "test": [
            "pytest",
        ],
    },
    entry_points={
        "console_scripts": [
            "yolo_world_detector = scene_analyzer.yolo_world_detector_node:main",
            "yolo_world_probe = scene_analyzer.yolo_world_probe:main",
            "object_pose_estimator = scene_analyzer.object_pose_estimator_node:main",
            "perception_smoke_test = scene_analyzer.perception_smoke_test:main",
        ],
    },
)
