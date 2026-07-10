from setuptools import find_packages, setup

package_name = 'audio_processor'

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
    maintainer='Aioma',
    maintainer_email='idfc1200@gmail.com',
    description='ROS2 Package for speech recognizing using Vosk',
    license='Apache License 2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'audio_processor = audio_processor.audio_processor_node:main',
        ],
    },
)
