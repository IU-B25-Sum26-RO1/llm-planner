#!/usr/bin/env bash

# Exercise the same Compose service command used in production.  This is a
# host-side test and therefore requires Docker Compose and the ROS Humble image.
set -euo pipefail

service=ur10e_control
container=control_container
health_timeout_seconds=70
stop_timeout_seconds=20

cleanup_needed=false

cleanup() {
    if [[ "$cleanup_needed" == true ]]; then
        docker compose stop -t "$stop_timeout_seconds" "$service" >/dev/null || true
    fi
}

trap cleanup EXIT

if [[ -n "$(docker compose ps --status running -q "$service")" ]]; then
    printf '%s is already running; stop it before running this smoke test.\n' "$service" >&2
    exit 2
fi

docker compose up -d --no-deps --force-recreate "$service"
cleanup_needed=true

deadline=$((SECONDS + health_timeout_seconds))
while true; do
    health_status="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}missing{{end}}' "$container")"
    if [[ "$health_status" == healthy ]]; then
        break
    fi
    if (( SECONDS >= deadline )); then
        docker compose logs "$service" >&2 || true
        printf '%s did not become healthy (last status: %s).\n' "$service" "$health_status" >&2
        exit 1
    fi
    sleep 2
done

# The node list proves the two programs from run_control.sh are alive together;
# the in-container verifier checks their client/server endpoints and action type.
nodes="$(docker compose exec -T "$service" bash -c '
    source /opt/ros/humble/setup.bash
    source /workspace/install/setup.bash
    ros2 node list
')"
grep -Fxq '/task_manager_node' <<<"$nodes"
grep -Fxq '/ur10e_interface' <<<"$nodes"
docker compose exec -T "$service" \
    bash /workspace/src/ur10e_control_system/scripts/verify_base_action.sh

docker compose stop -t "$stop_timeout_seconds" "$service"
cleanup_needed=false

exit_code="$(docker inspect --format '{{.State.ExitCode}}' "$container")"
if [[ "$exit_code" != 0 ]]; then
    docker compose logs "$service" >&2 || true
    printf '%s exited with %s instead of a clean zero exit.\n' "$service" "$exit_code" >&2
    exit 1
fi

printf 'Docker Compose control smoke test passed.\n'
