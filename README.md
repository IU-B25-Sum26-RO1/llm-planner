# UR10e Gazebo Simulation (ROS 2 Humble)

Базовая сцена для проекта Embodied AI (LLM Planner). Включает в себя манипулятор UR10e, зафиксированный на столе, тестовые объекты (лоток и кубик) и настроенные контроллеры (`ros2_control`) для удержания позы и перемещения. 

Проект полностью контейнеризирован и оптимизирован для работы в **WSL2** с аппаратным ускорением графики.

## Быстрый запуск (WSL2 / Windows)

### 1. Сборка Docker-образа
Откройте терминал в корневой папке проекта и соберите образ (в него уже зашиты все необходимые зависимости ROS 2 и плагины контроллеров):
```bash
docker build -t ur10e-gazebo-img
```

### 2. Запуск контейнера (с пробросом GPU)
Для плавной работы в симуляции в 60 FPS на WSL 2 используется проброс DirectX графики.
```bash
docker run -it --rm \
  -e DISPLAY=$DISPLAY \
  -v /tmp/.X11-unix:/tmp/.X11-unix \
  -v /usr/lib/wsl:/usr/lib/wsl \
  --device /dev/dxg \
  -e LD_LIBRARY_PATH=/usr/lib/wsl/lib \
  -v $(pwd):/workspace \
  ur10e-gazebo-img
```

### 3. Запуск симуляции
Оказавшись внутри контейнера (root@...), запустите launch-файл сцены:
```bash
ros2 launch /workspace/src/ur10e_scene/launch/start_scene.launch.py
```
