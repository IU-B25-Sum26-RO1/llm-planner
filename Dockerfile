FROM osrf/ros:humble-desktop

RUN apt-get update && apt-get install -y \
    ros-humble-gazebo-ros-pkgs \
    ros-humble-ur \
    ros-humble-gazebo-ros2-control \
    ros-humble-ros2-controllers \
    nano \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

RUN echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc
