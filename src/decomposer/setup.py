from setuptools import find_packages, setup

package_name = 'decomposer'

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
    maintainer_email='idfc1@gmail.com',
    description='ROS2 Package for text decomposition using LLM',
    license='Apache-2.0',
    tests_require=['pytest'],
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'decomposer = decomposer.decomposer_node:main',
        ],
    },
)
