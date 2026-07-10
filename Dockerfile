FROM osrf/ros:humble-desktop-full

ENV DEBIAN_FRONTEND=noninteractive

SHELL ["/bin/bash", "-c"]

RUN apt-get update && apt-get install -y \
    ros-humble-gazebo-ros-pkgs \
    ros-humble-ur \
    ros-humble-gazebo-ros2-control \
    ros-humble-ros2-controllers \
    python3-colcon-common-extensions \
    curl \
    libasound2-dev \
    libasound2-plugins \
    libportaudio2 \
    pulseaudio-utils \
    # 4vl-utils \
    # libgl1-mesa-glx \
    # libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /workspace

COPY pyproject.toml uv.lock ./

RUN uv pip compile pyproject.toml -o requirements.txt && \
    uv pip sync requirements.txt --system 

RUN uv add opencv-python-headless

COPY ./prompts ./prompts

COPY ./src ./src

RUN source /opt/ros/humble/setup.bash && colcon build --symlink-install

RUN echo "source /opt/ros/humble/setup.bash" >> ~/.bashrc && \
    echo "source /workspace/install/setup.bash" >> ~/.bashrc