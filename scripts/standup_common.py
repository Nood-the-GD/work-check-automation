#!/usr/bin/env python3
"""Shared helpers for the daily standup automation scripts."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


WORKDAY_STATUSES = {
    "morning_pending",
    "morning_captured",
    "afternoon_in_progress",
    "report_ready",
    "closed",
}


@dataclass
class Config:
    root_dir: Path
    timezone: str
    morning_time: str
    afternoon_time: str
    workdays: list[str]
    state_dir: Path
    default_blocker: str
    default_time_spent: str


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def load_config(config_path: str | None = None) -> Config:
    root_dir = Path(config_path).resolve().parent if config_path else Path(__file__).resolve().parent.parent
    resolved_path = Path(config_path).resolve() if config_path else root_dir / "standup.config.json"
    raw = load_json(resolved_path)
    return Config(
        root_dir=root_dir,
        timezone=raw["timezone"],
        morning_time=raw["morning_time"],
        afternoon_time=raw["afternoon_time"],
        workdays=list(raw["workdays"]),
        state_dir=(root_dir / raw["state_dir"]).resolve(),
        default_blocker=raw.get("default_blocker", "None"),
        default_time_spent=raw.get("default_time_spent", "Not specified"),
    )


def resolve_payload_path(config: Config, payload_file: str) -> Path:
    path = Path(payload_file)
    if path.is_absolute():
        return path
    return (config.root_dir / path).resolve()


def parse_args(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--config", help="Path to standup.config.json")
    parser.add_argument("--workday", help="Workday in YYYY-MM-DD. Defaults to today.")
    parser.add_argument(
        "--payload-file",
        required=True,
        help="JSON file containing extracted morning or afternoon data.",
    )
    return parser


def resolve_workday(config: Config, explicit_workday: str | None) -> str:
    if explicit_workday:
        return explicit_workday
    return date.today().isoformat()


def state_path(config: Config, workday: str) -> Path:
    return config.state_dir / f"{workday}.json"


def slugify(text: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return value or "task"


def stable_task_id(prefix: str, title: str, index: int) -> str:
    return f"{prefix}-{index + 1}-{slugify(title)[:40]}"


def default_state(config: Config, workday: str) -> dict[str, Any]:
    return {
        "workday": workday,
        "timezone": config.timezone,
        "status": "morning_pending",
        "schedule": {
            "morning_time": config.morning_time,
            "afternoon_time": config.afternoon_time,
            "workdays": config.workdays,
        },
        "morning_tasks": [],
        "afternoon_updates": [],
        "task_mappings": [],
        "next_workday_tasks": [],
        "transcript_snippets": [],
        "final_report": None,
    }


def load_or_create_state(config: Config, workday: str) -> tuple[dict[str, Any], Path]:
    path = state_path(config, workday)
    if path.exists():
        return load_json(path), path
    return default_state(config, workday), path


def normalize_task(task: dict[str, Any], prefix: str, index: int) -> dict[str, str]:
    title = task["title"].strip()
    normalized = {
        "id": task.get("id") or stable_task_id(prefix, title, index),
        "title": title,
    }
    notes = task.get("notes", "").strip()
    if notes:
        normalized["notes"] = notes
    return normalized


def normalize_update(update: dict[str, Any], prefix: str, index: int, config: Config) -> dict[str, str]:
    title = update["title"].strip()
    normalized = {
        "id": update.get("id") or stable_task_id(prefix, title, index),
        "title": title,
        "progress": update.get("progress", "").strip() or "Progress not specified",
        "blocker": update.get("blocker", "").strip() or config.default_blocker,
        "time_spent": update.get("time_spent", "").strip() or config.default_time_spent,
    }
    notes = update.get("notes", "").strip()
    if notes:
        normalized["notes"] = notes
    return normalized


def merge_transcript_snippets(
    existing: list[dict[str, str]], stage: str, transcript: list[dict[str, Any]]
) -> list[dict[str, str]]:
    merged = [item for item in existing if item.get("stage") != stage]
    for item in transcript:
        message = item.get("message", "").strip()
        if message:
            merged.append({"stage": stage, "message": message})
    return merged


def normalized_words(text: str) -> set[str]:
    return {word for word in re.findall(r"[a-z0-9]+", text.lower()) if len(word) > 2}


def score_match(task_title: str, update_title: str) -> int:
    task_words = normalized_words(task_title)
    update_words = normalized_words(update_title)
    if not task_words or not update_words:
        return 0
    overlap = task_words & update_words
    return len(overlap)


def detect_missing_details(state: dict[str, Any], config: Config) -> list[str]:
    missing: list[str] = []
    if not state["morning_tasks"] and not state["afternoon_updates"]:
        missing.append("morning_tasks")
    if not state["next_workday_tasks"]:
        missing.append("next_workday_tasks")
    for update in state["afternoon_updates"]:
        if update["progress"] == "Progress not specified":
            missing.append(f"progress:{update['title']}")
    return missing
