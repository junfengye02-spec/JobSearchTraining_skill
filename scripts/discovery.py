#!/usr/bin/env python3
"""Plan, validate, and report multi-source job discovery runs."""

from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlencode

from configuration import upgrade_config


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
VALID_MODES = {"initial_full", "daily_refresh"}
VALID_COMPLETE_STOP_REASONS = {"end", "consecutive_no_new", "page_limit"}
VALID_AUDIT_STATUSES = {"verified", "no_match", "deferred", "blocked", "error"}
COMPLETE_AUDIT_STATUSES = {"verified", "no_match"}
OPEN_APPLICATION_STATUSES = {"open", "currently_open", "可投递", "招聘中", "开放投递"}
READY_FIELDS = (
    "company", "title", "responsibilities", "source_url", "matched_roles",
    "application_status", "availability_evidence", "checked_at",
)


def now_iso() -> str:
    return datetime.now().astimezone().isoformat()


def valid_iso_timestamp(value: object) -> bool:
    raw = text(value)
    if "T" not in raw:
        return False
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.utcoffset() is not None


def company_audit_is_complete(item: dict) -> bool:
    return (
        item.get("status") in COMPLETE_AUDIT_STATUSES
        and item.get("official_search_attempted") is True
        and bool(text_list(item.get("queries")))
        and bool(text_list(item.get("pages_checked")))
        and valid_iso_timestamp(item.get("checked_at"))
    )


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
    return upgrade_config(json.loads(path.read_text(encoding="utf-8")))


def configured_path(workspace: Path, config: dict, key: str, fallback: str) -> Path:
    value = config.get("files", {}).get(key, fallback)
    path = Path(value)
    return path if path.is_absolute() else workspace / path


def pending_leads_path(workspace: Path, config: dict) -> Path:
    return configured_path(
        workspace, config, "pending_job_leads", f"{RUNTIME_DIR}/state/pending-job-leads.json"
    )


def company_audit_path(workspace: Path, config: dict) -> Path:
    return configured_path(
        workspace, config, "company_audit", f"{RUNTIME_DIR}/state/company-audit.json"
    )


def load_pending_leads(workspace: Path, config: dict) -> list[dict]:
    state = read_json(pending_leads_path(workspace, config), {"leads": []})
    leads = state.get("leads", []) if isinstance(state, dict) else []
    return [item for item in leads if isinstance(item, dict)]


def load_pending_company_audits(workspace: Path, config: dict) -> list[dict]:
    state = read_json(company_audit_path(workspace, config), {"companies": {}})
    companies = state.get("companies", {}) if isinstance(state, dict) else {}
    if not isinstance(companies, dict):
        return []
    return [
        item for item in companies.values()
        if isinstance(item, dict) and not company_audit_is_complete(item)
    ]


def text(value: object) -> str:
    if isinstance(value, list):
        return " / ".join(str(item).strip() for item in value if str(item).strip())
    return str(value or "").strip()


def text_list(value: object) -> list[str]:
    if isinstance(value, list):
        return list(dict.fromkeys(str(item).strip() for item in value if str(item).strip()))
    item = str(value or "").strip()
    return [item] if item else []


def normalize(value: object) -> str:
    return re.sub(r"\s+", " ", text(value)).strip().lower()


def role_aliases(profile: dict, role: str, limit: int = 8) -> list[str]:
    mapping = profile.get("role_aliases", {})
    aliases = mapping.get(role, []) if isinstance(mapping, dict) else []
    unique_aliases = [item for item in text_list(aliases) if normalize(item) != normalize(role)]
    return [role, *unique_aliases[:max(0, limit)]]


def completed_initial_full(workspace: Path, config: dict) -> bool:
    history = read_json(discovery_history_path(workspace, config), {"runs": []})
    runs = history.get("runs", []) if isinstance(history, dict) else []
    return any(
        run.get("schema_version") == 2
        and run.get("mode") == "initial_full"
        and run.get("full_search_complete") is True
        for run in runs
        if isinstance(run, dict)
    )


def resolve_mode(workspace: Path, config: dict, requested: str = "auto") -> str:
    if requested in VALID_MODES:
        return requested
    return "daily_refresh" if completed_initial_full(workspace, config) else "initial_full"


def query_plan(
    config: dict,
    mode: str = "initial_full",
    pending_leads: list[dict] | None = None,
    pending_company_audits: list[dict] | None = None,
) -> dict:
    profile = config.get("profile", {})
    grad = text(profile.get("target_grad_year"))
    season = text(profile.get("target_season_label"))
    roles = text_list(profile.get("roles")) or ["目标岗位方向"]
    include_internships = bool(profile.get("include_internships"))
    cohort_query = grad or "应届 校招"
    season_query = season or "校园招聘"
    internship_query = "实习 可转正" if include_internships else "正式校招 全职"
    discovery = config.get("discovery", {})
    alias_limit = int(discovery.get("max_role_aliases", 8))
    watch_companies = text_list(profile.get("watch_companies"))
    retry_companies = list(dict.fromkeys(
        text(item.get("company"))
        for item in (pending_company_audits or [])
        if isinstance(item, dict) and text(item.get("company"))
    ))
    company_search_companies = list(dict.fromkeys([*watch_companies, *retry_companies]))
    role_tasks = {group["id"]: [] for group in SOURCE_GROUPS}
    for role in roles:
        terms = role_aliases(profile, role, alias_limit)
        expression = " OR ".join(f'"{term}"' for term in terms)
        common = f'"{cohort_query}" ({expression}) {internship_query}'
        role_tasks["nowcoder"].append({
            "role": role,
            "search_terms": terms,
            "queries": [
                f"site:nowcoder.com/jobs {common}",
                f"site:nowcoder.com/discuss {season_query} {common}",
            ],
            "entry_urls": [
                "https://www.nowcoder.com/jobs/school/schedule?pageSource=5001",
                "https://www.nowcoder.com/jobs/recommend/campus",
                *[
                    "https://www.nowcoder.com/jobs/school/jobs?"
                    + urlencode({"search": term})
                    for term in terms
                ],
                *[
                    "https://www.nowcoder.com/search/all?"
                    + urlencode({"query": f"{cohort_query} {term} 校招", "type": "all"})
                    for term in terms
                ],
            ],
        })
        role_tasks["official"].append({
            "role": role,
            "search_terms": terms,
            "queries": [
                f'"校园招聘" "{cohort_query}" ({expression}) 招聘官网',
                f'"{season_query}" "正式启动" ({expression}) 招聘',
                f'site:mp.weixin.qq.com "{season_query}" ({expression}) 招聘',
                *[
                    f'"{company}" ({expression}) (校招 OR 校园招聘 OR 应届生) 招聘官网'
                    for company in company_search_companies
                ],
            ],
            "entry_urls": [],
        })
        role_tasks["campus_platforms"].append({
            "role": role,
            "search_terms": terms,
            "queries": [
                f"site:campus.51job.com {common}",
                f"site:xiaoyuan.zhaopin.com {common}",
                f"site:campus.liepin.com {common}",
            ],
            "entry_urls": [
                "https://campus.51job.com/",
                "https://xiaoyuan.zhaopin.com/",
                "https://campus.liepin.com/",
            ],
        })
        role_tasks["roundups_and_internships"].append({
            "role": role,
            "search_terms": terms,
            "queries": [
                f'"{season_query}" 名企名单 ({expression})',
                f'"校招进行时" ({expression}) "{cohort_query}"',
                f"site:shixiseng.com {common}",
            ],
            "entry_urls": ["https://www.shixiseng.com/interns"],
        })
    if mode == "initial_full":
        max_candidates = int(discovery.get("initial_max_candidates_per_source", 50))
        max_pages = int(discovery.get("initial_max_result_pages_per_query", 5))
        max_verifications = int(discovery.get("initial_max_new_company_verifications", 30))
    else:
        max_candidates = int(discovery.get("daily_max_candidates_per_source", 20))
        max_pages = int(discovery.get("daily_max_result_pages_per_query", 2))
        max_verifications = int(discovery.get("daily_max_new_company_verifications", 5))
    no_new_limit = int(discovery.get("stop_after_consecutive_no_new_pages", 2))
    tasks = []
    for group in SOURCE_GROUPS:
        group_role_tasks = role_tasks[group["id"]]
        queries = [query for task in group_role_tasks for query in task["queries"]]
        entry_urls = list(dict.fromkeys(url for task in group_role_tasks for url in task["entry_urls"]))
        tasks.append({
            **group,
            "role_tasks": group_role_tasks,
            "queries": queries,
            "entry_urls": entry_urls,
            "max_candidates": max_candidates,
            "max_result_pages_per_query": max_pages,
            "stop_after_consecutive_no_new_pages": no_new_limit,
            "max_new_company_verifications": (
                None
                if group["id"] == "nowcoder" and discovery.get("audit_all_nowcoder_companies", True)
                else max_verifications
            ),
            "required_watch_companies": (
                company_search_companies
                if group["id"] == "official" else []
            ),
            "requires_company_enumeration": group["id"] == "nowcoder",
            "instruction": (
                "逐个执行role_tasks，不得遗漏用户指定岗位方向或把多个方向合并成一个完成项。"
                "为每条查询填写独立query_runs证据，并逐一打开entry_urls填写entry_runs；"
                "对有分页的结果继续翻页，直到来源明确结束、"
                f"连续{no_new_limit}页没有新增，或达到每条查询{max_pages}页的安全上限。"
                "先广泛收集，再打开职位详情核实完整职责、当前可投状态、可投证据和核验时间。"
                f"首次最多保留本来源{max_candidates}条相关候选，不得因为找到第一条就停止；"
                "若命中候选上限，使用candidate_limit停止原因并保持exhausted=false。"
                "列出本来源发现的每家公司并执行官方招聘搜索；牛客公司列表必须完整枚举，"
                "无法核验的公司写入company_audits并标记deferred/blocked，不得静默丢弃。"
            ),
        })
    return {
        "schema_version": 2,
        "run_id": datetime.now().astimezone().strftime("DISC-%Y%m%d-%H%M%S"),
        "created_at": now_iso(),
        "mode": mode,
        "profile": {
            "target_grad_year": grad,
            "target_season_label": season,
            "roles": roles,
            "include_internships": include_internships,
            "location_preferences": profile.get("location_preferences", []),
            "company_type_preferences": profile.get("company_type_preferences", []),
            "watch_companies": watch_companies,
            "include_high_growth_companies": bool(profile.get("include_high_growth_companies")),
        },
        "retry_queue": {
            "pending_leads": pending_leads or [],
            "pending_company_audits": pending_company_audits or [],
        },
        "source_groups": tasks,
        "candidate_fields": [
            "company", "title", "responsibilities", "city", "job_type", "enterprise_tag",
            "direction_tags", "highlight", "verification", "source_platform", "source_url",
            "deadline", "grad_year", "season", "matched_roles", "application_status",
            "availability_evidence", "checked_at",
        ],
        "source_result_schema": {
            "id": "source group id",
            "status": "success | empty | blocked | error",
            "role_coverage": [
                {
                    "role": "configured role",
                    "status": "success | empty | blocked | error",
                    "query_runs": [{
                        "query": "one exact planned query",
                        "status": "success | empty | blocked | error",
                        "pages_checked": ["search and result pages actually opened"],
                        "exhausted": "true only after end/no-new-page rule",
                        "stop_reason": "end | consecutive_no_new | page_limit | candidate_limit | blocked | error",
                        "error": "required for blocked/error",
                    }],
                }
            ],
            "entry_runs": [{
                "url": "one exact planned entry URL",
                "status": "success | empty | blocked | error",
                "checked_at": "ISO-8601 timestamp",
                "evidence": "what was visible at this entry point",
                "error": "required for blocked/error",
            }],
            "enumeration_complete": "required true for Nowcoder after all visible companies are listed",
            "enumerated_companies": ["all companies visible on the source"],
            "company_audits": [{
                "company": "company name",
                "status": "verified | no_match | deferred | blocked | error",
                "official_search_attempted": "boolean",
                "queries": ["company-specific official search queries"],
                "pages_checked": ["official pages/search results opened"],
                "checked_at": "ISO-8601 timestamp",
                "error": "required unless verified/no_match",
            }],
            "error": "required for blocked/error",
            "candidates": ["candidate objects"],
        },
        "lead_resolution_schema": [{
            "lead_key": "exact lead_key from retry_queue.pending_leads",
            "resolution": "closed | duplicate | irrelevant",
            "evidence": "current evidence supporting removal from retry",
            "checked_at": "valid timezone-aware ISO-8601 timestamp",
        }],
    }


def cmd_plan(args: argparse.Namespace) -> int:
    workspace = Path(args.workspace).expanduser().resolve()
    config = load_config(workspace)
    plan = query_plan(
        config,
        resolve_mode(workspace, config, args.mode),
        load_pending_leads(workspace, config),
        load_pending_company_audits(workspace, config),
    )
    if args.output:
        write_json(Path(args.output).expanduser().resolve(), plan)
    print(json.dumps(plan, ensure_ascii=False, indent=2))
    return 0


def candidate_key(candidate: dict) -> str:
    company = re.sub(r"\s+", "", text(candidate.get("company")).lower())
    title = re.sub(r"\s+", "", text(candidate.get("title")).lower())
    url = text(candidate.get("source_url")).rstrip("/")
    return f"{company}|{title}|{url}"


def normalize_query_run(
    raw: dict,
    expected_query: str,
    max_pages: int,
    no_new_page_limit: int,
) -> dict:
    status = text(raw.get("status")) or "not_run"
    pages = text_list(raw.get("pages_checked"))
    exhausted = raw.get("exhausted") is True
    stop_reason = text(raw.get("stop_reason"))
    error = text(raw.get("error"))
    stop_evidence_complete = (
        stop_reason == "end"
        or (stop_reason == "page_limit" and len(pages) >= max_pages)
        or (
            stop_reason == "consecutive_no_new"
            and len(pages) >= no_new_page_limit
        )
    )
    complete = (
        status in ("success", "empty")
        and bool(pages)
        and exhausted
        and stop_reason in VALID_COMPLETE_STOP_REASONS
        and stop_evidence_complete
    )
    if not complete and not error:
        reasons = []
        if status not in VALID_STATUSES:
            reasons.append("invalid or missing status")
        if not pages:
            reasons.append("no visited pages")
        if not exhausted:
            reasons.append("pagination not exhausted")
        if stop_reason not in VALID_COMPLETE_STOP_REASONS:
            reasons.append("missing or non-completing stop reason")
        elif not stop_evidence_complete:
            reasons.append("visited-page evidence does not satisfy stop reason")
        if status in ("blocked", "error"):
            reasons.append("query failed")
        error = "; ".join(reasons) or "query incomplete"
    return {
        "query": expected_query,
        "status": status if status in VALID_STATUSES else "error",
        "pages_checked": pages,
        "exhausted": exhausted,
        "stop_reason": stop_reason,
        "complete": complete,
        "error": error,
    }


def normalize_entry_run(raw: dict, expected_url: str) -> dict:
    status = text(raw.get("status")) or "not_run"
    checked_at = text(raw.get("checked_at"))
    evidence = text(raw.get("evidence"))
    error = text(raw.get("error"))
    complete = status in ("success", "empty") and valid_iso_timestamp(checked_at) and bool(evidence)
    if not complete and not error:
        reasons = []
        if status not in VALID_STATUSES:
            reasons.append("invalid or missing status")
        if not valid_iso_timestamp(checked_at):
            reasons.append("missing or invalid checked_at")
        if not evidence:
            reasons.append("missing evidence")
        if status in ("blocked", "error"):
            reasons.append("entry failed")
        error = "; ".join(reasons) or "entry incomplete"
    return {
        "url": expected_url,
        "status": status if status in VALID_STATUSES else "error",
        "checked_at": checked_at,
        "evidence": evidence,
        "complete": complete,
        "error": error,
    }


def normalize_company_audit(raw: dict, company: str) -> dict:
    status = text(raw.get("status")) or "deferred"
    attempted = raw.get("official_search_attempted") is True
    queries = text_list(raw.get("queries"))
    pages = text_list(raw.get("pages_checked"))
    checked_at = text(raw.get("checked_at"))
    error = text(raw.get("error"))
    complete = company_audit_is_complete(raw)
    if not complete and not error:
        reasons = []
        if status not in VALID_AUDIT_STATUSES:
            reasons.append("invalid status")
        if not attempted:
            reasons.append("official search not attempted")
        if not queries:
            reasons.append("no company-specific query")
        if not pages:
            reasons.append("no official/search page checked")
        if not valid_iso_timestamp(checked_at):
            reasons.append("missing or invalid checked_at")
        error = "; ".join(reasons) or "company audit pending"
    return {
        "company": company,
        "status": status if status in VALID_AUDIT_STATUSES else "error",
        "official_search_attempted": attempted,
        "queries": queries,
        "pages_checked": pages,
        "checked_at": checked_at,
        "complete": complete,
        "error": error,
    }


def normalize_source_results(report: dict, plan: dict) -> tuple[list[dict], list[dict]]:
    supplied = report.get("sources", []) if isinstance(report, dict) else []
    by_id = {
        text(item.get("id")): item
        for item in supplied
        if isinstance(item, dict) and text(item.get("id"))
    }
    normalized = []
    candidates = []
    planned_groups = {group["id"]: group for group in plan.get("source_groups", [])}
    for group in SOURCE_GROUPS:
        raw = by_id.get(group["id"], {})
        raw_status = text(raw.get("status")) or "not_run"
        raw_error = text(raw.get("error"))
        source_candidates = raw.get("candidates", [])
        if not isinstance(source_candidates, list):
            source_candidates = []
        source_candidates = [item for item in source_candidates if isinstance(item, dict)]
        for candidate in source_candidates:
            item = candidate.copy()
            item.setdefault("source_group", group["id"])
            item.setdefault("source_platform", group["label"])
            candidates.append(item)

        planned = planned_groups.get(group["id"], {})
        supplied_coverage = raw.get("role_coverage", [])
        if not isinstance(supplied_coverage, list):
            supplied_coverage = []
        coverage_by_role = {
            normalize(item.get("role")): item
            for item in supplied_coverage
            if isinstance(item, dict) and normalize(item.get("role"))
        }
        normalized_coverage = []
        coverage_errors = []
        for role_task in planned.get("role_tasks", []):
            role = text(role_task.get("role"))
            coverage = coverage_by_role.get(normalize(role), {})
            role_status = text(coverage.get("status")) or "not_run"
            supplied_runs = coverage.get("query_runs", [])
            if not isinstance(supplied_runs, list):
                supplied_runs = []
            runs_by_query = {
                normalize(item.get("query")): item
                for item in supplied_runs
                if isinstance(item, dict) and normalize(item.get("query"))
            }
            query_runs = [
                normalize_query_run(
                    runs_by_query.get(normalize(query), {}),
                    query,
                    int(planned.get("max_result_pages_per_query", 1)),
                    int(planned.get("stop_after_consecutive_no_new_pages", 1)),
                )
                for query in role_task.get("queries", [])
            ]
            missing_queries = [item["query"] for item in query_runs if not item["complete"]]
            complete = (
                role_status in ("success", "empty")
                and bool(query_runs)
                and not missing_queries
            )
            role_error = text(coverage.get("error"))
            if not complete:
                if role_status in ("blocked", "error") and not role_error:
                    role_error = "missing failure reason"
                role_error = role_error or f"{len(missing_queries)} planned query runs incomplete"
                coverage_errors.append(f"{role}: {role_error}")
            normalized_coverage.append({
                "role": role,
                "status": role_status if role_status in VALID_STATUSES else "error",
                "query_runs": query_runs,
                "missing_planned_queries": missing_queries,
                "complete": complete,
                "error": role_error,
            })

        supplied_entries = raw.get("entry_runs", [])
        if not isinstance(supplied_entries, list):
            supplied_entries = []
        entries_by_url = {
            text(item.get("url")): item
            for item in supplied_entries
            if isinstance(item, dict) and text(item.get("url"))
        }
        entry_runs = [
            normalize_entry_run(entries_by_url.get(url, {}), url)
            for url in planned.get("entry_urls", [])
        ]
        entry_coverage_complete = all(item["complete"] for item in entry_runs)
        if not entry_coverage_complete:
            coverage_errors.append(
                f"{sum(1 for item in entry_runs if not item['complete'])} planned entry URLs incomplete"
            )

        enumerated_companies = text_list(raw.get("enumerated_companies"))
        enumeration_complete = raw.get("enumeration_complete") is True
        supplied_audits = raw.get("company_audits", [])
        if not isinstance(supplied_audits, list):
            supplied_audits = []
        required_companies = list(dict.fromkeys([
            *text_list(planned.get("required_watch_companies")),
            *enumerated_companies,
            *[text(item.get("company")) for item in source_candidates if text(item.get("company"))],
            *[
                text(item.get("company")) for item in supplied_audits
                if isinstance(item, dict) and text(item.get("company"))
            ],
        ]))
        audits_by_company = {
            normalize(item.get("company")): item
            for item in supplied_audits
            if isinstance(item, dict) and normalize(item.get("company"))
        }
        company_audits = [
            normalize_company_audit(audits_by_company.get(normalize(company), {}), company)
            for company in required_companies
        ]
        company_audit_complete = all(item["complete"] for item in company_audits)
        if planned.get("requires_company_enumeration") and not enumeration_complete:
            company_audit_complete = False
            coverage_errors.append("Nowcoder company enumeration incomplete")
        if not company_audit_complete:
            coverage_errors.append(
                f"{sum(1 for item in company_audits if not item['complete'])} company audits incomplete"
            )

        role_coverage_complete = bool(normalized_coverage) and all(
            item["complete"] for item in normalized_coverage
        )
        coverage_complete = role_coverage_complete and entry_coverage_complete and company_audit_complete
        if coverage_complete:
            status = "success" if source_candidates else "empty"
            error = ""
        elif raw_status == "blocked":
            status = "blocked"
            error = raw_error or "; ".join(coverage_errors) or "Source blocked"
        else:
            status = "error"
            error = raw_error or "; ".join(coverage_errors) or "Source coverage incomplete"
        normalized.append({
            "id": group["id"],
            "label": group["label"],
            "status": status,
            "coverage_complete": coverage_complete,
            "role_coverage_complete": role_coverage_complete,
            "entry_coverage_complete": entry_coverage_complete,
            "company_audit_complete": company_audit_complete,
            "role_coverage": normalized_coverage,
            "entry_runs": entry_runs,
            "enumeration_complete": enumeration_complete,
            "enumerated_companies": enumerated_companies,
            "company_audits": company_audits,
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


def candidate_readiness(candidate: dict) -> list[str]:
    reasons = [f"missing {field}" for field in READY_FIELDS if not text(candidate.get(field))]
    if text(candidate.get("checked_at")) and not valid_iso_timestamp(candidate.get("checked_at")):
        reasons.append("invalid checked_at")
    status = normalize(candidate.get("application_status"))
    if status and status not in OPEN_APPLICATION_STATUSES:
        reasons.append("application status is not open")
    deadline = text(candidate.get("deadline"))[:10]
    if deadline:
        try:
            if date.fromisoformat(deadline) < date.today():
                reasons.append("application deadline has passed")
        except ValueError:
            reasons.append("invalid deadline")
    return reasons


def candidate_matches_role(candidate: dict, role: str, profile: dict) -> bool:
    explicit = {normalize(value) for value in text_list(candidate.get("matched_roles"))}
    if normalize(role) in explicit:
        return True
    haystack = normalize(" ".join(
        text(candidate.get(field))
        for field in ("title", "responsibilities", "direction_tags", "highlight")
    ))
    return any(normalize(term) in haystack for term in role_aliases(profile, role))


def discovery_history_path(workspace: Path, config: dict) -> Path:
    value = config.get("files", {}).get("discovery_history", f"{RUNTIME_DIR}/state/discovery-runs.json")
    path = Path(value)
    return path if path.is_absolute() else workspace / path


def record_run(workspace: Path, config: dict, status: dict) -> None:
    path = discovery_history_path(workspace, config)
    history = read_json(path, {"schema_version": 2, "runs": []})
    if not isinstance(history, dict):
        history = {"schema_version": 2, "runs": []}
    history["schema_version"] = 2
    runs = history.setdefault("runs", [])
    runs.append(status)
    retention = int(config.get("discovery", {}).get("history_retention_runs", 30))
    history["runs"] = runs[-max(1, retention):]
    write_json(path, history)


def persist_pending_leads(
    workspace: Path,
    config: dict,
    report: dict,
    ready: list[dict],
    leads: list[dict],
) -> list[dict]:
    path = pending_leads_path(workspace, config)
    state = read_json(path, {"leads": [], "resolved": []})
    existing = state.get("leads", []) if isinstance(state, dict) else []
    if not isinstance(existing, list):
        existing = []
    by_key = {candidate_key(item): item for item in existing if candidate_key(item) != "||"}
    supplied_resolutions = report.get("lead_resolutions", [])
    if not isinstance(supplied_resolutions, list):
        supplied_resolutions = []
    valid_resolutions = {}
    for item in supplied_resolutions:
        if not isinstance(item, dict):
            continue
        key = text(item.get("lead_key"))
        resolution = text(item.get("resolution"))
        evidence = text(item.get("evidence"))
        checked_at = text(item.get("checked_at"))
        if (
            key
            and resolution in {"closed", "duplicate", "irrelevant"}
            and evidence
            and valid_iso_timestamp(checked_at)
        ):
            saved = item.copy()
            saved["resolved_at"] = now_iso()
            valid_resolutions[key] = saved
    resolution_history = state.get("resolved", []) if isinstance(state, dict) else []
    if not isinstance(resolution_history, list):
        resolution_history = []
    resolved_keys = {
        text(item.get("lead_key"))
        for item in resolution_history
        if isinstance(item, dict) and text(item.get("lead_key"))
    }
    resolved_keys.update(valid_resolutions)
    resolved_keys.update(candidate_key(item) for item in ready)
    for key in resolved_keys:
        by_key.pop(key, None)
    for item in leads:
        key = candidate_key(item)
        if key != "||" and key not in resolved_keys:
            saved = item.copy()
            saved["lead_key"] = key
            saved["last_seen_at"] = now_iso()
            by_key[key] = saved
    pending = list(by_key.values())
    resolution_history.extend(valid_resolutions.values())
    write_json(
        path,
        {
            "schema_version": 2,
            "updated_at": now_iso(),
            "leads": pending,
            "resolved": resolution_history[-500:],
        },
    )
    return pending


def persist_company_audits(workspace: Path, config: dict, sources: list[dict]) -> list[dict]:
    path = company_audit_path(workspace, config)
    state = read_json(path, {"schema_version": 1, "companies": {}})
    existing = state.get("companies", {}) if isinstance(state, dict) else {}
    if not isinstance(existing, dict):
        existing = {}
    for source in sources:
        for audit in source.get("company_audits", []):
            company = text(audit.get("company"))
            if not company:
                continue
            saved = audit.copy()
            saved["source_group"] = source.get("id")
            saved["last_seen_at"] = now_iso()
            existing[normalize(company)] = saved
    write_json(
        path,
        {"schema_version": 1, "updated_at": now_iso(), "companies": existing},
    )
    return [
        item for item in existing.values()
        if isinstance(item, dict) and not company_audit_is_complete(item)
    ]


def finalize_report(workspace: Path, report: dict) -> tuple[dict, list[dict], list[dict]]:
    config = load_config(workspace)
    requested_mode = text(report.get("mode"))
    mode = resolve_mode(workspace, config, requested_mode if requested_mode in VALID_MODES else "auto")
    plan = query_plan(
        config,
        mode,
        load_pending_leads(workspace, config),
        load_pending_company_audits(workspace, config),
    )
    sources, candidates = normalize_source_results(report, plan)
    candidates = dedupe_candidates(candidates)
    ready = []
    leads = []
    for item in candidates:
        reasons = candidate_readiness(item)
        if reasons:
            lead = item.copy()
            lead["lead_reasons"] = reasons
            leads.append(lead)
        else:
            ready.append(item)
    pending_leads = persist_pending_leads(workspace, config, report, ready, leads)
    pending_company_audits = persist_company_audits(workspace, config, sources)
    successful = [source for source in sources if source["coverage_complete"]]
    blocked = [source for source in sources if not source["coverage_complete"]]
    source_coverage_complete = len(successful) == len(SOURCE_GROUPS)
    coverage_complete = (
        source_coverage_complete
        and not pending_leads
        and not pending_company_audits
    )
    can_report_no_jobs = not ready and coverage_complete
    if ready and coverage_complete:
        conclusion = "jobs_found"
    elif ready:
        conclusion = "jobs_found_incomplete"
    elif can_report_no_jobs:
        conclusion = "searched_no_jobs"
    elif successful:
        conclusion = "partial_inconclusive"
    else:
        conclusion = "blocked"
    profile = config.get("profile", {})
    roles = text_list(profile.get("roles"))
    role_candidate_counts = {
        role: sum(1 for candidate in ready if candidate_matches_role(candidate, role, profile))
        for role in roles
    }
    low_yield_threshold = int(config.get("discovery", {}).get("initial_low_yield_threshold", 5))
    status = {
        "schema_version": 2,
        "run_id": text(report.get("run_id")) or datetime.now().astimezone().strftime("DISC-%Y%m%d-%H%M%S"),
        "finished_at": now_iso(),
        "mode": mode,
        "conclusion": conclusion,
        "coverage_complete": coverage_complete,
        "source_coverage_complete": source_coverage_complete,
        "full_search_complete": mode == "initial_full" and coverage_complete,
        "can_report_no_jobs": can_report_no_jobs,
        "successful_source_count": len(successful),
        "required_successful_sources_for_empty": len(SOURCE_GROUPS),
        "candidate_count": len(candidates),
        "ready_candidate_count": len(ready),
        "lead_count": len(leads),
        "pending_lead_count": len(pending_leads),
        "pending_company_audit_count": len(pending_company_audits),
        "role_candidate_counts": role_candidate_counts,
        "roles_without_open_candidates": [role for role, count in role_candidate_counts.items() if count == 0],
        "low_yield": mode == "initial_full" and len(ready) < low_yield_threshold,
        "low_yield_threshold": low_yield_threshold,
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
    print(f"模式：{run.get('mode', 'unknown')}；全量覆盖：{'是' if run.get('coverage_complete') else '否'}。")
    print()
    if run.get("conclusion") == "blocked":
        print("岗位发现被阻塞：所有来源均未成功执行，不能报告‘没有岗位’。")
    elif run.get("conclusion") == "partial_inconclusive":
        print(
            "岗位发现仅部分完成，结果不完整，不能报告‘没有岗位’。"
            f"待核实线索 {run.get('pending_lead_count', 0)} 条，"
            f"待完成企业审计 {run.get('pending_company_audit_count', 0)} 家。"
        )
    elif run.get("conclusion") == "jobs_found_incomplete":
        print(
            f"已核实 {run.get('ready_candidate_count', 0)} 个当前可投岗位，"
            "但岗位方向、来源或持久化重试队列尚未完成，必须继续扩搜，不能报告刷新完成。"
        )
    elif run.get("conclusion") == "searched_no_jobs":
        print("四路来源和全部目标岗位方向均已搜索到耗尽，本轮未发现当前可投岗位。")
    else:
        print(
            f"本轮发现 {run.get('candidate_count', 0)} 条线索，其中 "
            f"{run.get('ready_candidate_count', 0)} 条职责完整且当前可投。"
        )
    role_counts = run.get("role_candidate_counts", {})
    if role_counts:
        print()
        print("## 岗位方向")
        for role, count in role_counts.items():
            print(f"- {role}: 当前可投 {count} 个")
    print()
    print(
        f"待核实线索：{run.get('pending_lead_count', 0)}；"
        f"待完成企业审计：{run.get('pending_company_audit_count', 0)}。"
    )
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
    plan.add_argument("--mode", choices=("auto", "initial_full", "daily_refresh"), default="auto")
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
