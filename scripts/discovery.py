#!/usr/bin/env python3
"""Plan, validate, and report multi-source job discovery runs."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode


RUNTIME_DIR = ".adaptive-interview-coach"
SOURCE_GROUPS = (
    {
        "id": "nowcoder",
        "label": "牛客求职与校招",
        "domains": ["nowcoder.com/jobs", "nowcoder.com/discuss"],
        "priority": 1,
    },
    {
        "id": "official",
        "label": "企业招聘公众号与官方招聘网站",
        "domains": ["mp.weixin.qq.com", "企业官方招聘域名", "招聘系统详情页"],
        "priority": 1,
    },
    {
        "id": "campus_platforms",
        "label": "51job校园、智联校园与猎聘校园",
        "domains": ["campus.51job.com", "xiaoyuan.zhaopin.com", "campus.liepin.com"],
        "priority": 2,
    },
    {
        "id": "roundups_and_internships",
        "label": "校招名单与实习僧",
        "domains": ["shixiseng.com", "公开校招名单", "公开招聘时间表"],
        "priority": 3,
    },
)
VALID_STATUSES = {"success", "empty", "blocked", "error"}
READY_FIELDS = ("company", "title", "responsibilities", "source_url")


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def read_json(path: Path, default: object) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def load_config(workspace: Path) -> dict:
    path = workspace / RUNTIME_DIR / "config.json"
    if not path.exists():
        raise SystemExit(f"Workspace is not initialized: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def text(value: object) -> str:
    if isinstance(value, list):
        return " / ".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def text_list(value: object) -> list[str]:
    if isinstance(value, list):
        return list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))
    item = str(value or "").strip()
    return [item] if item else []


def query_plan(config: dict) -> dict:
    profile = config.get("profile", {})
    grad = text(profile.get("target_grad_year"))
    season = text(profile.get("target_season_label"))
    roles = text_list(profile.get("roles")) or ["目标岗位方向"]
    include_internships = bool(profile.get("include_internships"))
    cohort_query = grad or "应届 校招"
    season_query = season or "校园招聘"
    internship_query = "实习 可转正" if include_internships else "正式校招 全职"
    queries = {group["id"]: [] for group in SOURCE_GROUPS}
    entry_urls = {group["id"]: [] for group in SOURCE_GROUPS}
    for role in roles:
        common = f'"{cohort_query}" "{role}" {internship_query}'
        queries["nowcoder"].extend([
            f"site:nowcoder.com/jobs {common}",
            f"site:nowcoder.com/discuss {season_query} {common}",
        ])
        entry_urls["nowcoder"].append(
            "https://www.nowcoder.com/search/all?"
            + urlencode({"query": f"{cohort_query} {role} 校招", "type": "all"})
        )
        queries["official"].extend([
            f'"校园招聘" "{cohort_query}" "{role}" 招聘官网',
            f'"{season_query}" "正式启动" "{role}" 招聘',
            f'site:mp.weixin.qq.com "{season_query}" "{role}" 招聘',
        ])
        queries["campus_platforms"].extend([
            f"site:campus.51job.com {common}",
            f"site:xiaoyuan.zhaopin.com {common}",
            f"site:campus.liepin.com {common}",
        ])
        queries["roundups_and_internships"].extend([
            f'"{season_query}" 名企名单 "{role}"',
            f'"校招进行时" "{role}" "{cohort_query}"',
            f"site:shixiseng.com {common}",
        ])
    entry_urls["campus_platforms"] = [
        "https://campus.51job.com/",
        "https://xiaoyuan.zhaopin.com/",
        "https://campus.liepin.com/",
    ]
    entry_urls["roundups_and_internships"] = ["https://www.shixiseng.com/interns"]
    discovery = config.get("discovery", {})
    max_companies = int(discovery.get("max_companies_per_source", 15))
    tasks = []
    for group in SOURCE_GROUPS:
        tasks.append({
            **group,
            "queries": queries[group["id"]],
            "entry_urls": entry_urls[group["id"]],
            "max_companies": max_companies,
            "instruction": (
                "使用当前可用的网页搜索、WebFetch或浏览器工具直接完成本来源调研；"
                "有站内入口时优先打开entry_urls，不得把任务继续委托给下一层代理。"
                "先发现岗位，再打开详情页获取职责。"
                "返回来源状态、实际查询、访问页面和结构化候选岗位；单个来源最多深入核实"
                f"{max_companies}家最相关企业。"
            ),
        })
    return {
        "schema_version": 1,
        "run_id": datetime.now().astimezone().strftime("DISC-%Y%m%d-%H%M%S"),
        "created_at": now_iso(),
        "profile": {
            "target_grad_year": grad,
            "target_season_label": season,
            "roles": roles,
            "include_internships": include_internships,
            "location_preferences": profile.get("location_preferences", []),
            "company_type_preferences": profile.get("company_type_preferences", []),
        },
        "source_groups": tasks,
        "candidate_fields": [
            "company", "title", "responsibilities", "city", "job_type", "enterprise_tag",
            "direction_tags", "highlight", "verification", "source_platform", "source_url",
            "deadline", "grad_year", "season",
        ],
        "source_result_schema": {
            "id": "source group id",
            "status": "success | empty | blocked | error",
            "queries": ["actual queries used"],
            "pages_checked": ["URLs actually opened"],
            "error": "required for blocked/error",
            "candidates": ["candidate objects"],
        },
    }


def cmd_plan(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    plan = query_plan(load_config(workspace))
    if args.output:
        write_json(Path(args.output).expanduser().resolve(), plan)
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


def candidate_key(candidate: dict) -> str:
    company = re.sub(r"\s+", "", text(candidate.get("company")).lower())
    title = re.sub(r"\s+", "", text(candidate.get("title")).lower())
    url = text(candidate.get("source_url")).rstrip("/")
    return f"{company}|{title}|{url}"


def normalize_source_results(report: dict) -> tuple[list[dict], list[dict]]:
    supplied = report.get("sources", []) if isinstance(report, dict) else []
    by_id = {
        text(item.get("id")): item
        for item in supplied
        if isinstance(item, dict) and text(item.get("id"))
    }
    normalized = []
    candidates = []
    for group in SOURCE_GROUPS:
        raw = by_id.get(group["id"], {})
        status = text(raw.get("status")) or "not_run"
        queries = raw.get("queries", []) if isinstance(raw.get("queries", []), list) else []
        pages_checked = raw.get("pages_checked", []) if isinstance(raw.get("pages_checked", []), list) else []
        error = text(raw.get("error"))
        if status not in VALID_STATUSES:
            status = "error"
            error = "Invalid or missing source status"
        elif status in ("success", "empty") and (not queries or not pages_checked):
            status = "error"
            error = "Completed source lacks actual query or visited-page evidence"
        elif status in ("blocked", "error") and not error:
            error = "Source did not provide a failure reason"
        source_candidates = raw.get("candidates", [])
        if not isinstance(source_candidates, list):
            source_candidates = []
        for candidate in source_candidates:
            if not isinstance(candidate, dict):
                continue
            item = candidate.copy()
            item.setdefault("source_group", group["id"])
            item.setdefault("source_platform", group["label"])
            candidates.append(item)
        normalized.append({
            "id": group["id"],
            "label": group["label"],
            "status": status,
            "queries": queries,
            "pages_checked": pages_checked,
            "error": error,
            "candidate_count": len(source_candidates),
        })
    return normalized, candidates


def dedupe_candidates(candidates: list[dict]) -> list[dict]:
    found: dict[str, dict] = {}
    for item in candidates:
        key = candidate_key(item)
        if key == "||":
            continue
        previous = found.get(key)
        if not previous or len(text(item.get("responsibilities"))) > len(text(previous.get("responsibilities"))):
            found[key] = item
    return list(found.values())


def discovery_history_path(workspace: Path, config: dict) -> Path:
    value = config.get("files", {}).get("discovery_history", f"{RUNTIME_DIR}/state/discovery-runs.json")
    path = Path(value)
    return path if path.is_absolute() else workspace / path


def record_run(workspace: Path, config: dict, status: dict) -> None:
    path = discovery_history_path(workspace, config)
    history = read_json(path, {"schema_version": 1, "runs": []})
    if not isinstance(history, dict):
        history = {"schema_version": 1, "runs": []}
    runs = history.setdefault("runs", [])
    runs.append(status)
    retention = int(config.get("discovery", {}).get("history_retention_runs", 30))
    history["runs"] = runs[-max(1, retention):]
    write_json(path, history)


def finalize_report(workspace: Path, report: dict) -> tuple[dict, list[dict], list[dict]]:
    config = load_config(workspace)
    sources, candidates = normalize_source_results(report)
    candidates = dedupe_candidates(candidates)
    ready = [item for item in candidates if all(text(item.get(field)) for field in READY_FIELDS)]
    leads = [item for item in candidates if item not in ready]
    successful = [source for source in sources if source["status"] in ("success", "empty")]
    blocked = [source for source in sources if source["status"] in ("blocked", "error", "not_run")]
    minimum = int(config.get("discovery", {}).get("min_successful_sources_for_empty", 3))
    can_report_no_jobs = not candidates and len(successful) >= minimum
    if candidates:
        conclusion = "jobs_found"
    elif can_report_no_jobs:
        conclusion = "searched_no_jobs"
    elif successful:
        conclusion = "partial_inconclusive"
    else:
        conclusion = "blocked"
    status = {
        "schema_version": 1,
        "run_id": text(report.get("run_id")) or datetime.now().astimezone().strftime("DISC-%Y%m%d-%H%M%S"),
        "finished_at": now_iso(),
        "conclusion": conclusion,
        "can_report_no_jobs": can_report_no_jobs,
        "successful_source_count": len(successful),
        "required_successful_sources_for_empty": minimum,
        "candidate_count": len(candidates),
        "ready_candidate_count": len(ready),
        "lead_count": len(leads),
        "sources": sources,
        "blocked_sources": [source["id"] for source in blocked],
    }
    record_run(workspace, config, status)
    return status, ready, leads


def cmd_finalize(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    report = read_json(Path(args.input).expanduser().resolve(), {})
    status, ready, leads = finalize_report(workspace, report if isinstance(report, dict) else {})
    write_json(Path(args.candidates_output).expanduser().resolve(), ready)
    if args.leads_output:
        write_json(Path(args.leads_output).expanduser().resolve(), leads)
    if args.status_output:
        write_json(Path(args.status_output).expanduser().resolve(), status)
    print(json.dumps(status, ensure_ascii=False, indent=2))
    return 0 if status["conclusion"] in ("jobs_found", "searched_no_jobs") else 2


def latest_run(workspace: Path, config: dict) -> dict | None:
    history = read_json(discovery_history_path(workspace, config), {"runs": []})
    runs = history.get("runs", []) if isinstance(history, dict) else []
    return runs[-1] if runs else None


def cmd_status(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    config = load_config(workspace)
    run = latest_run(workspace, config)
    print(json.dumps({"latest_discovery": run}, ensure_ascii=False, indent=2))
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    config = load_config(workspace)
    run = latest_run(workspace, config)
    if not run:
        print("岗位发现尚未执行，不能判断是否存在新岗位。")
        return 2
    print(f"# 岗位发现日报 · {run.get('finished_at', '')[:10]}")
    print()
    if run.get("conclusion") == "blocked":
        print("岗位发现被阻塞：所有来源均未成功执行，不能报告‘没有岗位’。")
    elif run.get("conclusion") == "partial_inconclusive":
        print("岗位发现仅部分完成，结果不完整，不能报告‘没有岗位’。")
    elif run.get("conclusion") == "searched_no_jobs":
        print("已完成足够来源的实际搜索，本轮未发现候选岗位。")
    else:
        print(f"本轮发现 {run.get('candidate_count', 0)} 条线索，其中 {run.get('ready_candidate_count', 0)} 条职责完整。")
    print()
    print("## 来源状态")
    for source in run.get("sources", []):
        detail = source.get("error") or f"候选 {source.get('candidate_count', 0)} 条"
        print(f"- {source.get('label', source.get('id'))}: {source.get('status')}，{detail}")
    return 0 if run.get("conclusion") in ("jobs_found", "searched_no_jobs") else 2


def parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="command", required=True)
    plan = sub.add_parser("plan", help="Generate the four-source discovery plan from workspace config")
    plan.add_argument("--workspace", required=True)
    plan.add_argument("--output")
    plan.set_defaults(func=cmd_plan)
    finalize = sub.add_parser("finalize", help="Validate source coverage and emit ready candidates")
    finalize.add_argument("--workspace", required=True)
    finalize.add_argument("--input", required=True)
    finalize.add_argument("--candidates-output", required=True)
    finalize.add_argument("--leads-output")
    finalize.add_argument("--status-output")
    finalize.set_defaults(func=cmd_finalize)
    status = sub.add_parser("status", help="Show the latest discovery run")
    status.add_argument("--workspace", required=True)
    status.set_defaults(func=cmd_status)
    report = sub.add_parser("report", help="Render a coverage-aware discovery report")
    report.add_argument("--workspace", required=True)
    report.set_defaults(func=cmd_report)
    return ap


def main() -> int:
    args = parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
