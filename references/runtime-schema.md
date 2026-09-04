# Runtime layout and schemas

Keep user data outside the installed Skill. Resolve every relative path from the user's selected workspace.

## Workspace layout

```text
user-workspace/
├── latest resume files
├── 岗位总表.xlsx
├── 面试薄弱点复习表.xlsx
└── .adaptive-interview-coach/
    ├── config.json
    ├── state/jobs.json
    ├── state/discovery-runs.json
    ├── state/pending-job-leads.json
    ├── state/company-audit.json
    ├── state/pending-weakness-updates.json
    └── tmp/
```

Never write resumes, job results, weakness records, thread IDs, automation IDs, or personal information into the Skill directory.

## Discovery report schema

Generate a discovery plan with `scripts/discovery.py plan`. After executing its four source groups, create a report containing:

- `run_id`: copied from the plan.
- `mode`: copied from the plan: `initial_full` or `daily_refresh`.
- `sources`: one result for every planned source group.

Each source result contains:

- `id`: `nowcoder`, `official`, `campus_platforms`, or `roundups_and_internships`.
- `status`: `success`, `empty`, `blocked`, or `error`.
- `role_coverage`: one result for every canonical role in that source's plan.
- `entry_runs`: one result for every exact public entry URL in that source's plan.
- `enumeration_complete` and `enumerated_companies`: required for 牛客 company enumeration.
- `company_audits`: official-search evidence for every enumerated, watched, retry, or candidate company.
- `error`: required when blocked or failed.
- `candidates`: discovered candidate objects.

Each `role_coverage` item contains:

- `role`: the exact canonical role from the plan.
- `status`: `success`, `empty`, `blocked`, or `error`.
- `query_runs`: one object for every exact planned query. Each object contains `query`, `status`, `pages_checked`, `exhausted`, `stop_reason`, and an `error` when blocked or failed.
- A query run's `exhausted` is true only after the source end, consecutive-no-new-page rule, or configured page limit.
- A query run's `stop_reason` is `end`, `consecutive_no_new`, `page_limit`, `candidate_limit`, `blocked`, or `error`. `candidate_limit` is incomplete and must never be reported as exhausted coverage.
- `error`: required for blocked or failed role searches.

Each `entry_runs` item contains `url`, `status`, `checked_at`, `evidence`, and `error` when needed. Each `company_audits` item contains `company`, `status`, `official_search_attempted`, exact `queries`, `pages_checked`, `checked_at`, and `error` when needed. Only `verified` and `no_match` are complete audit statuses.

Finalize with `scripts/discovery.py finalize`. Missing roles, independent query evidence, entries, pages, exhaustion, company enumeration, company audits, or stop reasons make the run incomplete even when candidates were found. The script writes only complete and currently open records to the candidate file, persists the rest in the lead and company-audit state files, and permits a zero-open-job conclusion only after all four sources and all persistent retries complete. Aggregate legacy fields do not satisfy schema version 2.

To resolve a pending non-ready lead, add a `lead_resolutions` array to the report. Each item requires the exact `lead_key` from the retry queue, `resolution` equal to `closed`, `duplicate`, or `irrelevant`, current `evidence`, and a timezone-aware ISO-8601 `checked_at`. A bare key cannot delete a lead. The resolution is retained as a tombstone so the same stale lead cannot reappear; a future candidate with complete duties and current-open evidence can still become ready and re-enter through the normal merge path. Ready candidates resolve their matching pending lead automatically.

## Candidate job schema

Each discovered candidate passed to `scripts/jobs.py merge` is a JSON object with:

- `company`: required company name.
- `title`: required job title.
- `responsibilities`: required verbatim or faithfully condensed responsibilities. Do not invent missing duties.
- `source_url`: required direct source URL.
- `source_platform`: source or channel label.
- `city`: location, or `未注明`.
- `job_type`: campus hire, internship, convertible internship, or another explicit type.
- `enterprise_tag`: optional organization category.
- `direction_tags`: string or list of role directions.
- `matched_roles`: required canonical role names from the configured target roles.
- `highlight`: concise factual highlight.
- `verification`: `官方招聘页`, `招聘平台职位页`, `公开公告`, or `待核实`.
- `deadline`: ISO date when explicit; otherwise empty.
- `application_status`: required `open` for workbook-ready records.
- `availability_evidence`: required current page evidence, such as an active apply button or official open listing.
- `checked_at`: required timestamp from the current discovery run.
- `grad_year`: target graduation cohort when explicit.
- `season`: recruitment season label.
- `match_level`: `高度匹配`, `较高匹配`, `相近方向`, `待评估`, or `待确认`.
- `match_reason`: resume-to-duty evidence.
- `skill_gaps`: concrete missing or weak capabilities inferred from the resume.

The merge script rejects records missing company, title, responsibilities, source URL, open application status, availability evidence, or check time. It also rejects expired deadlines.

## Deactivation schema

Pass an array to `scripts/jobs.py deactivate`. Each item contains a job identifier or company/title pair plus:

- `reason`: one of `deadline_passed`, `removed`, `closed`, `http_404`, `http_410`, `not_found`.
- `evidence`: the explicit page text, status code, or dated fact that proves deactivation.

Temporary errors, authentication walls, rate limits, CAPTCHAs, timeouts, and ambiguous pages are not deactivation evidence.

## Duty profile schema

After every job merge, summarize all active responsibilities and pass one JSON object to `scripts/jobs.py profile`:

- `new_job_ids`: job IDs discovered in the current refresh. These drive daily change explanations.
- `clusters`: semantically grouped responsibility requirements.

Each cluster contains:

- `category`: stable capability category.
- `summary`: faithful normalized summary of related responsibilities.
- `frequency`: number of active jobs containing this requirement.
- `priority`: interview priority based on frequency, match, and role importance.
- `keywords`: representative technologies and concepts.
- `companies`: representative companies.
- `representative_job_ids` or `representative_jobs`: traceable examples.
- `resume_evidence`: current resume evidence meeting the summarized duty.
- `resume_gap`: missing, weak, or unverified evidence.
- `new_job_influence`: how today's new jobs changed this cluster.

The script calculates coverage and compares the previous snapshot to mark clusters `新增`, `上升`, `稳定`, or `下降`. Recompute from the full active set every day instead of appending only new duties.

## Weakness upsert schema

Pass an object or array to `scripts/weaknesses.py upsert` with:

- `category`, `topic`, `source`, `weakness`. Format `source` with the duty profile generation time, cluster summary, representative jobs, and corresponding resume evidence or gap.
- `correct_conclusion`, `explanation`, `example`.
- `answer_framework`, `keywords`, `traps`.
- `confirmation_question`, `user_answer`.
- `status`, `mastery`, `next_review`.
- `period_day`, `task_title`, `notes`.

Use a stable canonical topic. The script deduplicates by normalized `category + topic`.

## Weakness review schema

Pass an object or array to `scripts/weaknesses.py review` with:

- `weakness_id`, or the same `category + topic` pair.
- `method`, `mastery_after`, `question`, `answer_summary`, `passed`.
- `review_date`, `next_review`, `period_day`, `task_title`, `notes`.

If `next_review` is omitted, the script schedules 0–2 points for the next day, 3–4 points for three days later, and 5 points for seven days later.
