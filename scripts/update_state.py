#!/usr/bin/env python3
"""Create or update the JSON state used by the daily standup workflow."""

from __future__ import annotations

import json
from typing import Any

from standup_common import (
    detect_missing_details,
    load_config,
    load_json,
    load_or_create_state,
    merge_transcript_snippets,
    normalize_task,
    normalize_update,
    parse_args,
    resolve_payload_path,
    score_match,
    resolve_workday,
    write_json,
)


def merge_morning(state: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    tasks = payload.get("tasks", [])
    transcript = payload.get("transcript_snippets", [])
    state["morning_tasks"] = [normalize_task(task, "morning", index) for index, task in enumerate(tasks)]
    state["transcript_snippets"] = merge_transcript_snippets(state["transcript_snippets"], "morning", transcript)
    state["status"] = "morning_captured" if state["morning_tasks"] else "morning_pending"
    return state


def build_mappings(state: dict[str, Any]) -> list[dict[str, Any]]:
    mappings: list[dict[str, Any]] = []
    used_morning_ids: set[str] = set()
    for update in state["afternoon_updates"]:
        best_task = None
        best_score = 0
        for task in state["morning_tasks"]:
            if task["id"] in used_morning_ids:
                continue
            candidate_score = score_match(task["title"], update["title"])
            if candidate_score > best_score:
                best_score = candidate_score
                best_task = task
        if best_task and best_score > 0:
            mappings.append(
                {
                    "morning_task_id": best_task["id"],
                    "update_id": update["id"],
                    "match_type": "matched",
                }
            )
            used_morning_ids.add(best_task["id"])
        else:
            mappings.append(
                {
                    "morning_task_id": None,
                    "update_id": update["id"],
                    "match_type": "unplanned",
                }
            )
    return mappings


def merge_afternoon(state: dict[str, Any], payload: dict[str, Any], config: Any) -> dict[str, Any]:
    updates = payload.get("updates", [])
    next_tasks = payload.get("next_workday_tasks", [])
    transcript = payload.get("transcript_snippets", [])
    state["afternoon_updates"] = [
        normalize_update(update, "afternoon", index, config) for index, update in enumerate(updates)
    ]
    state["task_mappings"] = build_mappings(state)
    state["next_workday_tasks"] = [normalize_task(task, "next", index) for index, task in enumerate(next_tasks)]
    state["transcript_snippets"] = merge_transcript_snippets(
        state["transcript_snippets"], "afternoon", transcript
    )
    missing = detect_missing_details(state, config)
    state["status"] = "report_ready" if not missing else "afternoon_in_progress"
    return state


def main() -> None:
    parser = parse_args("Create or update daily standup JSON state.")
    parser.add_argument(
        "--stage",
        required=True,
        choices=["morning", "afternoon"],
        help="Which part of the standup workflow is being updated.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    workday = resolve_workday(config, args.workday)
    state, state_file = load_or_create_state(config, workday)
    payload = load_json(resolve_payload_path(config, args.payload_file))

    if args.stage == "morning":
        state = merge_morning(state, payload)
    else:
        state = merge_afternoon(state, payload, config)

    write_json(state_file, state)
    print(json.dumps({"state_file": str(state_file), "status": state["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
