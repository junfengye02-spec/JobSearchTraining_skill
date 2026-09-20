#!/usr/bin/env python3
"""Merge high-growth company leads into the persistent company watchlist."""

import argparse
import json
import re
from datetime import date
from pathlib import Path


STATUS_KEYS = {
    "新增匹配岗位": "matched_jobs",
    "已有匹配岗位": "matched_jobs",
    "暂无匹配岗位": "no_matching_jobs",
    "岗位职责不完整": "incomplete_job_details",
    "访问受限": "access_restricted",
    "暂停关注": "paused",
}


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8-sig") as handle:
            return json.load(handle)
    except FileNotFoundError:
        return default


def company_key(name):
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", str(name).lower())


def as_companies(payload):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        companies = payload.get("companies", [])
        return companies if isinstance(companies, list) else []
    return []


def merge_list(old, new, identity=None):
    merged = []
    seen = set()
    for value in list(old or []) + list(new or []):
        marker = identity(value) if identity else json.dumps(value, ensure_ascii=False, sort_keys=True)
        if marker in seen:
            continue
        seen.add(marker)
        merged.append(value)
    return merged


def evidence_key(item):
    if not isinstance(item, dict):
        return str(item)
    return "|".join(
        str(item.get(field, "")).strip()
        for field in ("source_url", "type", "summary", "published_at")
    )


def merge_company(existing, incoming, today):
    merged = dict(existing or {})
    for key, value in incoming.items():
        if value not in (None, "", [], {}):
            merged[key] = value

    merged["company"] = str(incoming.get("company") or merged.get("company") or "").strip()
    merged["first_seen"] = existing.get("first_seen") or incoming.get("first_seen") or today
    merged["last_seen"] = today
    merged["last_checked"] = incoming.get("checked_at") or incoming.get("last_checked") or today
    merged["evidence"] = merge_list(
        existing.get("evidence", []), incoming.get("evidence", []), evidence_key
    )
    for field in ("risk_flags", "matched_titles", "aliases"):
        merged[field] = merge_list(existing.get(field, []), incoming.get(field, []))
    return merged


def build_stats(input_companies, new_count):
    stats = {
        "discovered": len(input_companies),
        "deep_checked": 0,
        "new_watch_companies": new_count,
        "matched_jobs": 0,
        "no_matching_jobs": 0,
        "incomplete_job_details": 0,
        "access_restricted": 0,
        "paused": 0,
    }
    matched_companies = set()
    for item in input_companies:
        if item.get("official_search_attempted"):
            stats["deep_checked"] += 1
        status = str(item.get("job_search_status", "")).strip()
        bucket = STATUS_KEYS.get(status)
        if not bucket:
            continue
        if bucket == "matched_jobs":
            matched_companies.add(company_key(item.get("company", "")))
        else:
            stats[bucket] += 1
    stats["matched_jobs"] = len(matched_companies)
    return stats


def write_json(path, payload):
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--date", default=date.today().isoformat())
    args = parser.parse_args()

    incoming = [item for item in as_companies(load_json(args.input, [])) if item.get("company")]
    prior_payload = load_json(args.state, {"companies": []})
    prior = as_companies(prior_payload)
    by_key = {company_key(item.get("company", "")): item for item in prior if item.get("company")}

    new_count = 0
    for item in incoming:
        key = company_key(item["company"])
        if key not in by_key or str(by_key[key].get("first_seen", "")) == args.date:
            new_count += 1
        by_key[key] = merge_company(by_key.get(key, {}), item, args.date)

    companies = sorted(
        by_key.values(),
        key=lambda item: (-float(item.get("growth_score") or 0), item.get("company", "")),
    )
    payload = {
        "updated_at": args.date,
        "stats": build_stats(incoming, new_count),
        "companies": companies,
    }
    write_json(args.state, payload)
    write_json(args.output, payload)
    print(json.dumps(payload["stats"], ensure_ascii=False))


if __name__ == "__main__":
    main()
