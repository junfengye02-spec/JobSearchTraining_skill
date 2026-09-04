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
from configuration import upgrade_config  # noqa: E402


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


def read_json(path: Path, default: object) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def config_path(workspace: Path) -> Path:
    return workspace / RUNTIME_DIR / "config.json"


def parse_role_aliases(values: list[str], roles: list[str]) -> dict[str, list[str]]:
    result = {role: [] for role in roles}
    role_lookup = {role.strip().lower(): role for role in roles}
    for value in values:
        if "=" not in value:
            raise SystemExit(f"Role alias must use ROLE=ALIAS format: {value}")
        supplied_role, alias = (part.strip() for part in value.split("=", 1))
        role = role_lookup.get(supplied_role.lower())
        if not role or not alias:
            raise SystemExit(f"Role alias references an unknown or empty role: {value}")
        if alias != role and alias not in result[role]:
            result[role].append(alias)
    return result


def build_config(args: argparse.Namespace) -> dict:
    roles = list(dict.fromkeys(args.role or []))
    locations = list(dict.fromkeys(args.location or []))
    company_types = list(dict.fromkeys(args.company_type or []))
    positive = list(dict.fromkeys(args.positive_keyword or []))
    fuzzy = list(dict.fromkeys(args.fuzzy_keyword or []))
    negative = list(dict.fromkeys(args.negative_keyword or []))
    watch_companies = list(dict.fromkeys(args.watch_company or []))
    aliases = parse_role_aliases(args.role_alias or [], roles)

    return {
        "schema_version": 2,
        "onboarded": True,
        "created_at": datetime.now().astimezone().isoformat(),
        "profile": {
            "target_grad_year": args.grad_year,
            "target_season_label": args.season,
            "roles": roles,
            "role_aliases": aliases,
            "include_internships": args.include_internships,
            "location_preferences": locations,
            "company_type_preferences": company_types,
            "watch_companies": watch_companies,
            "include_high_growth_companies": bool(args.include_high_growth_companies),
        },
        "filters": {
            "positive_keywords": positive,
            "fuzzy_keywords": fuzzy,
            "negative_keywords": negative,
            "intern_exclusion_keywords": [
                "实习生", "实习", "暑期实习", "日常实习", "寒假实习", "提前批实习", "intern",
            ],
            "formal_recruit_keywords": [
                "校园招聘", "校招", "管培生", "应届生", "全职", "正式员工",
            ],
        },
        "schedule": {
            "job_refresh_time": args.job_time,
            "interview_time": args.interview_time,
            "timezone": args.timezone,
            "thread_span_days": max(1, args.thread_days),
        },
        "discovery": {
            "max_role_aliases": 8,
            "initial_max_candidates_per_source": 120,
            "daily_max_candidates_per_source": 40,
            "initial_max_result_pages_per_query": 8,
            "daily_max_result_pages_per_query": 3,
            "stop_after_consecutive_no_new_pages": 2,
            "initial_max_new_company_verifications": 120,
            "daily_max_new_company_verifications": 20,
            "initial_low_yield_threshold": 20,
            "audit_all_nowcoder_companies": True,
            "require_official_company_search": True,
            "retry_pending_leads": True,
            "retry_pending_company_audits": True,
            "history_retention_runs": 30,
        },
        "files": {
            "resume_patterns": DEFAULT_RESUME_PATTERNS,
            "job_workbook": "岗位总表.xlsx",
            "weakness_workbook": "面试薄弱点复习表.xlsx",
            "job_state": f"{RUNTIME_DIR}/state/jobs.json",
            "discovery_history": f"{RUNTIME_DIR}/state/discovery-runs.json",
            "pending_job_leads": f"{RUNTIME_DIR}/state/pending-job-leads.json",
            "company_audit": f"{RUNTIME_DIR}/state/company-audit.json",
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
    discovery_path = workspace / config["files"]["discovery_history"]
    if not discovery_path.exists() or args.force:
        write_json(discovery_path, {"schema_version": 2, "runs": []})
    pending_leads_path = workspace / config["files"]["pending_job_leads"]
    if not pending_leads_path.exists() or args.force:
        write_json(
            pending_leads_path,
            {"schema_version": 2, "updated_at": None, "leads": [], "resolved": []},
        )
    company_audit_path = workspace / config["files"]["company_audit"]
    if not company_audit_path.exists() or args.force:
        write_json(company_audit_path, {"schema_version": 1, "updated_at": None, "companies": {}})

    job_book = jobs.export_workbook(workspace) if args.force else jobs.ensure_workbook(workspace)
    weakness_book = weaknesses.ensure_workbook(workspace)
    result = {
        "workspace": str(workspace),
        "config": str(path),
        "job_workbook": str(job_book),
        "weakness_workbook": str(weakness_book),
        "job_state": str(state_path),
        "discovery_history": str(discovery_path),
        "pending_job_leads": str(pending_leads_path),
        "company_audit": str(company_audit_path),
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
    config = upgrade_config(json.loads(path.read_text(encoding="utf-8")))
    resume = latest_resume(workspace, config)
    summary = jobs.state_summary(workspace)
    history_path = workspace / config["files"].get("discovery_history", f"{RUNTIME_DIR}/state/discovery-runs.json")
    try:
        history = json.loads(history_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        history = {"runs": []}
    runs = history.get("runs", []) if isinstance(history, dict) else []
    pending_path = workspace / config["files"].get("pending_job_leads", f"{RUNTIME_DIR}/state/pending-job-leads.json")
    audit_path = workspace / config["files"].get("company_audit", f"{RUNTIME_DIR}/state/company-audit.json")
    pending = read_json(pending_path, {"leads": []})
    audits = read_json(audit_path, {"companies": {}})
    result = {
        "workspace": str(workspace),
        "onboarded": bool(config.get("onboarded")),
        "latest_resume": str(resume) if resume else None,
        "roles": config.get("profile", {}).get("roles", []),
        "role_aliases": config.get("profile", {}).get("role_aliases", {}),
        "watch_companies": config.get("profile", {}).get("watch_companies", []),
        "schedule": config.get("schedule", {}),
        "jobs": summary,
        "pending_job_lead_count": len(pending.get("leads", [])) if isinstance(pending, dict) else 0,
        "pending_company_audit_count": sum(
            1 for value in audits.get("companies", {}).values()
            if isinstance(value, dict) and value.get("complete") is not True
        ) if isinstance(audits, dict) and isinstance(audits.get("companies", {}), dict) else 0,
        "latest_discovery": runs[-1] if runs else None,
        "job_workbook": str(workspace / config["files"]["job_workbook"]),
        "weakness_workbook": str(workspace / config["files"]["weakness_workbook"]),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_migrate(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    path = config_path(workspace)
    if not path.exists():
        raise SystemExit(f"Workspace is not initialized: {path}")
    original = json.loads(path.read_text(encoding="utf-8"))
    config = upgrade_config(original)
    if config != original:
        write_json(path, config)

    pending_path = workspace / config["files"]["pending_job_leads"]
    if not pending_path.exists():
        write_json(
            pending_path,
            {"schema_version": 2, "updated_at": None, "leads": [], "resolved": []},
        )
    audit_path = workspace / config["files"]["company_audit"]
    if not audit_path.exists():
        write_json(audit_path, {"schema_version": 1, "updated_at": None, "companies": {}})
    history_path = workspace / config["files"].get(
        "discovery_history", f"{RUNTIME_DIR}/state/discovery-runs.json"
    )
    if not history_path.exists():
        write_json(history_path, {"schema_version": 2, "runs": []})

    result = {
        "workspace": str(workspace),
        "config": str(path),
        "changed": config != original,
        "schema_version": config["schema_version"],
        "pending_job_leads": str(pending_path),
        "company_audit": str(audit_path),
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


def cmd_set_role_aliases(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    path = config_path(workspace)
    if not path.exists():
        raise SystemExit(f"Workspace is not initialized: {path}")
    config = upgrade_config(json.loads(path.read_text(encoding="utf-8")))
    profile = config.setdefault("profile", {})
    roles = profile.get("roles", [])
    updates = parse_role_aliases(args.role_alias or [], roles)
    aliases = {} if args.replace else profile.get("role_aliases", {})
    if not isinstance(aliases, dict):
        aliases = {}
    for role in roles:
        existing = [] if args.replace else aliases.get(role, [])
        if not isinstance(existing, list):
            existing = [str(existing)] if str(existing).strip() else []
        aliases[role] = list(dict.fromkeys([*existing, *updates.get(role, [])]))
    profile["role_aliases"] = aliases
    write_json(path, config)
    print(json.dumps({"roles": roles, "role_aliases": aliases}, ensure_ascii=False, indent=2))
    return 0


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init", help="Create runtime configuration, state, and Excel workbooks")
    init.add_argument("--workspace", required=True)
    init.add_argument("--grad-year", default="")
    init.add_argument("--season", default="")
    init.add_argument("--role", action="append", default=[])
    init.add_argument("--role-alias", action="append", default=[], help="ROLE=ALIAS; repeat as needed")
    init.add_argument("--location", action="append", default=[])
    init.add_argument("--company-type", action="append", default=[])
    init.add_argument("--watch-company", action="append", default=[], help="Company to audit on every full search")
    init.add_argument("--include-high-growth-companies", action="store_true")
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

    migrate = sub.add_parser("migrate", help="Upgrade an existing runtime config and add missing v2 state")
    migrate.add_argument("--workspace", required=True)
    migrate.set_defaults(func=cmd_migrate)

    aliases = sub.add_parser("set-role-aliases", help="Add or replace job-title aliases for configured roles")
    aliases.add_argument("--workspace", required=True)
    aliases.add_argument("--role-alias", action="append", required=True, help="ROLE=ALIAS; repeat as needed")
    aliases.add_argument("--replace", action="store_true")
    aliases.set_defaults(func=cmd_set_role_aliases)
    return ap


def main() -> int:
    args = parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
