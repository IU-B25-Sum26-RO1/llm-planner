"""Canonical contract for LLM-generated robot tasks."""

LLM_ACTIONS = frozenset(
    {
        "pick",
        "place",
        "open_gripper",
        "close_gripper",
        "go_home",
        "stop",
    }
)

TARGET_REQUIRED_ACTIONS = frozenset({"pick"})
PLACEMENT_REQUIRED_ACTIONS = frozenset({"place"})
