# Архитектура

Текущий основной путь выполнения:

```text
микрофон
  -> audio_processor (Vosk)
  -> /recognized_text
  -> decomposer (OpenAI-compatible LLM + Pydantic validation)
  -> /decomposer/json_output/command
  -> task_manager_node
  -> /execute/base_action
  -> ur10e_interface
  -> ros2_control / Gazebo
```

Визуальный путь существует параллельно:

```text
Gazebo/камера
  -> /camera/color/image_raw
  -> sam3_preprocessor (resize, FPS limit, JPEG)
  -> sam3_bridge (WebSocket)
  -> /sam3/output/mask_raw
```

Task Manager публикует выбранную цель в `/to_track/target`, а `sam3_bridge`
передаёт её внешнему SAM3-серверу. Однако маска пока не преобразуется в
трёхмерную позу и не используется для проверки шага или перепланирования.
Исполнение `pick`/`place` в симуляции ищет модели по имени в
`/gazebo/model_states`.

## Контракт команд

Единый контракт LLM содержит шесть действий:

- `pick`
- `place`
- `open_gripper`
- `close_gripper`
- `go_home`
- `stop`

Ответ LLM проверяется строгой Pydantic-схемой до публикации в ROS. Модификаторы
`speed` и `precision` передаются в action и влияют на ограниченную скорость и
допуск конечного положения. Поля выбора объекта, пространственных ограничений и
отношения размещения сохраняются в JSON, но пока не влияют на исполнение.

## Границы текущей реализации

- `pick`/`place` — детерминированные IK-последовательности с виртуальным
  Gazebo-прикреплением объекта, а не обученные политики.
- Есть ограничение декартовой рабочей области и проверка конечной ошибки
  суставов, но нет collision-aware motion planning или аппаратного E-stop.
- Нет потребителя SAM3-маски, depth-to-world локализации, step verifier,
  recovery/replanning или измеряемого набора end-to-end robot trials. Для
  LLM-декомпозиции уже есть отдельный корпус из 14 команд и точный evaluator.

Подробный аудит и приоритеты: [review-2026-09-04.md](../review-2026-09-04.md).
