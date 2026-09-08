# Installation and startup

[Русская версия](deployment.md)

The supported runtime environment is Windows 10/11 with WSL2 Ubuntu, Docker,
and ROS 2 Humble inside the project image. macOS is suitable only for
source-level Python checks and is not a runtime acceptance platform.

For the complete installation, configuration, verification, and troubleshooting
workflow, see [README.en.md](../README.en.md).

Quick start:

```bash
git clone git@github.com:IU-B25-Sum26-RO1/llm-planner.git
cd llm-planner
cp .env.example .env

# Download the Russian Vosk model into ./models.
# Configure LLM_API_URL, LLM_API_KEY, and LLM_MODEL in .env.

docker compose build
docker compose up
```

Verify the control action graph:

```bash
docker compose exec ur10e_control \
  bash /workspace/src/ur10e_control_system/scripts/verify_base_action.sh
```

Run the isolated control smoke test only when the normal `ur10e_control` service
is not already running:

```bash
bash tests/docker-compose-control-smoke-test.sh
```

The full stack also requires a configured Vosk model, an OpenAI-compatible LLM
endpoint, working WSLg/PulseAudio settings, and optionally a SAM3 server.
