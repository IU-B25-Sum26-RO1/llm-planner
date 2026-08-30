import os
import stat
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFY_SCRIPT = ROOT / "src/ur10e_control_system/scripts/verify_base_action.sh"


def _write_executable(path, content):
    path.write_text(content)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def _environment(tmp_path, action_info):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    _write_executable(
        bin_dir / "ros2",
        "#!/usr/bin/env bash\n"
        "if [[ $1 == action && $2 == type ]]; then\n"
        "  printf '%s\\n' robot_interfaces/action/BaseAction\n"
        "elif [[ $1 == action && $2 == info ]]; then\n"
        f"  cat <<'ACTION_INFO'\n{action_info}\nACTION_INFO\n"
        "else\n"
        "  exit 2\n"
        "fi\n",
    )
    ros_setup = tmp_path / "ros_setup.bash"
    workspace_setup = tmp_path / "workspace_setup.bash"
    ros_setup.touch()
    workspace_setup.touch()
    environment = os.environ.copy()
    environment.update(
        {
            "PATH": f"{bin_dir}:{environment['PATH']}",
            "ROS_SETUP_FILE": str(ros_setup),
            "WORKSPACE_SETUP_FILE": str(workspace_setup),
        }
    )
    return environment


def test_base_action_verification_accepts_task_manager_and_interface(tmp_path):
    action_info = """Action: /execute/base_action
Action clients: 1
    /task_manager_node
Action servers: 1
    /ur10e_interface"""

    result = subprocess.run(
        ["bash", str(VERIFY_SCRIPT)],
        env=_environment(tmp_path, action_info),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "/task_manager_node" in result.stdout


def test_base_action_verification_rejects_unrelated_action_client(tmp_path):
    action_info = """Action: /execute/base_action
Action clients: 1
    /another_client
Action servers: 1
    /ur10e_interface"""

    result = subprocess.run(
        ["bash", str(VERIFY_SCRIPT)],
        env=_environment(tmp_path, action_info),
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
