# Job discovery and workbook refresh

## Capability gate

Require at least one real public-web capability: web search plus page fetch, or an interactive browser that can open search results and job details. Before claiming there are no jobs, actually execute the source plan below.

If no web capability exists, record every source as `blocked`, run `scripts/discovery.py finalize`, report `岗位发现被阻塞`, and stop before merge. Never turn missing tools, login walls, CAPTCHAs, or network errors into an empty-job conclusion.

## Generate the source plan

Run:

```text
python "$SKILL_DIR/scripts/discovery.py" plan --workspace "$WORKSPACE" --mode auto --output "<plan.json>"
```

The plan substitutes the configured cohort, season, roles, internship choice, locations, and company preferences into four independent source groups.
It generates separate `role_tasks` for every configured role and includes that role's common job-title aliases. Never collapse multiple user-requested roles into one coverage item.

`auto` uses `initial_full` until history contains a successful first-use full search. That mode searches up to 50 relevant candidates per source, checks up to five result pages per query, and allows broader official verification. Only after all four sources and every role task pass coverage validation does `auto` switch to the smaller daily refresh plan.

## Four source groups

1. **牛客求职与校招**: search job-detail and discussion pages on `nowcoder.com`. Use discussions as leads, then open a job or official detail page for responsibilities.
2. **企业招聘公众号与官网**: discover verified recruitment announcements and follow them to official career sites or recruitment systems. Treat this as the strongest source for availability and duties.
3. **51job校园、智联校园、猎聘校园**: search `campus.51job.com`, `xiaoyuan.zhaopin.com`, and `campus.liepin.com` with the configured role and cohort.
4. **校招名单与实习僧**: use public recruitment roundups to discover newly recruiting companies and `shixiseng.com` for internships. Treat roundup content as a lead until verified.

Do not use BOSS直聘 or 拉勾 as routine sources because they commonly require login and trigger anti-automation controls. Use them only as an explicitly reported fallback when all four normal groups fail.

## Execute the source plan

When agent delegation is available, run the four source groups in parallel. Otherwise execute the same four groups sequentially in the current task. A source worker must not delegate to another worker.

For each source group:

- Execute every query in every `role_task`; do not stop after the first matching job.
- Open all public `entry_urls` in that role task, then use the generated queries for broader recall.
- Follow result pagination until the source ends, two consecutive pages add no relevant jobs, or the configured per-query page limit is reached.
- Preserve up to the mode's candidate limit per source. The limit is a safety boundary, not a completion signal; if it is reached, use `candidate_limit`, keep `exhausted=false`, and report coverage incomplete instead of truncating and claiming completion.
- Record role-level queries, URLs opened, whether pagination was exhausted, and the stop reason.
- Return `success`, `empty`, `blocked`, or `error`; distinguish empty results from inability to search.
- Return structured candidates with company, title, responsibilities, city, job type, enterprise tag, direction tags, matched canonical roles, highlight, verification, source platform, source URL, deadline, cohort, season, application status, current-availability evidence, and check time.
- Keep incomplete discoveries as leads. Do not invent responsibilities.
- Do not repeatedly retry the same inaccessible method.

For each canonical role, return one `role_coverage` entry. Mark `exhausted=true` only after reaching the actual end, the consecutive-no-new-page rule, or the configured page limit. Include every planned query in that entry's `queries`; missing even one planned query makes coverage incomplete.

Combine results into one report matching the schema emitted by `discovery.py plan`, then run:

```text
python "$SKILL_DIR/scripts/discovery.py" finalize --workspace "$WORKSPACE" \
  --input "<source-report.json>" --candidates-output "<candidates.json>" \
  --leads-output "<leads.json>" --status-output "<discovery-status.json>"
```

Exit code `2` means discovery is blocked, shallow, or incomplete. `jobs_found_incomplete` means usable jobs were found, but missing roles, planned queries, pages, or sources still require work. Preserve those jobs, continue the missing work, and finalize again. Do not report “搜索完成” or “没有岗位” in that state.

A zero-open-job conclusion is allowed only when all four source groups completed every role task with query, visited-page, exhaustion, and stop-reason evidence. One source worker returning `success` is not enough.

## Enrich and verify

Open incomplete leads and obtain responsibilities from a job-detail or official page. A workbook-ready job must meet all of these conditions:

- Complete, faithfully captured responsibilities.
- `application_status` is `open`.
- `availability_evidence` quotes a visible current signal, such as an active apply button, an official job currently listed, or an unexpired application window.
- `checked_at` records this run's check time.
- An explicit deadline has not passed.

Search snippets, roundup mentions, inaccessible pages, unknown status, and closed or expired jobs stay in the lead file. Update the source report and finalize again after enrichment.

For companies not previously seen, use the plan's verification allowance: larger during `initial_full`, smaller during `daily_refresh`. Replace aggregator links with official detail links when available. If an official page proves the cohort is wrong or the job is closed, reject or deactivate it. A failed verification attempt is not proof of closure.

## Filter, merge, profile, and export

Read [keyword-filters.md](keyword-filters.md), then:

1. Compare duties with the latest resume and fill match level, match reason, and skill gaps.
2. Run `scripts/jobs.py merge` to validate, filter, and deduplicate.
3. Recompute the duty profile from every active job, including current new job IDs, and run `scripts/jobs.py profile`.
4. Recheck active jobs and deactivate only with supported explicit evidence. Recompute the profile if the active set changes.
5. Run `scripts/jobs.py export` to rebuild the one workbook, including `岗位总表`, `职责画像`, `已失效岗位`, and `概览`.
6. Run `scripts/discovery.py report` and report discovery coverage plus new, rejected, deactivated, active, and duty-profile counts.

Maintain one `岗位总表.xlsx`; keep `岗位名称` and `岗位职责` as the first two columns, preserve clickable source links, show current application status/evidence/check time, and never create a fallback copy when Excel is locked.
