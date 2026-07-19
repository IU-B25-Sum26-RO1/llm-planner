from setuptools import find_packages, setup

package_name = 'ur10e_control_system'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='idfc1',
    maintainer_email='idfc1200@gmail.com',
    description='Basic manipulation policies for the anchored UR10e in Gazebo '
                '(move, directional jog, grasp/release, pick/place) with URDF-based IK.',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'ur10e_interface = ur10e_control_system.robot_interface_node:main',
            'cli = ur10e_control_system.cli:main',
        ],
    },
)
