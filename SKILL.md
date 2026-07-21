---
name: adaptive-interview-coach
description: End-to-end job discovery and adaptive interview training that reads the latest resume, finds and verifies matching jobs, maintains one formatted job Excel workbook, asks duty-specific interview questions, teaches detected weaknesses before continuing, records mastery in a review Excel workbook, schedules daily runs, and rotates interview tasks after a configured number of days. Use when the user says "开始skill", "start skill", "start everything", or asks Codex to initialize or run a personal job-search pipeline, refresh campus or experienced-hire postings, create or update job and weakness spreadsheets, conduct resume-and-JD-based mock interviews, review weak knowledge areas, or manage the recurring interview task lifecycle.
---

# Adaptive Interview Coach

Run a private, workspace-scoped pipeline from job discovery through interview practice and spaced review. Keep the installed Skill immutable; generate all personal data at runtime in the user's selected workspace.

## Resolve paths

Set `SKILL_DIR` to the directory containing this `SKILL.md`. Resolve scripts and references relative to it. Set `WORKSPACE` to the project or directory chosen by the user.

Never hardcode a publisher path, username, resume name, automation ID, task ID, graduation year, role, city, or personal detail. Do not store runtime data inside `SKILL_DIR`.

This Skill is self-contained. Do not require another Skill for browsing, spreadsheet creation, job tracking, or interviewing.

## Route the request

- For “开始skill”, “start skill”, or an equivalent request, follow **One-command bootstrap** and complete the workflow end to end in the same turn.
- For first use or “set this up,” follow **Initialize the workspace**, then **Create the recurring workflow**.
- For “find jobs,” “refresh jobs,” or an unattended job automation, follow **Refresh jobs**.
- For “interview me” or a daily interview automation, follow **Run the interview loop**.
- For an answer that exposes a weakness, follow **Teach and record weaknesses** before asking anything new.
- For status questions, run the status and summary commands without mutating data.

## One-command bootstrap

Treat `开始skill` as authorization to complete all reversible, workspace-local setup and supported Codex task/automation creation. Do not stop after explaining the workflow or presenting a plan.

1. Use the current project root as `WORKSPACE` unless the user already selected another directory.
2. Look for an existing config. If it exists, preserve it and repair only missing workbooks, tasks, or automations.
3. Locate the latest readable resume. Also inspect an existing job workbook when present.
4. Infer the initial profile from those files:
   - graduation cohort or experienced-hire status from education and dates;
   - role directions and programming language from projects, experience, skills, and existing job duties;
   - include internships when the resume clearly represents a current student or target graduate;
   - reuse explicit location and organization preferences from existing files; otherwise search nationwide without inventing a preferred city;
   - infer the current recruitment season conservatively, leaving uncertain labels empty rather than fabricating them.
5. Derive positive, fuzzy, and negative keywords, then run **Initialize the workspace** without asking the user to repeat information already present in the files.
6. Immediately run one **Refresh jobs** cycle. If a web source is unavailable, continue with other sources and do not block the remaining setup.
7. Run **Create the recurring workflow**: create or update the job refresh automation, create and pin the current interview task, attach the daily interview automation, and ask the first question in that task.
8. Finish with the generated file paths, automation times, interview task identity, and job refresh counts.

Ask a blocking question only when no readable resume exists and neither an existing config nor job workbook provides enough information to determine a target role. In that case, ask the user to add or identify a resume, then resume this bootstrap from the interrupted step.

Make this operation idempotent. Repeating `开始skill` must update or reuse exact-name automations and the current-period task, not create duplicates or erase state.

## Initialize the workspace

Read [runtime-schema.md](references/runtime-schema.md) and [automation-setup.md](references/automation-setup.md).

1. Check whether `WORKSPACE/.adaptive-interview-coach/config.json` exists.
2. If it does not exist in an interactive task, first infer the essential profile from the latest resume and existing job workbook. Ask only for values that cannot be inferred safely:
   - target graduation cohort or experienced-hire status;
   - target season;
   - role directions in plain language;
   - whether to include internships;
   - preferred locations and organization types.
3. Default the timezone from the user's environment, job refresh to 08:00, interview to 09:00, and task span to 7 days unless the user specifies otherwise.
4. Derive concise positive, fuzzy, and negative job keywords from the role directions. Do not make the user enumerate technical synonyms.
5. Run `scripts/workspace.py init` with the collected values. Quote every path and repeat multi-value flags as needed.

Example shape:

```text
python "$SKILL_DIR/scripts/workspace.py" init --workspace "$WORKSPACE" \
  --grad-year "<cohort>" --season "<season>" \
  --role "<role>" --location "<location>" \
  --positive-keyword "<keyword>" --fuzzy-keyword "<keyword>" \
  --negative-keyword "<keyword>" --include-internships
```

Omit `--include-internships` when not selected. Never use `--force` unless the user explicitly authorizes replacing an existing configuration.

If initialization is requested by an unattended automation and no config exists, stop and report that one interactive initialization or `开始skill` run is required. Do not guess a career profile in an unattended task.

After initialization, confirm that the one job workbook and one weakness workbook exist. If `openpyxl` is missing, install that dependency in the user's Python environment or an isolated runtime directory, then retry; do not copy third-party source code into the Skill.

## Refresh jobs

Read [job-discovery.md](references/job-discovery.md) and [runtime-schema.md](references/runtime-schema.md).

1. Run workspace status and locate the latest resume on every refresh:

```text
python "$SKILL_DIR/scripts/workspace.py" status --workspace "$WORKSPACE"
```

2. Read the resume and config before searching. Use currently available web or browser tools to inspect public sources. Prefer official job details and verify aggregator leads. Do not depend on subagents.
3. Collect complete job responsibilities and normalize each result to the candidate schema. Do not invent missing responsibilities; exclude those records from the main workbook.
4. Compare every candidate's duties with the latest resume. Fill `match_level`, `match_reason`, and `skill_gaps` with concrete evidence.
5. Save candidates under `WORKSPACE/.adaptive-interview-coach/tmp/`, then merge:

```text
python "$SKILL_DIR/scripts/jobs.py" merge --workspace "$WORKSPACE" \
  --input "<candidates.json>" --new-output "<new.json>" \
  --rejected-output "<rejected.json>"
```

6. Recheck active jobs. Deactivate only when an official deadline has passed, the job is explicitly closed/removed, the page returns 404/410, or an authoritative source proves it no longer exists. Temporary network errors, authentication, CAPTCHAs, throttling, and ambiguity are not evidence. Use:

```text
python "$SKILL_DIR/scripts/jobs.py" deactivate --workspace "$WORKSPACE" --input "<deactivations.json>"
```

7. Rebuild the configured workbook in place:

```text
python "$SKILL_DIR/scripts/jobs.py" export --workspace "$WORKSPACE"
```

Do not create dated workbook copies. If Excel locks the workbook, leave state intact, report that export is pending, and retry on the next run.

Always report new, deactivated, rejected, and active totals, including a normal zero-change report.

## Run the interview loop

Read [interview-loop.md](references/interview-loop.md).

Before each new question:

1. Re-read the latest resume.
2. Read active jobs from the configured job workbook or job state.
3. Read recent task history and weakness status.
4. If a prior answer, explanation, or confirmation is incomplete, continue it instead of asking a new main question.
5. Otherwise select one high-value duty from a highly matched job and connect it to resume evidence, foundational knowledge, algorithms, system design, or a recent public interview trend.

Ask exactly one main question. Do not show the answer before the user responds. Adapt follow-ups to distinguish familiarity from real understanding, including personal contribution, trade-offs, failure modes, measurement methods, complexity, and boundaries.

Use the configured programming language when present; otherwise infer it from the resume or ask once.

## Teach and record weaknesses

When an answer reveals a real weakness, stop the question sequence.

1. Prepare a complete weakness JSON object using [runtime-schema.md](references/runtime-schema.md).
2. Upsert it during the same turn in which the explanation is delivered:

```text
python "$SKILL_DIR/scripts/weaknesses.py" upsert --workspace "$WORKSPACE" --input "<weakness.json>"
```

3. Explain in this order:
   - the exact weak statement or omission;
   - the correct conclusion;
   - intuition and underlying mechanism;
   - a resume-project, code, or system example;
   - an interview-ready answer structure and keywords;
   - common follow-up traps;
   - one confirmation question or restatement request.
4. Do not continue until the user demonstrates understanding or explicitly confirms it.
5. After the confirmation answer, append review history and update mastery:

```text
python "$SKILL_DIR/scripts/weaknesses.py" review --workspace "$WORKSPACE" --input "<review.json>"
```

Do not mark a weakness mastered merely because the explanation was shown. If the workbook is locked, the script queues the update; tell the user it is pending and run `weaknesses.py flush` before the next new question.

At the start of a session, prioritize overdue unresolved weaknesses when relevant to the target job duties.

## Create the recurring workflow

Read [automation-setup.md](references/automation-setup.md) completely before creating or updating tasks and automations.

When task and automation tools are available:

1. Create or update one project-scoped job refresh automation using the configured refresh time.
2. Create the current interactive interview task, ask its first question, title it with its period and date range, and pin it.
3. Create or update one daily interview automation targeted at that task using the configured interview time.
4. On the first run outside the configured task span, create the next task, carry forward covered topics and unresolved weaknesses, retarget the interview automation, then archive the old task.

During **One-command bootstrap**, execute all four actions now. Do not merely describe commands the user could run later.

Resolve existing automation and task IDs at runtime. Never embed IDs in the Skill or create duplicates with the same exact name.

When scheduling tools are unavailable, finish workspace initialization and provide the exact manual refresh and interview invocation. Do not claim that a schedule was created.

## Preserve privacy and integrity

- Do not copy resumes, job records, weakness records, local paths, or task history into the Skill directory.
- Do not add author identities or personal metadata to generated runtime files unless the user explicitly requests it.
- Preserve user edits in the weakness workbook. Rebuild the job workbook only from its canonical job state.
- Treat public job and interview information as external evidence, not bundled Skill content.
- Do not fabricate job availability, responsibilities, deadlines, interview trends, scores, or mastery.
- Keep the main job sheet's first two columns as `岗位名称` and `岗位职责`.

## Inspect status

Use read-only commands when the user asks for status:

```text
python "$SKILL_DIR/scripts/workspace.py" status --workspace "$WORKSPACE"
python "$SKILL_DIR/scripts/jobs.py" summary --workspace "$WORKSPACE"
python "$SKILL_DIR/scripts/weaknesses.py" summary --workspace "$WORKSPACE"
```
