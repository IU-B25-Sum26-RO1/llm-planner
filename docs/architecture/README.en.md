# Architecture

[Русская версия](README.md)

## Primary execution path

```text
microphone
  -> audio_processor (Vosk)
  -> /recognized_text
  -> decomposer (OpenAI-compatible LLM + Pydantic validation)
  -> /decomposer/json_output/command
  -> task_manager_node
  -> /execute/base_action
  -> ur10e_interface
  -> ros2_control / Gazebo
```

The visual path runs in parallel:

```text
Gazebo/camera
  -> /camera/color/image_raw
  -> sam3_preprocessor (resize, FPS limit, JPEG)
  -> sam3_bridge (WebSocket)
  -> /sam3/output/mask_raw
```

Task Manager publishes the selected target to `/to_track/target`, and
`sam3_bridge` forwards it to the external SAM3 service. The mask is not yet
converted into a 3-D pose or used for step verification or replanning. Simulated
`pick` and `place` currently resolve objects by model name through
`/gazebo/model_states`.

## Command contract

The canonical LLM contract exposes six actions:

- `pick`
- `place`
- `open_gripper`
- `close_gripper`
- `go_home`
- `stop`

The LLM response is validated against a strict Pydantic schema before it is
published to ROS. The `speed` and `precision` modifiers are forwarded through
the action contract and influence bounded movement speed and endpoint tolerance.
Object selection, search-space constraints, and placement relations remain in
the JSON but do not yet affect execution.

## Current implementation boundaries

- `pick` and `place` are deterministic IK sequences with virtual Gazebo object
  attachment, not trained policies.
- Cartesian workspace limits and final joint-error checks exist, but there is no
  collision-aware motion planning or hardware emergency-stop path.
- There is no SAM3 mask consumer, depth-to-world localization, step verifier,
  recovery/replanning loop, or measured end-to-end robot trial set.
- LLM decomposition has a separate 14-command corpus and exact evaluator.
- Runtime acceptance belongs on Windows/WSL2; source-only checks on macOS do not
  prove the ROS/Gazebo stack.

See the [project review](../review-2026-09-04.md) for detailed findings and the
[team TODO](../TODO.md) for the dependency-ordered implementation plan.
