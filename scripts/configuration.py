"""Backward-compatible runtime configuration upgrades."""

from __future__ import annotations

import copy


RUNTIME_DIR = ".adaptive-interview-coach"


V1_TO_V2_DEFAULTS = {
    "initial_max_candidates_per_source": (50, 120),
    "daily_max_candidates_per_source": (20, 40),
    "initial_max_result_pages_per_query": (5, 8),
    "daily_max_result_pages_per_query": (2, 3),
    "initial_max_new_company_verifications": (30, 120),
    "daily_max_new_company_verifications": (5, 20),
    "initial_low_yield_threshold": (5, 20),
}


V2_DISCOVERY_DEFAULTS = {
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
}


V2_FILE_DEFAULTS = {
    "pending_job_leads": f"{RUNTIME_DIR}/state/pending-job-leads.json",
    "company_audit": f"{RUNTIME_DIR}/state/company-audit.json",
}


def upgrade_config(config: dict) -> dict:
    """Return a v2 config while preserving intentional user customizations."""
    upgraded = copy.deepcopy(config)
    try:
        version = int(upgraded.get("schema_version", 1))
    except (TypeError, ValueError):
        version = 1

    profile = upgraded.setdefault("profile", {})
    profile.setdefault("watch_companies", [])
    profile.setdefault("include_high_growth_companies", False)

    discovery = upgraded.setdefault("discovery", {})
    if version < 2:
        for key, (old_default, new_default) in V1_TO_V2_DEFAULTS.items():
            if discovery.get(key, old_default) == old_default:
                discovery[key] = new_default
    for key, value in V2_DISCOVERY_DEFAULTS.items():
        discovery.setdefault(key, value)

    files = upgraded.setdefault("files", {})
    for key, value in V2_FILE_DEFAULTS.items():
        files.setdefault(key, value)

    upgraded["schema_version"] = 2
    return upgraded
