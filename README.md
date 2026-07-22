# LLM Planner

Голосовое и текстовое управление роботом UR10e: LLM разбивает команду оператора на примитивы, которые исполняются в симуляции Gazebo (ROS 2 Humble).

Пайплайн: микрофон → Vosk → LLM-декомпозиция → Task Manager → UR10e Interface / Gazebo. Опционально: кадры камеры → SAM3.

## Требования

- Windows 10/11 + **WSL2** (Ubuntu)
- [Docker](https://docs.docker.com/engine/install/) в WSL (Docker Engine или Docker Desktop с интеграцией WSL)
- Доступ к LLM API в формате OpenAI-compatible (`/v1/chat/completions`)
- Модель [Vosk](https://alphacephei.com/vosk/models) для русского языка (по умолчанию `vosk-model-small-ru-0.22`)
- (Опционально) внешний SAM3 WebSocket-сервер для сегментации

Проверьте:

```bash
docker --version
docker compose version
```

## Клонирование

```bash
git clone git@github.com:IU-B25-Sum26-RO1/llm-planner.git
cd llm-planner
```

## Конфигурация

Скопируйте пример окружения и отредактируйте под себя:

```bash
cp .env.example .env
```

Основные переменные в `.env`:

| Переменная | Назначение |
|---|---|
| `HOST_VOSK_MODELS_PATH` | Путь к каталогу с моделями Vosk на хосте (по умолчанию `./models`) |
| `VOSK_MODEL` | Имя подкаталога модели внутри `models/` |
| `AUDIO_SAMPLERATE` / `AUDIO_BLOCK_SIZE` | Параметры захвата аудио |
| `PULSE_SERVER` / `AUDIO_DEVICE` | PulseAudio (WSLg: `unix:/mnt/wslg/PulseServer`) |
| `LLM_API_URL` | Базовый URL OpenAI-compatible API |
| `LLM_API_KEY` | API-ключ (если не нужен — любое значение) |
| `LLM_MODEL` | Имя модели |
| `SYS_PROMPT_PATH` | Путь к system prompt внутри контейнера |
| `LIBGL_ALWAYS_SOFTWARE` | `1` — xvfb/software GL (Docker Desktop); `0` — GPU через WSLg |
| `DISPLAY` / `WAYLAND_DISPLAY` | Дисплей для GUI Gazebo |
| `CAMERA_RAW_TOPIC` | Топик сырого изображения камеры |
| `SAM3_SERVER_URL` | WebSocket URL сервера SAM3 |
| `TARGET_VIDEO_FPS` / `TARGET_VIDEO_WIDTH` / `TARGET_VIDEO_HEIGHT` | Параметры видео для preprocessor |

### Модель Vosk

```bash
mkdir -p models
cd models
wget https://alphacephei.com/vosk/models/vosk-model-small-ru-0.22.zip
unzip vosk-model-small-ru-0.22.zip
cd ..
```

В `.env` должно быть:

```env
HOST_VOSK_MODELS_PATH=./models
VOSK_MODEL=vosk-model-small-ru-0.22
```

### LLM

Запустите свой OpenAI-compatible endpoint (vLLM, Ollama с OpenAI-прокси, и т.п.) и укажите в `.env`:

```env
LLM_API_URL=http://host.docker.internal:8000/v1
LLM_API_KEY=not-needed
LLM_MODEL=Qwen/Qwen2.5-3B-Instruct
SYS_PROMPT_PATH=/workspace/prompts/decomposer_system_prompt.txt
```

`host.docker.internal` должен резолвиться из контейнера на хост. При необходимости раскомментируйте `extra_hosts` у сервиса `decomposer` в `docker-compose.yml`.

## Запуск

Сборка образа и поднятие всех сервисов из корня репозитория:

```bash
docker compose build
docker compose up
```

Сервисы:

| Сервис | Что делает |
|---|---|
| `audio_processor` | Захват микрофона, распознавание речи (Vosk) |
| `decomposer` | Декомпозиция текста командой через LLM |
| `simulation` | Gazebo + сцена UR10e + `ur10e_interface` |
| `ur10e_control` | Task Manager (очередь задач на робота) |
| `sam3_preprocessor` | Прокидывание/подготовка кадров камеры |
| `sam3_bridge` | Клиент к внешнему SAM3 |

Остановка:

```bash
docker compose down
```

Перезапуск одного сервиса:

```bash
docker compose up -d --build simulation
```

### Графика Gazebo

- **Docker Desktop / без GPU:** оставьте `LIBGL_ALWAYS_SOFTWARE=1` (симуляция через `xvfb`).
- **Нативный Docker в WSL + GPU:** поставьте `LIBGL_ALWAYS_SOFTWARE=0`, проверьте доступ к `/dev/dxg` и WSLg (`DISPLAY`, `/mnt/wslg`).

### Только симуляция (без голоса)

```bash
docker compose up simulation
```

Внутри уже поднятой симуляции можно слать базовые команды через CLI:

```bash
docker compose exec simulation bash -c \
  "source /opt/ros/humble/setup.bash && source /workspace/install/setup.bash && \
   ros2 run ur10e_control_system cli pick green_cube"
```

Примеры CLI:

```text
cli home
cli pick green_cube
cli place white_tray
cli move_to_object green_cube
cli move_to 0.3 0.2 1.05
cli forward 0.1
```

### Ручной запуск launch-файла сцены

Если контейнер уже собран (`llm_planner_image:latest`):

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

## Структура репозитория

```text
.
├── docker-compose.yml      # сервисы системы
├── Dockerfile              # ROS 2 Humble + зависимости + colcon build
├── prompts/                # system prompt для LLM
├── schemas/                # pydantic-схемы команд
├── scripts/                # вспомогательные скрипты (тест декомпозиции)
└── src/
    ├── audio_processor/    # микрофон + Vosk
    ├── decomposer/         # LLM-планировщик
    ├── ur10e_control_system/
    ├── ur10e_scene/        # Gazebo world, URDF, launch
    ├── robot_interfaces/   # action/service
    ├── sam3_preprocessor/
    ├── sam3_bridge/
    └── camera_driver/
```

## Локальная разработка Python-зависимостей (без ROS)

Для скриптов вне Docker (например `scripts/test_llm_decompose.py`):

```bash
# нужен uv: https://docs.astral.sh/uv/
uv sync
source .venv/bin/activate
export LLM_API_URL=http://localhost:8000/v1
export LLM_MODEL=Qwen/Qwen2.5-3B-Instruct
export SYS_PROMPT_PATH=./prompts/decomposer_system_prompt.txt
python scripts/test_llm_decompose.py
```

Полный ROS-стек запускается через Docker, как описано выше.

## Полезные команды

```bash
# логи сервиса
docker compose logs -f decomposer

# список ROS-топиков (из любого контейнера стека)
docker compose exec decomposer bash -c \
  "source /opt/ros/humble/setup.bash && source /workspace/install/setup.bash && ros2 topic list"

# отправить текст напрямую в decomposer (минуя микрофон)
docker compose exec decomposer bash -c \
  "source /opt/ros/humble/setup.bash && source /workspace/install/setup.bash && \
   ros2 topic pub --once /recognized_text std_msgs/msg/String \"{data: 'Возьми зелёный куб'}\""
```

## Дополнительно

- Правила работы с ветками и PR: [CONTRIBUTING.md](CONTRIBUTING.md)
- Краткая заметка по установке: [docs/deployment.md](docs/deployment.md)
