# Job discovery and workbook refresh

## Capability gate

Require at least one real public-web capability: web search plus page fetch, or an interactive browser that can open search results and job details. Before claiming there are no jobs, actually execute the source plan below.

If no web capability exists, record every source as `blocked`, run `scripts/discovery.py finalize`, report `岗位发现被阻塞`, and stop before merge. Never turn missing tools, login walls, CAPTCHAs, or network errors into an empty-job conclusion.

## Generate the source plan

Run:

```text
python "$SKILL_DIR/scripts/discovery.py" plan --workspace "$WORKSPACE" --output "<plan.json>"
```

The plan substitutes the configured cohort, season, roles, internship choice, locations, and company preferences into four independent source groups.
It generates separate queries for every configured role instead of joining unrelated roles into one exact phrase. When `entry_urls` are present, open those public site-search pages first; this avoids depending on a general search engine for every source.

## Four source groups

1. **牛客求职与校招**: search job-detail and discussion pages on `nowcoder.com`. Use discussions as leads, then open a job or official detail page for responsibilities.
2. **企业招聘公众号与官网**: discover verified recruitment announcements and follow them to official career sites or recruitment systems. Treat this as the strongest source for availability and duties.
3. **51job校园、智联校园、猎聘校园**: search `campus.51job.com`, `xiaoyuan.zhaopin.com`, and `campus.liepin.com` with the configured role and cohort.
4. **校招名单与实习僧**: use public recruitment roundups to discover newly recruiting companies and `shixiseng.com` for internships. Treat roundup content as a lead until verified.

Do not use BOSS直聘 or 拉勾 as routine sources because they commonly require login and trigger anti-automation controls. Use them only as an explicitly reported fallback when all four normal groups fail.

## Execute the source plan

When agent delegation is available, run the four source groups in parallel. Otherwise execute the same four groups sequentially in the current task. A source worker must not delegate to another worker.

For each source group:

- Use its generated queries and available web/browser tools.
- Open public `entry_urls` first when provided, then use the generated queries for broader recall.
- Limit deep verification to the configured maximum, normally 10–15 relevant companies.
- Record the actual queries and URLs opened.
- Return `success`, `empty`, `blocked`, or `error`; distinguish empty results from inability to search.
- Return structured candidates with company, title, responsibilities, city, job type, enterprise tag, direction tags, highlight, verification, source platform, source URL, deadline, cohort, and season.
- Keep incomplete discoveries as leads. Do not invent responsibilities.
- Do not repeatedly retry the same inaccessible method.

Combine results into one report matching the schema emitted by `discovery.py plan`, then run:

```text
python "$SKILL_DIR/scripts/discovery.py" finalize --workspace "$WORKSPACE" \
  --input "<source-report.json>" --candidates-output "<candidates.json>" \
  --leads-output "<leads.json>" --status-output "<discovery-status.json>"
```

Exit code `2` means discovery is blocked or inconclusive. Do not report “没有岗位” in that case. A source marked `success` or `empty` must contain both an actual query and at least one visited page; otherwise finalization changes it to `error`. A zero-job conclusion is allowed only when at least the configured minimum number of source groups, normally three, completed with auditable `success` or `empty` evidence.

## Enrich and verify

Open incomplete leads and obtain responsibilities from a job-detail or official page. Update the source report and finalize again. Records without responsibilities remain outside the main workbook.

For companies not previously seen, verify up to five against official career sites. Replace aggregator links with official detail links when available. If an official page proves the cohort is wrong or the job is closed, reject or deactivate it. A failed verification attempt is not proof of closure.

## Filter, merge, profile, and export

Read [keyword-filters.md](keyword-filters.md), then:

1. Compare duties with the latest resume and fill match level, match reason, and skill gaps.
2. Run `scripts/jobs.py merge` to validate, filter, and deduplicate.
3. Recompute the duty profile from every active job, including current new job IDs, and run `scripts/jobs.py profile`.
4. Recheck active jobs and deactivate only with supported explicit evidence. Recompute the profile if the active set changes.
5. Run `scripts/jobs.py export` to rebuild the one workbook, including `岗位总表`, `职责画像`, `已失效岗位`, and `概览`.
6. Run `scripts/discovery.py report` and report discovery coverage plus new, rejected, deactivated, active, and duty-profile counts.

Maintain one `岗位总表.xlsx`; keep `岗位名称` and `岗位职责` as the first two columns, preserve clickable source links, and never create a fallback copy when Excel is locked.
