#!/usr/bin/env python3
"""Render a daily standup report from the JSON state file."""

from __future__ import annotations

import argparse
import json

from standup_common import load_config, load_json, state_path, write_json


def format_yesterday_line(
    title: str,
    status: str,
    blocker: str | None,
    time_spent: str | None,
    default_blocker: str,
    default_time_spent: str,
) -> str:
    parts = [title, f"`[{status}]`"]
    normalized_blocker = (blocker or "").strip()
    normalized_time = (time_spent or "").strip()

    if normalized_blocker and normalized_blocker != default_blocker:
        parts.append(f"`[{normalized_blocker}]`")
    if normalized_time and normalized_time != default_time_spent:
        parts.append(f"`[{normalized_time}]`")

    return "- " + " - ".join(parts)


def render_report(state: dict[str, object], default_blocker: str, default_time_spent: str) -> str:
    mappings = {
        mapping["update_id"]: mapping.get("morning_task_id")
        for mapping in state.get("task_mappings", [])
    }
    morning_tasks = {task["id"]: task for task in state.get("morning_tasks", [])}
    yesterday_lines: list[str] = []

    for update in state.get("afternoon_updates", []):
        morning_task_id = mappings.get(update["id"])
        if morning_task_id and morning_task_id in morning_tasks:
            title = morning_tasks[morning_task_id]["title"]
        elif mappings.get(update["id"]) is None:
            title = f"{update['title']} (unplanned)"
        else:
            title = update["title"]
        yesterday_lines.append(
            format_yesterday_line(
                title=title,
                status=update.get("progress", "Progress not specified"),
                blocker=update.get("blocker"),
                time_spent=update.get("time_spent"),
                default_blocker=default_blocker,
                default_time_spent=default_time_spent,
            )
        )

    if not yesterday_lines:
        yesterday_lines.append("- No updates captured - `[Progress not specified]`")

    today_lines = [
        f"- {task['title']}" for task in state.get("next_workday_tasks", [])
    ] or ["- No tasks planned yet"]

    return "`Yesterday:`\n" + "\n".join(yesterday_lines) + "\n`Today:`\n" + "\n".join(today_lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Render a standup report from state JSON.")
    parser.add_argument("--config", help="Path to standup.config.json")
    parser.add_argument("--workday", required=True, help="Workday in YYYY-MM-DD")
    parser.add_argument(
        "--write-back",
        action="store_true",
        help="Persist the rendered report into the state file.",
    )
    args = parser.parse_args()

    config = load_config(args.config)
    path = state_path(config, args.workday)
    state = load_json(path)
    report = render_report(state, config.default_blocker, config.default_time_spent)

    if args.write_back:
        state["final_report"] = report
        if state["status"] == "report_ready":
            state["status"] = "closed"
        write_json(path, state)

    print(report)
    print(json.dumps({"state_file": str(path), "status": state["status"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
