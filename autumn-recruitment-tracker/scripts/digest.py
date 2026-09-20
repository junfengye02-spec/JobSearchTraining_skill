#!/usr/bin/env python3
"""Render the daily digest as Markdown.

Usage:
  python3 digest.py render --new new_only.json --state state/seen_postings.json \
      --config config.json [--date 2026-07-08]

The digest title is built from config.json's target_season_label and
job_category_label, so it stays generic across whatever job category the
skill is configured to track (finance is just the default example).

Prints a Markdown digest to stdout.
"""
import argparse
import json
from collections import OrderedDict
from datetime import date
from pathlib import Path


def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def group_by_company(postings):
    grouped = OrderedDict()
    for rec in postings:
        grouped.setdefault(rec["company"], []).append(rec)
    return grouped


def render_markdown(
    new_postings,
    state,
    today,
    season_label,
    category_label,
    current_postings=None,
    expired_count=0,
    excel_status="未提供",
    max_new=20,
    company_watch=None,
    source_coverage=None,
):
    prefix = f"{season_label} " if season_label else ""
    direction = f"{category_label}方向" if category_label else ""
    title = f"{prefix}{direction}岗位监控日报"
    current = current_postings if current_postings is not None else list(state.get("postings", {}).values())
    priority = [r for r in current if any(city in str(r.get("city", "")) for city in ("广州", "深圳"))]
    campus_27 = [r for r in current if r.get("is_2027_campus")]
    central = [r for r in current if r.get("is_central_state_owned")]

    lines = []
    lines.append(f"# {title} · {today}")
    lines.append("")
    companies = {r.get("company", "") for r in current}
    lines.append(f"新增岗位：{len(new_postings)} | 删除过期：{expired_count} | 当前有效：{len(current)}")
    lines.append(f"已监控公司：{len(companies)} | 明确 2027 届：{len(campus_27)} | 央国企本体：{len(central)} | 广州/深圳优先：{len(priority)}")
    lines.append(f"Excel：{excel_status}")
    lines.append("")
    lines.append("## 广州/深圳优先摘要")
    if priority:
        rank = {"最高": 0, "高": 1, "重点": 2, "常规": 3}
        for r in sorted(priority, key=lambda x: (rank.get(x.get("watch_priority", "常规"), 9), x.get("company", ""), x.get("title", "")))[:12]:
            track = r.get("recruitment_track", r.get("job_type", ""))
            lines.append(f"- **{r.get('company', '')}｜{r.get('title', '')}** — {r.get('city', '未注明')} · {track} · {r.get('watch_priority', '常规')}")
    else:
        lines.append("- 当前没有广州/深圳优先岗位。")
    lines.append("")

    lines.append("## 本轮新增")
    if not new_postings:
        lines.append("今日没有去重后新增岗位。")
    else:
        grouped = group_by_company(new_postings)
        for company, recs in grouped.items():
            lines.append(f"- {company}：{len(recs)} 个")
        if len(new_postings) <= max_new:
            for r in new_postings:
                source_url = r.get("source_url", "")
                link = f"[投递链接]({source_url})" if source_url else "无链接"
                lines.append(f"  - {r.get('title', '')} — {r.get('city', '未注明')} · {link}")
        else:
            lines.append(f"- 仅展开前 {max_new} 条岗位链接，其余新增岗位已写入 JSON/Excel。")
            for r in new_postings[:max_new]:
                source_url = r.get("source_url", "")
                link = f"[投递链接]({source_url})" if source_url else "无链接"
                lines.append(f"  - {r.get('company', '')}｜{r.get('title', '')} — {r.get('city', '未注明')} · {link}")

    if source_coverage is not None:
        recheck = source_coverage.get("current_recheck", {}) if isinstance(source_coverage, dict) else {}
        if recheck:
            lines.append("")
            lines.append("## 存量岗位复核与状态同步")
            lines.append(
                "已逐项复核 {records} 条存量记录（{urls} 个唯一链接）；确认保留 {retained} 条，"
                "访问受限/暂时错误 {restricted} 条，明确失效并同步移除 {expired} 条。".format(
                    records=recheck.get("records_checked", 0),
                    urls=recheck.get("unique_urls", 0),
                    retained=recheck.get("retained_without_block_signal", 0),
                    restricted=recheck.get("access_restricted_or_transient", 0),
                    expired=recheck.get("explicitly_expired_removed", 0),
                )
            )
            policy = str(recheck.get("policy", "")).strip()
            if policy:
                lines.append(f"- 判定口径：{policy}")
            note = str(recheck.get("same_day_baseline_note", "")).strip()
            if note:
                lines.append(f"- 状态同步：{note}")
        discovery = source_coverage.get("discovery", {}) if isinstance(source_coverage, dict) else {}
        if discovery:
            followup_new = discovery.get("followup_new_after_state_dedupe", 0)
            first_pass_new = max(0, discovery.get("new_after_state_dedupe", 0) - followup_new)
            lines.append(
                "- 合并去重：四组原始候选 {raw} 个，统一过滤后 {filtered} 个；"
                "公司别名重复合并 {groups} 组、移除重复记录 {removed} 条；四组首轮新增 {first_pass} 个，"
                "后续ATS复核新增 {followup} 个，当日累计新增 {new} 个。".format(
                    raw=discovery.get("raw_candidates", 0),
                    filtered=discovery.get("filtered_unique_candidates", 0),
                    groups=discovery.get("alias_duplicate_groups_collapsed", 0),
                    removed=discovery.get("alias_duplicate_records_removed", 0),
                    first_pass=first_pass_new,
                    followup=followup_new,
                    new=discovery.get("new_after_state_dedupe", 0),
                )
            )
        followup = source_coverage.get("followup_verification", {}) if isinstance(source_coverage, dict) else {}
        if followup:
            lines.append("")
            lines.append("## 后续动态ATS核验")
            lines.append(
                "继续复核 {attempted} 家高成长公司；解除访问/职责阻塞 {resolved} 家，"
                "核实当前岗位 {verified} 个，去重后新增 {new} 个；仍访问受限 {restricted} 家，"
                "当前无匹配岗位 {no_match} 家，明确停止的旧单岗链接 {expired_links} 个。".format(
                    attempted=followup.get("companies_attempted", 0),
                    resolved=followup.get("companies_resolved", 0),
                    verified=followup.get("verified_current_jobs", 0),
                    new=followup.get("new_after_dedupe", 0),
                    restricted=followup.get("still_access_restricted", 0),
                    no_match=followup.get("no_matching_jobs", 0),
                    expired_links=followup.get("specific_expired_links", 0),
                )
            )
            for item in followup.get("outcomes", []):
                if isinstance(item, dict):
                    lines.append(f"- **{item.get('company', '')}** — {item.get('result', '')}")
            policy = str(followup.get("policy", "")).strip()
            if policy:
                lines.append(f"- 判定口径：{policy}")
        groups = source_coverage.get("four_source_groups", []) if isinstance(source_coverage, dict) else []
        lines.append("")
        lines.append("## 四组来源覆盖")
        for group in groups:
            name = group.get("name", "未命名来源组")
            status = group.get("status", "已完成")
            jobs = group.get("qualified_jobs", 0)
            companies = group.get("companies_checked", 0)
            restricted = group.get("access_restricted", 0)
            lines.append(
                f"- **{name}** — {status}；复核公司 {companies} 家，职责完整候选 {jobs} 个，访问受限 {restricted} 项。"
            )
            scope = str(group.get("scope_coverage", "")).strip()
            if scope:
                lines.append(f"  - 覆盖：{scope}")
            note = str(group.get("note", "")).strip()
            if note:
                lines.append(f"  - 说明：{note}")
        nowcoder = source_coverage.get("nowcoder_entry_audit", {}) if isinstance(source_coverage, dict) else {}
        if nowcoder:
            lines.append("")
            lines.append(
                "牛客入口：已枚举 {enumerated} 家，公众号线索 {wechat} 家，官网已尝试 {attempted} 家，"
                "逐一复核 {reviewed} 家，待复核 {pending} 家；官网未尝试 {unattempted} 家；"
                "官网已尝试但仍受限 {restricted} 家。".format(
                    enumerated=nowcoder.get("enumerated_companies", 0),
                    wechat=nowcoder.get("wechat_clues", 0),
                    attempted=nowcoder.get("official_search_attempted", 0),
                    reviewed=nowcoder.get("individually_reviewed", 0),
                    pending=nowcoder.get("pending_review", 0),
                    unattempted=nowcoder.get("official_not_attempted", 0),
                    restricted=nowcoder.get("official_attempted_but_access_limited", 0),
                )
            )
        growth = source_coverage.get("high_growth", {}) if isinstance(source_coverage, dict) else {}
        if growth:
            lines.append("")
            lines.append(
                "高成长公司覆盖：上市科技 {listed} 家，未上市科创 {private} 家，早期团队 {early} 家，"
                "细分黑马 {blackhorse} 家；发现 {discovered} 家，纳入当日深查 {deep_checked} 家，"
                "反向匹配到岗位 {matched} 家，延后复核 {deferred} 家；风险标记 {risk_flags} 项，"
                "硬风险暂停 {hard_paused} 家。".format(
                    listed=growth.get("listed_tech", 0),
                    private=growth.get("private_tech", 0),
                    early=growth.get("early_team", 0),
                    blackhorse=growth.get("industry_blackhorse", 0),
                    discovered=growth.get("discovered", 0),
                    deep_checked=growth.get("deep_checked", 0),
                    matched=growth.get("matched_companies", 0),
                    deferred=growth.get("deferred", 0),
                    risk_flags=growth.get("risk_flags_total", 0),
                    hard_paused=growth.get("hard_risk_paused", 0),
                )
            )
            deferred = growth.get("deferred_companies", [])
            if deferred:
                lines.append(f"- 未完成本日中央深查、延后复核：{'、'.join(deferred)}。")
            limited = growth.get("deferred_by_daily_limit_companies", [])
            if limited:
                lines.append(f"- 其中受每日12家公司深查上限约束：{'、'.join(limited)}。")

    if company_watch is not None:
        stats = company_watch.get("stats", {}) if isinstance(company_watch, dict) else {}
        watch_companies = company_watch.get("companies", []) if isinstance(company_watch, dict) else []
        lines.append("")
        lines.append("## 高风险高成长公司增量层")
        lines.append(
            "本轮纳入观察池：{discovered} | 深入复核：{deep_checked} | 新增观察：{new_watch_companies} | "
            "取得匹配岗位：{matched_jobs}".format(
                discovered=stats.get("discovered", 0),
                deep_checked=stats.get("deep_checked", 0),
                new_watch_companies=stats.get("new_watch_companies", 0),
                matched_jobs=stats.get("matched_jobs", 0),
            )
        )
        lines.append(
            "暂无匹配岗位：{no_matching_jobs} | 职责不完整：{incomplete_job_details} | "
            "访问受限：{access_restricted} | 暂停关注：{paused}".format(
                no_matching_jobs=stats.get("no_matching_jobs", 0),
                incomplete_job_details=stats.get("incomplete_job_details", 0),
                access_restricted=stats.get("access_restricted", 0),
                paused=stats.get("paused", 0),
            )
        )
        newly_seen = [item for item in watch_companies if item.get("first_seen") == str(today)]
        if newly_seen:
            lines.append("")
            lines.append("### 本轮最值得关注的新公司及证据")
            for item in newly_seen[:10]:
                score = item.get("growth_score", "未评分")
                confidence = item.get("confidence", "未注明")
                status = item.get("job_search_status", "待反向查岗")
                lines.append(
                    f"- **{item.get('company', '')}** — {item.get('industry', '行业未注明')} · "
                    f"成长分 {score} · 可信度 {confidence} · {status}"
                )
                thesis = str(item.get("growth_thesis", "")).strip()
                if thesis:
                    lines.append(f"  - 判断：{thesis}")
                evidence = item.get("evidence", [])
                for proof in evidence[:3] if isinstance(evidence, list) else []:
                    if not isinstance(proof, dict):
                        continue
                    summary = str(proof.get("summary", "")).strip()
                    source_url = str(proof.get("source_url", "")).strip()
                    published_at = str(proof.get("published_at", "")).strip()
                    suffix = f"（{published_at}）" if published_at else ""
                    if summary and source_url:
                        lines.append(f"  - 证据{suffix}：{summary} · [来源]({source_url})")
                    elif summary:
                        lines.append(f"  - 证据{suffix}：{summary}")
                risks = [str(value).strip() for value in item.get("risk_flags", []) if str(value).strip()]
                if risks:
                    lines.append(f"  - 风险：{'；'.join(risks[:4])}")
                access_reason = str(item.get("access_reason", "")).strip()
                next_action = str(item.get("next_action", "")).strip()
                if access_reason:
                    lines.append(f"  - 查岗限制：{access_reason}")
                if next_action:
                    lines.append(f"  - 下一步：{next_action}")
        else:
            lines.append("- 本轮没有新增高成长公司观察项；现有观察池继续保留并按计划复查。")
        lines.append("- 股价、融资和创始人财富只作为公司发现线索；没有通过官方岗位核实的公司不会进入岗位主表。")
    return "\n".join(lines).rstrip()


def cmd_render(args):
    new_postings = load_json(args.new, [])
    state = load_json(args.state, {"postings": {}})
    config = load_json(args.config, {})
    current_postings = load_json(args.current, None) if args.current else None
    company_watch = load_json(args.company_watch, {"companies": [], "stats": {}}) if args.company_watch else None
    source_coverage = load_json(args.source_coverage, {}) if args.source_coverage else None
    today = args.date or date.today().isoformat()
    season_label = config.get("target_season_label", "")
    category_label = config.get("job_category_label", "")
    rendered = render_markdown(
        new_postings,
        state,
        today,
        season_label,
        category_label,
        current_postings=current_postings,
        expired_count=args.expired,
        excel_status=args.excel_status,
        max_new=args.max_new,
        company_watch=company_watch,
        source_coverage=source_coverage,
    )
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)

    p_render = sub.add_parser("render")
    p_render.add_argument("--new", required=True)
    p_render.add_argument("--state", required=True)
    p_render.add_argument("--config", required=True)
    p_render.add_argument("--date")
    p_render.add_argument("--current")
    p_render.add_argument("--expired", type=int, default=0)
    p_render.add_argument("--excel-status", default="未提供")
    p_render.add_argument("--max-new", type=int, default=20)
    p_render.add_argument("--company-watch")
    p_render.add_argument("--source-coverage")
    p_render.add_argument("--output")
    p_render.set_defaults(func=cmd_render)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
