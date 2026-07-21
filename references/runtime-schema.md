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
    ├── state/pending-weakness-updates.json
    └── tmp/
```

Never write resumes, job results, weakness records, thread IDs, automation IDs, or personal information into the Skill directory.

## Discovery report schema

Generate a discovery plan with `scripts/discovery.py plan`. After executing its four source groups, create a report containing:

- `run_id`: copied from the plan.
- `sources`: one result for every planned source group.

Each source result contains:

- `id`: `nowcoder`, `official`, `campus_platforms`, or `roundups_and_internships`.
- `status`: `success`, `empty`, `blocked`, or `error`.
- `queries`: actual queries executed.
- `pages_checked`: URLs actually opened.
- `error`: required when blocked or failed.
- `candidates`: discovered candidate objects.

For `success` and `empty`, both `queries` and `pages_checked` must be non-empty. Finalize the report with `scripts/discovery.py finalize`. It writes only responsibility-complete records to the candidate file, keeps incomplete records in the lead file, records source coverage, and permits a zero-job conclusion only after enough source groups completed real searches.

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
- `highlight`: concise factual highlight.
- `verification`: `官方招聘页`, `招聘平台职位页`, `公开公告`, or `待核实`.
- `deadline`: ISO date when explicit; otherwise empty.
- `grad_year`: target graduation cohort when explicit.
- `season`: recruitment season label.
- `match_level`: `高度匹配`, `较高匹配`, `相近方向`, `待评估`, or `待确认`.
- `match_reason`: resume-to-duty evidence.
- `skill_gaps`: concrete missing or weak capabilities inferred from the resume.

The merge script rejects records missing company, title, responsibilities, or source URL.

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
