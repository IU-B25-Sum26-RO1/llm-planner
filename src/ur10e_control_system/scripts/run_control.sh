#!/usr/bin/env bash

set -euo pipefail

source "${ROS_SETUP_FILE:-/opt/ros/humble/setup.bash}"
source "${WORKSPACE_SETUP_FILE:-/workspace/install/setup.bash}"

terminate_children() {
    trap - INT TERM
    kill -TERM "$task_manager_pid" "$interface_pid" 2>/dev/null || true
    wait "$task_manager_pid" 2>/dev/null || true
    wait "$interface_pid" 2>/dev/null || true
}

trap 'terminate_children; exit 0' INT TERM

ros2 run ur10e_control_system task_manager &
task_manager_pid=$!
ros2 run ur10e_control_system ur10e_interface &
interface_pid=$!

set +e
wait -n "$task_manager_pid" "$interface_pid"
exit_status=$?
set -e

terminate_children
exit "$exit_status"
