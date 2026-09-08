#!/usr/bin/env python3
"""Run the versioned decomposer corpus against an OpenAI-compatible endpoint."""

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src" / "decomposer"))

from decomposer.evaluation import (  # noqa: E402
    load_cases,
    score_response,
    summarize_results,
)
from decomposer.llm_client import LLMClient  # noqa: E402
from decomposer.sys_prompt_collector import get_system_prompt  # noqa: E402


DEFAULT_MANIFEST = ROOT / "evaluation" / "decomposer_commands.json"
DEFAULT_OUTPUT = ROOT / "artifacts" / "evaluations" / "decomposer-evaluation.json"


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default=os.environ.get("LLM_API_URL"))
    parser.add_argument("--api-key", default=os.environ.get("LLM_API_KEY", "not-needed"))
    parser.add_argument("--model", default=os.environ.get("LLM_MODEL"))
    parser.add_argument(
        "--system-prompt",
        type=Path,
        default=Path(
            os.environ.get(
                "SYS_PROMPT_PATH", ROOT / "prompts" / "decomposer_system_prompt.txt"
            )
        ),
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--trials", type=int, default=1)
    return parser.parse_args()


async def evaluate(args):
    if args.trials <= 0:
        raise ValueError("--trials must be positive")
    cases = load_cases(args.manifest)
    system_prompt = get_system_prompt(str(args.system_prompt))
    client = LLMClient(
        base_url=args.base_url,
        api_key=args.api_key,
        model=args.model,
        system_prompt=system_prompt,
    )
    results = []
    try:
        for trial in range(1, args.trials + 1):
            for case in cases:
                started = time.monotonic()
                response = await client.decompose(case["utterance"])
                results.append(
                    {
                        "case_id": case["id"],
                        "trial": trial,
                        "utterance": case["utterance"],
                        "expected_type": case["expected_type"],
                        "expected_actions": case["expected_actions"],
                        "latency_seconds": round(time.monotonic() - started, 3),
                        "score": score_response(case, response),
                        "response": response,
                    }
                )
    finally:
        await client.close()

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "base_url": args.base_url,
        "manifest": str(args.manifest),
        "trials_per_case": args.trials,
        "summary": summarize_results(results),
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args()
    try:
        report = asyncio.run(evaluate(args))
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Evaluation failed: {exc}") from exc
    summary = report["summary"]
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    raise SystemExit(0 if summary["passed"] == summary["total_trials"] else 1)


if __name__ == "__main__":
    main()
