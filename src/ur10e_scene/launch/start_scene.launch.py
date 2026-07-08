import os
from launch import LaunchDescription
from launch.actions import ExecuteProcess
from launch.substitutions import Command
from launch_ros.actions import Node

def generate_launch_description():
    world_path = '/workspace/src/ur10e_scene/worlds/station.world'
    xacro_path = '/workspace/src/ur10e_scene/urdf/ur10e_anchored.urdf.xacro'

    gazebo = ExecuteProcess(
        cmd=['gazebo', '--verbose', world_path, 
             '-s', 'libgazebo_ros_init.so', 
             '-s', 'libgazebo_ros_factory.so'],
        output='screen'
    )

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{'robot_description': Command(['xacro ', xacro_path])}]
    )

    spawn_entity = Node(
        package='gazebo_ros',
        executable='spawn_entity.py',
        arguments=['-topic', 'robot_description', '-entity', 'ur10e'],
        output='screen'
    )

    load_joint_state_broadcaster = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["joint_state_broadcaster"],
    )

    load_joint_trajectory_controller = Node(
        package="controller_manager",
        executable="spawner",
        arguments=["joint_trajectory_controller"],
    )

    return LaunchDescription([
        gazebo,
        robot_state_publisher,
        spawn_entity,
        load_joint_state_broadcaster,
        load_joint_trajectory_controller
    ])
