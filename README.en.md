# LLM Planner

[Русская документация](README.md)

Voice and text control for a UR10e robot. An LLM decomposes an operator command
into primitives that are executed in a Gazebo simulation using ROS 2 Humble.

Pipeline: microphone -> Vosk -> LLM decomposition -> Task Manager -> UR10e
Interface / Gazebo. Optional visual pipeline: camera frames -> SAM3.

## Requirements

- Windows 10/11 with **WSL2** running Ubuntu
- [Docker](https://docs.docker.com/engine/install/) inside WSL, either Docker
  Engine or Docker Desktop with WSL integration
- Access to an OpenAI-compatible LLM API exposing `/v1/chat/completions`
- A Russian [Vosk model](https://alphacephei.com/vosk/models), with
  `vosk-model-small-ru-0.22` used by default
- Optional external SAM3 WebSocket segmentation server

Verify the host tools:

```bash
docker --version
docker compose version
```

## Clone the repository

```bash
git clone git@github.com:IU-B25-Sum26-RO1/llm-planner.git
cd llm-planner
```

## Configuration

Copy the environment template and edit it for your system:

```bash
cp .env.example .env
```

Important `.env` variables:

| Variable | Purpose |
|---|---|
| `HOST_VOSK_MODELS_PATH` | Host directory containing Vosk models; defaults to `./models` |
| `VOSK_MODEL` | Model subdirectory inside `models/` |
| `AUDIO_SAMPLERATE` / `AUDIO_BLOCK_SIZE` | Audio capture parameters |
| `PULSE_SERVER` / `AUDIO_DEVICE` | PulseAudio configuration; WSLg normally uses `unix:/mnt/wslg/PulseServer` |
| `LLM_API_URL` | Base URL of the OpenAI-compatible API |
| `LLM_API_KEY` | API key; use any non-empty value if the server does not require one |
| `LLM_MODEL` | Model identifier |
| `SYS_PROMPT_PATH` | System-prompt path inside the container |
| `LIBGL_ALWAYS_SOFTWARE` | `1` for xvfb/software GL; `0` for GPU rendering through WSLg |
| `DISPLAY` / `WAYLAND_DISPLAY` | Gazebo GUI display settings |
| `CAMERA_RAW_TOPIC` | Raw camera topic |
| `SAM3_SERVER_URL` | SAM3 WebSocket URL |
| `TARGET_VIDEO_FPS` / `TARGET_VIDEO_WIDTH` / `TARGET_VIDEO_HEIGHT` | Preprocessor video settings |

### Verify camera -> preprocessor -> SAM3

The default input topic is `/camera/color/image_raw`. It matches both
`CAMERA_RAW_TOPIC` in `.env.example` and the topic published by `camera_driver`.
Build the affected packages:

```bash
source /opt/ros/humble/setup.bash
colcon build --packages-select camera_driver sam3_preprocessor sam3_bridge
source install/setup.bash
```

Open three terminals. In each terminal, source ROS and the workspace before
starting the publisher, preprocessor, or bridge:

```bash
ros2 run camera_driver camera_publisher
```

```bash
CAMERA_RAW_TOPIC=/camera/color/image_raw ros2 run sam3_preprocessor preprocessor
```

```bash
SAM3_SERVER_URL=ws://localhost:8120/websocket ros2 run sam3_bridge bridge
```

In a fourth terminal, inspect the topic types and data flow:

```bash
ros2 topic info -v /camera/color/image_raw
ros2 topic info -v /camera/color/image_raw/processed
ros2 topic echo --once /camera/color/image_raw/processed sensor_msgs/msg/CompressedImage
```

When using the simulator, do not start `camera_driver`; let `ur10e_scene`
publish `/camera/color/image_raw`. If a SAM3 server is available, also verify the
mask output:

```bash
ros2 topic echo --once /sam3/output/mask_raw sensor_msgs/msg/Image
```

### Vosk model

```bash
mkdir -p models
cd models
wget https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip
unzip vosk-model-small-ru-0.22.zip
cd ..
```

Set the following values in `.env`:

```env
HOST_VOSK_MODELS_PATH=./models
VOSK_MODEL=vosk-model-small-ru-0.22
```

### LLM endpoint

Start an OpenAI-compatible endpoint, such as vLLM or Ollama behind an
OpenAI-compatible proxy, and configure `.env`:

```env
LLM_API_URL=http://host.docker.internal:8000/v1
LLM_API_KEY=not-needed
LLM_MODEL=Qwen/Qwen2.5-3B-Instruct
SYS_PROMPT_PATH=/workspace/prompts/decomposer_system_prompt.txt
```

`host.docker.internal` must resolve from inside the container. If necessary,
enable `extra_hosts` for the `decomposer` service in `docker-compose.yml`.

## Run the stack

Build and start all services from the repository root:

```bash
docker compose build
docker compose up
```

Services:

| Service | Responsibility |
|---|---|
| `audio_processor` | Microphone capture and Vosk speech recognition |
| `decomposer` | LLM-based text-command decomposition |
| `simulation` | Gazebo and the UR10e scene |
| `ur10e_control` | Task Manager and `ur10e_interface` |
| `sam3_preprocessor` | Camera frame preprocessing |
| `sam3_bridge` | Client for the external SAM3 service |

Stop the stack:

```bash
docker compose down
```

Verify the Task Manager -> BaseAction connection after startup:

```bash
docker compose exec ur10e_control \
  bash /workspace/src/ur10e_control_system/scripts/verify_base_action.sh
```

The command exits with status 0 only when `/execute/base_action` has type
`robot_interfaces/action/BaseAction` and the ROS graph exposes at least one
server and one client. The same check is used by the `ur10e_control` healthcheck.

### `ur10e_control` smoke test

After building the ROS Humble image, run this command from the repository root:

```bash
docker compose build && bash tests/docker-compose-control-smoke-test.sh
```

The test starts the real `ur10e_control` Compose service without its external
dependencies. It checks that `task_manager_node` and `ur10e_interface` run at
the same time and that `/execute/base_action` exposes the required client,
server, and type. It then stops the service. Do not run this test while a working
`ur10e_control` session is active: the script exits instead of interrupting it.

Rebuild and restart one service:

```bash
docker compose up -d --build simulation
```

### Gazebo graphics

- **Docker Desktop or no GPU:** keep `LIBGL_ALWAYS_SOFTWARE=1` to run through
  xvfb/software GL.
- **Native Docker in WSL with a GPU:** set `LIBGL_ALWAYS_SOFTWARE=0` and verify
  `/dev/dxg`, WSLg, `DISPLAY`, and `/mnt/wslg`.

### Simulation only, without voice input

```bash
docker compose up simulation
```

Send a basic command through the CLI inside a running simulation:

```bash
docker compose exec simulation bash -c \
  "source /opt/ros/humble/setup.bash && source /workspace/install/setup.bash && \
   ros2 run ur10e_control_system cli pick green_cube"
```

CLI examples:

```text
cli home
cli pick green_cube
cli place white_tray
cli move_to_object green_cube
cli move_to 0.3 0.2 1.05
cli forward 0.1
```

### Start the scene launch file manually

If `llm_planner_image:latest` is already built:

```bash
docker run -it --rm --network host --privileged \
  -e DISPLAY=$DISPLAY \
  -e LIBGL_ALWAYS_SOFTWARE=1 \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v /usr/lib/wsl:/usr/lib/wsl \
  -v "$(pwd)/src:/workspace/src" \
  llm_planner_image:latest \
  bash -c "source /opt/ros/humble/setup.bash && source /workspace/install/setup.bash && \
           ros2 launch ur10e_scene start_scene.launch.py"
```

## Repository structure

```text
.
├── docker-compose.yml      # system services
├── Dockerfile              # ROS 2 Humble, dependencies, and colcon build
├── evaluation/             # versioned LLM evaluation corpus and text fixtures
├── prompts/                # LLM system prompt
├── schemas/                # Pydantic command schemas
├── scripts/                # standalone evaluation tools
├── tests/                  # unit, regression, and Compose smoke tests
└── src/
    ├── audio_processor/    # microphone, Vosk, and text replay
    ├── decomposer/         # LLM planner
    ├── ur10e_control_system/
    ├── ur10e_scene/        # Gazebo world, URDF, and launch files
    ├── robot_interfaces/   # actions and services
    ├── sam3_preprocessor/
    ├── sam3_bridge/
    └── camera_driver/
```

## Local Python development without ROS

For unit and regression tests outside Docker:

```bash
# uv is required: https://docs.astral.sh/uv/
uv sync
source .venv/bin/activate
python -m pytest
```

`.python-version` pins Python 3.10 to match ROS 2 Humble. Vosk 0.3.45 is
installed only on Linux because it has no macOS/Apple Silicon distribution.
macOS can run source-level unit and regression tests, but full audio, ROS,
Gazebo, and runtime acceptance must run in the Windows/WSL2/Docker environment.

## Evaluate LLM decomposition

[`evaluation/decomposer_commands.json`](evaluation/decomposer_commands.json)
contains 14 versioned Russian-language cases covering all six actions,
multi-step commands, spatial constraints, object selection, unsupported
requests, and `non_command` utterances.

After configuring the LLM, run several trials for each case:

```bash
set -a
source .env
set +a
python scripts/evaluate_decomposer.py --trials 3
```

The evaluator checks the Pydantic schema, command type, action order, language,
source-text preservation, and required semantic fields. It writes a detailed
report to `artifacts/evaluations/decomposer-evaluation.json` and exits with
status 0 only at 100% exact accuracy. This evaluates the planner, not successful
robot execution.

### Repeatable input without a microphone

Use `evaluation/recognized_text_smoke.txt` to smoke-test the
`recognized_text -> decomposer` boundary. After starting `decomposer`, run this
in another terminal:

```bash
docker compose exec decomposer bash -c \
  "source /opt/ros/humble/setup.bash && source /workspace/install/setup.bash && \
   ros2 run audio_processor text_replay --ros-args \
   -p transcript_path:=/workspace/evaluation/recognized_text_smoke.txt"
```

The node waits for a `/recognized_text` subscriber, publishes each command in
order, and stops its timer after the final line. This makes planner input
repeatable but does not independently validate Vosk or physical execution.

## Useful commands

```bash
# decomposer logs
docker compose logs -f decomposer

# ROS topics from any stack container
docker compose exec decomposer bash -c \
  "source /opt/ros/humble/setup.bash && source /workspace/install/setup.bash && ros2 topic list"

# Send text directly to decomposer, bypassing the microphone
docker compose exec decomposer bash -c \
  "source /opt/ros/humble/setup.bash && source /workspace/install/setup.bash && \
   ros2 topic pub --once /recognized_text std_msgs/msg/String \
   \"{data: 'Возьми зелёный куб'}\""
```

## Additional documentation

- [Windows/WSL2 deployment quick start](docs/deployment.en.md)
- [Architecture](docs/architecture/README.en.md)
- [Contribution workflow](CONTRIBUTING.en.md)
- [Team TODO](docs/TODO.md)
- [Project review](docs/review-2026-09-04.md)
