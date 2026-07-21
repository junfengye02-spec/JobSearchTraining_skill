#!/usr/bin/env python3
"""Initialize and inspect an Adaptive Interview Coach workspace."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import jobs  # noqa: E402
import weaknesses  # noqa: E402


RUNTIME_DIR = ".adaptive-interview-coach"
DEFAULT_RESUME_PATTERNS = [
    "**/*简历*.pdf",
    "**/*简历*.docx",
    "**/*简历*.doc",
    "**/*简历*.md",
    "**/*resume*.pdf",
    "**/*resume*.docx",
    "**/*resume*.md",
    "**/*cv*.pdf",
    "**/*cv*.docx",
]


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def config_path(workspace: Path) -> Path:
    return workspace / RUNTIME_DIR / "config.json"


def build_config(args: argparse.Namespace) -> dict:
    roles = list(dict.fromkeys(args.role or []))
    locations = list(dict.fromkeys(args.location or []))
    company_types = list(dict.fromkeys(args.company_type or []))
    positive = list(dict.fromkeys(args.positive_keyword or []))
    fuzzy = list(dict.fromkeys(args.fuzzy_keyword or []))
    negative = list(dict.fromkeys(args.negative_keyword or []))

    return {
        "schema_version": 1,
        "onboarded": True,
        "created_at": datetime.now().astimezone().isoformat(),
        "profile": {
            "target_grad_year": args.grad_year,
            "target_season_label": args.season,
            "roles": roles,
            "include_internships": args.include_internships,
            "location_preferences": locations,
            "company_type_preferences": company_types,
        },
        "filters": {
            "positive_keywords": positive,
            "fuzzy_keywords": fuzzy,
            "negative_keywords": negative,
        },
        "schedule": {
            "job_refresh_time": args.job_time,
            "interview_time": args.interview_time,
            "timezone": args.timezone,
            "thread_span_days": max(1, args.thread_days),
        },
        "files": {
            "resume_patterns": DEFAULT_RESUME_PATTERNS,
            "job_workbook": "岗位总表.xlsx",
            "weakness_workbook": "面试薄弱点复习表.xlsx",
            "job_state": f"{RUNTIME_DIR}/state/jobs.json",
            "pending_weakness_updates": f"{RUNTIME_DIR}/state/pending-weakness-updates.json",
        },
        "job_schema_version": 1,
        "weakness_schema_version": 1,
    }


def cmd_init(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    path = config_path(workspace)
    if path.exists() and not args.force:
        raise SystemExit(f"Configuration already exists: {path}. Use --force only when replacement is intended.")

    config = build_config(args)
    write_json(path, config)
    state_path = workspace / config["files"]["job_state"]
    if not state_path.exists() or args.force:
        write_json(
            state_path,
            {
                "schema_version": 1,
                "updated_at": None,
                "jobs": {},
                "duty_profile": {
                    "generated_at": None,
                    "source_job_count": 0,
                    "new_job_ids": [],
                    "clusters": [],
                },
            },
        )

    job_book = jobs.export_workbook(workspace) if args.force else jobs.ensure_workbook(workspace)
    weakness_book = weaknesses.ensure_workbook(workspace)
    result = {
        "workspace": str(workspace),
        "config": str(path),
        "job_workbook": str(job_book),
        "weakness_workbook": str(weakness_book),
        "job_state": str(state_path),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def latest_resume(workspace: Path, config: dict) -> Path | None:
    runtime = workspace / RUNTIME_DIR
    matches: list[Path] = []
    for pattern in config.get("files", {}).get("resume_patterns", DEFAULT_RESUME_PATTERNS):
        for item in workspace.glob(pattern):
            if item.is_file() and runtime not in item.parents:
                matches.append(item)
    unique = {p.resolve(): p for p in matches}
    if not unique:
        return None
    return max(unique.values(), key=lambda p: p.stat().st_mtime)


def cmd_status(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    path = config_path(workspace)
    if not path.exists():
        raise SystemExit(f"Workspace is not initialized: {path}")
    config = json.loads(path.read_text(encoding="utf-8"))
    resume = latest_resume(workspace, config)
    summary = jobs.state_summary(workspace)
    result = {
        "workspace": str(workspace),
        "onboarded": bool(config.get("onboarded")),
        "latest_resume": str(resume) if resume else None,
        "roles": config.get("profile", {}).get("roles", []),
        "schedule": config.get("schedule", {}),
        "jobs": summary,
        "job_workbook": str(workspace / config["files"]["job_workbook"]),
        "weakness_workbook": str(workspace / config["files"]["weakness_workbook"]),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create runtime configuration, state, and Excel workbooks")
    init.add_argument("--workspace", required=True)
    init.add_argument("--grad-year", default="")
    init.add_argument("--season", default="")
    init.add_argument("--role", action="append", default=[])
    init.add_argument("--location", action="append", default=[])
    init.add_argument("--company-type", action="append", default=[])
    init.add_argument("--positive-keyword", action="append", default=[])
    init.add_argument("--fuzzy-keyword", action="append", default=[])
    init.add_argument("--negative-keyword", action="append", default=[])
    init.add_argument("--include-internships", action="store_true")
    init.add_argument("--job-time", default="08:00")
    init.add_argument("--interview-time", default="09:00")
    init.add_argument("--timezone", default="Asia/Shanghai")
    init.add_argument("--thread-days", type=int, default=7)
    init.add_argument("--force", action="store_true")
    init.set_defaults(func=cmd_init)

    status = sub.add_parser("status", help="Show initialized inputs and generated artifacts")
    status.add_argument("--workspace", required=True)
    status.set_defaults(func=cmd_status)
    return ap


def main() -> int:
    args = parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
