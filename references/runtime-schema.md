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

## Weakness upsert schema

Pass an object or array to `scripts/weaknesses.py upsert` with:

- `category`, `topic`, `source`, `weakness`.
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
