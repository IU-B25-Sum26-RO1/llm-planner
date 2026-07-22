#!/usr/bin/env python3

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "decomposer"))

from decomposer.llm_client import LLMClient
from decomposer.sys_prompt_collector import get_system_prompt


TEST_CASES = [
    ("pick_simple", "Возьми кружку."),
    ("place_simple", "Положи бутылку на стол."),
    ("non_command", "Ой."),
    ("non_command2", "Красиво."),
    ("stop", "Стой."),
    ("multi_action", "Возьми кружку и поставь её на стол."),
    ("complex", "Возьми самую левую красную кружку рядом с бутылкой."),
    ("go_home_pick", "Вернись домой, затем возьми зелёный куб."),
    ("open_gripper", "Открой захват."),
    ("ambiguous", "Сделай что-нибудь с этим."),
]


def analyze_hallucination(name: str, utterance: str, result: dict) -> list[str]:
    issues = []
    if "error" in result:
        issues.append(f"ERROR: {result['error']}")
        return issues

    if result.get("text") and result["text"] != utterance:
        issues.append(f"text mismatch: got '{result.get('text')}'")

    cmd_type = result.get("type")
    tasks = result.get("tasks", [])

    if name.startswith("non_command"):
        if cmd_type != "non_command":
            issues.append(f"expected non_command, got {cmd_type}")
        if tasks:
            issues.append(f"non_command has tasks: {tasks}")
        return issues

    if cmd_type != "command":
        issues.append(f"expected command, got {cmd_type}")
        return issues

    expected_actions = {
        "pick_simple": ["pick"],
        "place_simple": ["place"],
        "stop": ["stop"],
        "multi_action": ["pick", "place"],
        "complex": ["pick"],
        "go_home_pick": ["go_home", "pick"],
        "open_gripper": ["open_gripper"],
    }
    if name in expected_actions:
        actual = [t.get("action") for t in tasks]
        if actual != expected_actions[name]:
            issues.append(f"actions mismatch: expected {expected_actions[name]}, got {actual}")

    for i, task in enumerate(tasks):
        action = task.get("action")
        target = task.get("target")

        if action in ("pick", "place", "move_to") and target is None:
            issues.append(f"task[{i}] action={action} but target is null")

        if target:
            obj = target.get("object", {})
            cls = obj.get("class")
            if cls and not isinstance(cls, str):
                issues.append(f"task[{i}] object.class is not string: {cls}")

            for space in target.get("search_space", []):
                ref = space.get("reference", {})
                if "object" in ref:
                    issues.append(f"task[{i}] search_space.reference has nested 'object' key (hallucinated schema)")

            sel = target.get("selection")
            if sel and sel.get("type") not in (
                "nearest", "furthest", "largest", "smallest",
                "leftmost", "rightmost", "topmost", "bottommost",
                "first", "last", "any", "same", None,
            ):
                issues.append(f"task[{i}] unknown selection type: {sel}")

        placement = task.get("placement")
        if placement:
            ref = placement.get("reference")
            if ref and "object" in ref:
                pref_obj = ref["object"]
                if "prompt" not in pref_obj:
                    issues.append(f"task[{i}] placement reference object missing prompt")

    return issues


class _PrintLogger:
    def info(self, msg): print(f"[INFO] {msg}")
    def warning(self, msg): print(f"[WARN] {msg}")
    def error(self, msg): print(f"[ERROR] {msg}")


async def main():
    base_url = os.environ.get("LLM_API_URL", "http://localhost:11434/v1")
    model = os.environ.get("LLM_MODEL", "llama3:latest")
    prompt_path = os.environ.get(
        "SYS_PROMPT_PATH",
        os.path.join(os.path.dirname(__file__), "..", "prompts", "decomposer_system_prompt.txt"),
    )

    system_prompt = get_system_prompt(prompt_path)
    if not system_prompt:
        print(f"Failed to load prompt from {prompt_path}")
        sys.exit(1)

    print(f"Model: {model}")
    print(f"Prompt: {prompt_path} ({len(system_prompt)} chars)")
    print("=" * 70)

    client = LLMClient(
        base_url=base_url,
        model=model,
        api_key=os.environ.get("LLM_API_KEY", "ollama"),
        system_prompt=system_prompt,
        logger=_PrintLogger(),
    )

    passed = 0
    failed = 0

    for name, utterance in TEST_CASES:
        print(f"\n[{name}] Input: {utterance!r}")
        result = await client.decompose(utterance)
        issues = analyze_hallucination(name, utterance, result)

        print(json.dumps(result, ensure_ascii=False, indent=2))

        if issues:
            failed += 1
            print("ISSUES:")
            for issue in issues:
                print(f"  - {issue}")
        else:
            passed += 1
            print("OK")

    print("\n" + "=" * 70)
    print(f"Results: {passed} OK, {failed} with issues, {len(TEST_CASES)} total")


if __name__ == "__main__":
    asyncio.run(main())
