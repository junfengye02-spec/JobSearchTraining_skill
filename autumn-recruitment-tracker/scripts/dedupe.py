#!/usr/bin/env python3
"""Dedupe candidate postings against state/seen_postings.json.

Usage:
  python3 dedupe.py --input candidates.json --state state/seen_postings.json \
      --config config.json [--output new_only.json]

candidates.json: JSON array of objects with fields:
  company, title, city, highlight, source_url, source_platform
  (discovered_date optional, defaults to today)

Prints the list of newly-seen postings (JSON array) to stdout (or --output
file if given), and updates the state file in place.
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import date, datetime
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

from metadata import annotate_record

VOLATILE_PARAM_PREFIXES = ("utm_", "spm", "session", "token", "sid", "from", "trace", "_t", "timestamp")
SOURCE_AUDIT_FIELDS = (
    "discovery_url", "discovery_platform", "official_url",
    "official_search_attempted", "official_checked_at", "official_match_status",
    "official_evidence_url", "official_check_result", "official_fallback_reason",
)


def is_nowcoder_url(url):
    hostname = (urlsplit(str(url or "")).hostname or "").lower()
    return hostname == "nowcoder.com" or hostname.endswith(".nowcoder.com")


def verified_nowcoder_upgrade(existing, candidate):
    """Consume explicit research evidence; never infer official status from a URL."""
    old_url = existing.get("source_url", "")
    new_url = candidate.get("source_url", "")
    return (
        is_nowcoder_url(old_url)
        and clean_url(candidate.get("discovery_url", "")) == clean_url(old_url)
        and company_identity(existing.get("company", "")) == company_identity(candidate.get("company", ""))
        and candidate.get("official_search_attempted") is True
        and candidate.get("official_match_status") in {"matched_job", "target_campus_open"}
        and urlsplit(new_url).scheme in {"https", "http"}
        and bool(urlsplit(new_url).hostname)
        and not is_nowcoder_url(new_url)
        and clean_url(candidate.get("official_url", "")) == clean_url(new_url)
        and urlsplit(candidate.get("official_evidence_url", "")).scheme in {"https", "http"}
        and not is_nowcoder_url(candidate.get("official_evidence_url", ""))
        and bool(candidate.get("official_check_result"))
        and bool(candidate.get("official_checked_at"))
    )
COMPANY_ALIAS_GROUPS = (
    (("nvidia", "英伟达"), "nvidia"),
    (("amazon", "亚马逊"), "amazon"),
    (("shopee", "虾皮"), "shopee"),
    (("pdd", "拼多多"), "pdd"),
    (("dji", "大疆"), "dji"),
    (("联影",), "联影医疗"),
    (("小鹏",), "小鹏汽车"),
    (("普渡",), "普渡机器人"),
    (("新石器",), "新石器无人车"),
    (("天源迪科",), "天源迪科"),
    (("凌志软件",), "凌志软件"),
    (("天翼云",), "天翼云"),
    (("交银金科", "交银金融科技"), "交银金科"),
    (("恒生电子",), "恒生电子"),
    (("中欧基金",), "中欧基金"),
    (("中通服网盈",), "中通服网盈"),
    (("贝壳找房", "贝壳"), "贝壳"),
)


def today_str():
    return date.today().isoformat()


def normalize_text(s):
    if not s:
        return ""
    s = s.strip()
    s = re.sub(r"\s+", "", s)
    s = s.translate(str.maketrans("（）【】", "()[]"))
    return s.lower()


def clean_url(url):
    if not url:
        return ""
    parts = urlsplit(url)
    kept = [
        (k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not any(k.lower().startswith(p) for p in VOLATILE_PARAM_PREFIXES)
    ]
    kept.sort()
    new_query = urlencode(kept)
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), new_query, ""))


def posting_hash(company, title, url):
    key = f"{normalize_text(company)}|{normalize_text(title)}|{clean_url(url)}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def company_identity(company):
    normalized = normalize_text(company)
    for aliases, canonical in COMPANY_ALIAS_GROUPS:
        if any(normalize_text(alias) in normalized for alias in aliases):
            return canonical
    normalized = re.sub(r"(?:股份有限公司|有限责任公司|有限公司|科技股份|管理有限公司)$", "", normalized)
    normalized = re.sub(r"^(?:苏州工业园区|北京|上海|广州|深圳|大连)", "", normalized)
    return normalized


def normalized_title(title):
    return normalize_text(re.sub(r"\[方向待确认\]", "", str(title or "")))


def fuzzy_key(company, title):
    return f"{company_identity(company)}|{normalized_title(title)}"


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write("\n")


def merge_candidate(existing, candidate, config):
    """Refresh confirmed source metadata without changing the dedupe identity."""
    for key in (
        "city", "highlight", "responsibilities", "job_type", "enterprise_tag",
        "match_level", "verification",
    ):
        value = candidate.get(key)
        if value not in (None, ""):
            existing[key] = value
    # Preserve the evidence that accompanies the selected destination. A later
    # fallback discovery must not silently downgrade an already official link.
    if clean_url(existing.get("source_url", "")) == clean_url(candidate.get("source_url", "")):
        for key in SOURCE_AUDIT_FIELDS:
            if key in candidate:
                existing[key] = candidate[key]
    annotate_record(existing, config)
    return existing


def maybe_archive_season(state, config, state_path):
    season_end = config.get("season_end_date")
    if not season_end:
        return state
    try:
        if date.today() <= date.fromisoformat(season_end):
            return state
    except ValueError:
        return state
    season_label = state.get("season", "season")
    archive_path = state_path.replace(".json", f".{season_label}.json")
    save_json(archive_path, state)
    return {"schema_version": 1, "season": season_label, "last_run": None, "postings": {}}


def prune_stale(state, retention_days):
    if not retention_days:
        return state
    cutoff = date.today().toordinal() - int(retention_days)
    kept = {}
    for h, rec in state.get("postings", {}).items():
        try:
            last = date.fromisoformat(rec.get("last_confirmed", rec.get("first_seen", today_str())))
        except ValueError:
            last = date.today()
        if last.toordinal() >= cutoff:
            kept[h] = rec
    state["postings"] = kept
    return state


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--config", required=True)
    ap.add_argument("--output")
    args = ap.parse_args()

    candidates = load_json(args.input, [])
    config = load_json(args.config, {})
    state = load_json(args.state, {"schema_version": 1, "season": config.get("target_season_label", "season"), "last_run": None, "postings": {}})

    state = maybe_archive_season(state, config, args.state)

    postings = state.setdefault("postings", {})
    fuzzy_index = {fuzzy_key(rec["company"], rec["title"]): h for h, rec in postings.items()}

    today = today_str()
    new_only = []

    for c in candidates:
        company = c.get("company", "").strip()
        title = c.get("title", "").strip()
        url = c.get("source_url", "").strip()
        if not company or not title:
            continue

        h = posting_hash(company, title, url)
        fkey = fuzzy_key(company, title)

        if h in postings:
            postings[h]["last_confirmed"] = today
            merge_candidate(postings[h], c, config)
            continue

        provenance_matches = [
            record for record in postings.values()
            if c.get("discovery_url")
            and record.get("discovery_url")
            and company_identity(record["company"]) == company_identity(company)
            and clean_url(record["discovery_url"]) == clean_url(c["discovery_url"])
            and clean_url(record.get("source_url", "")) == clean_url(url)
        ]
        if len(provenance_matches) == 1:
            provenance_matches[0]["last_confirmed"] = today
            merge_candidate(provenance_matches[0], c, config)
            continue

        # A verified source migration is an update even when the official title
        # differs. Original company + discovery URL identifies the prior row.
        # Ambiguous shared discovery URLs are not automatically migrated.
        upgrade_keys = [
            key for key, record in postings.items()
            if verified_nowcoder_upgrade(record, c)
        ] if c.get("discovery_url") else []
        if len(upgrade_keys) == 1:
            existing_h = upgrade_keys[0]
            record = postings.pop(existing_h)
            record["discovery_url"] = record["source_url"]
            record["discovery_platform"] = record.get("source_platform", "牛客网")
            record["source_url"] = url
            record["source_platform"] = c.get("source_platform", "公司官方招聘")
            record["last_confirmed"] = today
            # Preserve the existing title, dates and user processing fields.
            merge_candidate(record, c, config)
            upgraded_h = posting_hash(record["company"], record["title"], url)
            postings[upgraded_h] = record
            for indexed_key, indexed_hash in list(fuzzy_index.items()):
                if indexed_hash == existing_h:
                    fuzzy_index[indexed_key] = upgraded_h
            fuzzy_index[fkey] = upgraded_h
            continue

        if fkey in fuzzy_index:
            existing_h = fuzzy_index[fkey]
            postings[existing_h]["last_confirmed"] = today
            merge_candidate(postings[existing_h], c, config)
            continue

        rec = {
            "company": company,
            "title": title,
            "city": c.get("city", "未注明"),
            "highlight": c.get("highlight", ""),
            "source_platform": c.get("source_platform", ""),
            "source_url": url,
            "responsibilities": c.get("responsibilities", ""),
            "job_type": c.get("job_type", ""),
            "enterprise_tag": c.get("enterprise_tag", ""),
            "match_level": c.get("match_level", ""),
            "verification": c.get("verification", ""),
            "first_seen": today,
            "last_confirmed": today,
        }
        for key in SOURCE_AUDIT_FIELDS:
            if key in c:
                rec[key] = c[key]
        annotate_record(rec, config)
        postings[h] = rec
        fuzzy_index[fkey] = h
        new_only.append(rec)

    for rec in postings.values():
        annotate_record(rec, config)
    state = prune_stale(state, config.get("state_retention_days"))
    state["last_run"] = datetime.now().astimezone().isoformat()

    save_json(args.state, state)

    out = json.dumps(new_only, ensure_ascii=False, indent=2)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out + "\n")
    else:
        print(out)


if __name__ == "__main__":
    main()
