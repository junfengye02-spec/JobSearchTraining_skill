#!/usr/bin/env python3
"""Derive stable monitoring metadata for a recruitment record."""

import re


INTERN_MARKERS = ("实习", "intern")
FORMAL_MARKERS = ("校招", "正式", "全职", "应届", "管培生")
EARLY_MARKERS = ("提前批", "AIDU")
CENTRAL_MARKERS = (
    "央企", "国企", "央国企", "中国电信", "天翼云", "中国移动", "移动云",
    "中国联通", "联通云", "中国电子", "中国电科", "中电福富", "国家电网",
    "南方电网", "南网数字", "中国石油", "中国石化", "中国海油", "航天科技",
    "航天科工", "航空工业", "中国商飞", "中国中车", "中国中铁", "中国铁建",
    "中国交建", "中国四维", "中船", "中广核", "兵器工业",
)


def _text(record):
    return " ".join(
        str(record.get(key, "") or "")
        for key in (
            "company", "title", "highlight", "responsibilities", "job_type",
            "enterprise_tag", "source_platform", "verification",
        )
    )


def _watch_entry(record, config):
    company = str(record.get("company", "") or "").lower()
    watch = config.get("priority_monitoring", {}).get("watch_companies", [])
    for entry in watch:
        names = [entry.get("company", "")] + entry.get("aliases", [])
        if any(str(name).lower() in company or company in str(name).lower() for name in names if name):
            return entry
    return None


def explicit_grad_target(text, config):
    matches = re.findall(r"(20\d{2})\s*届", text)
    if matches:
        return f"{matches[-1]}届"
    if re.search(r"(?<!\d)27\s*届", text, re.IGNORECASE):
        return "2027届"
    target = str(config.get("target_grad_year", "2027届") or "2027届")
    target_match = re.search(r"(20\d{2})", target)
    target_year = target_match.group(1) if target_match else "2027"
    short_year = target_year[-2:]
    english_recruitment_context = r"campus|graduate|early\s*career|intern(?:ship)?"
    if re.search(rf"(?<!\d){re.escape(target_year)}(?!\d)", text, re.IGNORECASE) and re.search(
        english_recruitment_context, text, re.IGNORECASE
    ):
        return f"{target_year}届"
    if re.search(
        rf"(?<!\d)20\d{{2}}\s*[-/]\s*{re.escape(short_year)}(?!\d)", text, re.IGNORECASE
    ) and re.search(english_recruitment_context, text, re.IGNORECASE):
        return f"{target_year}届"
    return f"{target}（未明确）"


def _primary_text(record):
    return " ".join(
        str(record.get(key, "") or "")
        for key in ("company", "title", "highlight", "responsibilities", "job_type")
    )


def explicitly_older_than_target(record, config):
    """Return true only when the primary job content names an older cohort."""
    primary = _primary_text(record)
    target = str(config.get("target_grad_year", "2027届") or "2027届")
    target_match = re.search(r"(20\d{2})\s*届", target)
    target_year = int(target_match.group(1)) if target_match else 2027
    years = [int(year) for year in re.findall(r"(20\d{2})\s*届", primary)]
    if not years:
        return False
    if any(year >= target_year for year in years):
        return False
    return min(years) < target_year


def is_2027_campus(record, config):
    text = _text(record)
    title = str(record.get("title", "") or "")
    target = str(config.get("target_grad_year", "2027届") or "2027届")
    target_match = re.search(r"(20\d{2})", target)
    target_year = target_match.group(1) if target_match else "2027"
    short_year = target_year[-2:]
    english_recruitment_context = r"campus|graduate|early\s*career|intern(?:ship)?"
    return bool(
        re.search(r"2027\s*(?:届|[/、和至-]\s*2028\s*届)|(?<!\d)27\s*届", text, re.IGNORECASE)
        or target in text
        or (
            re.search(rf"(?<!\d){re.escape(target_year)}(?!\d)", title, re.IGNORECASE)
            and re.search(english_recruitment_context, title, re.IGNORECASE)
        )
        or (
            re.search(rf"(?<!\d)20\d{{2}}\s*[-/]\s*{re.escape(short_year)}(?!\d)", title, re.IGNORECASE)
            and re.search(english_recruitment_context, title, re.IGNORECASE)
        )
    )


def recruitment_track(record, is_2027):
    text = _text(record)
    lower = text.lower()
    has_sp_marker = bool(re.search(r"(?<![A-Za-z0-9])SP(?![A-Za-z0-9])", text, re.IGNORECASE))
    if any(marker.lower() in lower for marker in EARLY_MARKERS) or has_sp_marker:
        return "2027届校招提前批" if is_2027 else "校招提前批（届别未明确）"
    has_intern_marker = "实习" in lower or bool(re.search(r"\bintern(?:ship)?\b", lower))
    if has_intern_marker:
        return "2027届实习/可转正" if is_2027 else "实习/可转正（届别未明确）"
    if any(marker in lower for marker in FORMAL_MARKERS):
        return "2027届校招正式批" if is_2027 else "校招正式批（届别未明确）"
    return "其他招聘轨道（届别未明确）"


def is_central_state_owned(record):
    company = str(record.get("company", "") or "")
    tag = str(record.get("enterprise_tag", "") or "")
    if any(marker.lower() in company.lower() for marker in CENTRAL_MARKERS):
        return True
    if any(marker in tag for marker in ("央企", "国企", "央国企")) and "关联" not in tag:
        return True
    return False


def enterprise_type(record, central):
    text = _text(record)
    tag = str(record.get("enterprise_tag", "") or "").strip()
    lower = text.lower()
    if central or any(marker in tag for marker in ("央企", "国企")):
        return "央企/国企"
    if "专精特新" in text:
        return "国家级专精特新"
    if "小巨人" in text:
        return "国家级小巨人"
    if "独角兽" in text or re.search(r"[abc]轮|d轮|未融资", lower):
        return "独角兽/高成长科技企业"
    if "世界500强" in text:
        return "世界500强"
    if "上市" in text:
        return "上市公司"
    if any(word in text for word in ("大厂", "中大型", "大型科技", "大型互联网")):
        return "中大型科技企业"
    return tag or "其他科技企业"


def watch_priority(record, config, is_2027, central, track):
    entry = _watch_entry(record, config)
    if central:
        return "最高"
    if is_2027 and "正式批" in track:
        return "最高"
    if is_2027:
        return "高"
    if entry:
        return entry.get("watch_level", "重点")
    return "常规"


def annotate_record(record, config):
    """Mutate and return a record, preserving source fields and adding metadata."""
    is_2027 = is_2027_campus(record, config)
    central = is_central_state_owned(record)
    track = recruitment_track(record, is_2027)
    primary = _primary_text(record)
    verification = str(record.get("verification", "") or "")
    if re.search(r"2027\s*(?:届\s*[/、和至-]\s*2028\s*届|[/、和至-]\s*2028\s*届)", primary):
        record["grad_target"] = "2027届（含2028届）"
    elif re.search(r"2027\s*届", primary):
        record["grad_target"] = "2027届"
    else:
        record["grad_target"] = explicit_grad_target(primary or verification, config)
    record["recruitment_track"] = track
    record["is_2027_campus"] = is_2027
    record["enterprise_type"] = enterprise_type(record, central)
    record["is_central_state_owned"] = central
    record["watch_priority"] = watch_priority(record, config, is_2027, central, track)
    return record
