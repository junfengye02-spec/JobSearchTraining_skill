# Job discovery and workbook refresh

## Source priority

Use current, publicly accessible sources in this order:

1. The employer's official careers site or campus recruitment system.
2. The employer's verified public recruitment announcement linking to the official application page.
3. Reputable job-platform detail pages.
4. Public recruitment roundups only as discovery leads; verify them before assigning high confidence.

Prefer direct job-detail URLs over home pages or search result pages. Avoid repeatedly retrying one inaccessible source. Do not require a signed-in personal account when a public alternative exists.

## Refresh sequence

1. Read `.adaptive-interview-coach/config.json` and the latest resume before searching.
2. Search the configured cohort, season, role directions, locations, company types, and internship preference.
3. Capture responsibilities from the source. Reject a candidate from the main workbook when duties cannot be obtained.
4. Normalize each candidate to the schema in `runtime-schema.md`.
5. Compare duties with the latest resume and fill `match_level`, `match_reason`, and `skill_gaps` with evidence, not generic praise.
6. Write candidates to a temporary JSON file inside `.adaptive-interview-coach/tmp/`.
7. Run `scripts/jobs.py merge` to filter and deduplicate.
8. Recompute the duty profile from every active job. Include current new job IDs, cluster similar requirements, map clusters to the latest resume, and run `scripts/jobs.py profile`.
9. Recheck existing active jobs. Deactivate only records with supported explicit evidence. If deactivation changes the active set, recompute the profile again.
10. Run `scripts/jobs.py export` to rebuild the one configured job workbook, including its `职责画像` sheet, in place.
11. Report new, deactivated, rejected, active, and duty-profile cluster totals even when no new jobs were found.

## Matching guidance

Evaluate duties against resume evidence across:

- Required language, framework, database, middleware, AI, or platform skills.
- Project depth: personal contribution, design decisions, measurement, failure handling, and production exposure.
- Domain relevance and transferable experience.
- Graduation cohort, job type, location, and organization preferences.

Use `高度匹配` only when multiple important duties have direct resume evidence. Use `待确认` when the source or resume evidence is incomplete.

## Workbook guarantees

- Maintain one `岗位总表.xlsx` unless the user configured another filename.
- Keep `岗位名称` and `岗位职责` as the first two columns of the main sheet.
- Rebuild `职责画像` from all active duties after every refresh; let today's new jobs change its coverage, priority, and trend.
- Keep active and deactivated jobs auditable in separate sheets.
- Preserve clickable source links.
- Never create a fallback copy when Excel has locked the workbook. Report the lock and retry on the next run.
