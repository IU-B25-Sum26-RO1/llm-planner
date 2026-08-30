#!/usr/bin/env bash

set -euo pipefail

source "${ROS_SETUP_FILE:-/opt/ros/humble/setup.bash}"
source "${WORKSPACE_SETUP_FILE:-/workspace/install/setup.bash}"

action_name=/execute/base_action
expected_type=robot_interfaces/action/BaseAction

actual_type="$(ros2 action type "$action_name")"
if [[ "$actual_type" != "$expected_type" ]]; then
    printf 'Expected %s to have type %s, got %s\n' \
        "$action_name" "$expected_type" "${actual_type:-<none>}" >&2
    exit 1
fi

action_info="$(ros2 action info "$action_name")"
printf '%s\n' "$action_info"

grep -Eq '^Action clients: [1-9][0-9]*$' <<<"$action_info"
grep -Eq '^Action servers: [1-9][0-9]*$' <<<"$action_info"
grep -Fxq '    /task_manager_node' <<<"$action_info"
grep -Fxq '    /ur10e_interface' <<<"$action_info"
