# Automation and task lifecycle

Use Codex app task and automation tools when available. If they are unavailable, keep the same workflow runnable manually and explain that scheduled delivery requires a supporting Codex surface.

## One-command startup

When the user says `开始skill`, perform setup immediately and end to end:

1. Initialize or inspect the current workspace.
2. Run job discovery before scheduling future refreshes. On first use, keep `initial_full` mode active until all source and role tasks pass; a small partial result is not completion.
3. Create or update both exact-name automations.
4. Create or reuse the current-period interview task, pin it, and ask its first question.
5. Return concrete created or reused task and automation results.

Do not ask for values already available in the resume, existing workbook, config, or environment. Only pause when the target role cannot be inferred because no readable resume or equivalent profile data exists.

## Initialize automations

1. Read the configured timezone, job refresh time, interview time, and task span.
2. Prefer at least 30 minutes between job refresh and interview. The default is 08:00 and 09:00.
3. Find existing automations by exact name before creating anything:
   - `Adaptive Interview Coach · Job Refresh`
   - `Adaptive Interview Coach · Daily Interview`
4. Update an existing automation instead of creating a duplicate.

## Job refresh automation

Create a project-scoped recurring local job. Its prompt must:

- Invoke `$adaptive-interview-coach` in unattended refresh mode.
- Read the current workspace config and latest resume.
- Generate and execute the four-source discovery plan from `job-discovery.md` without waiting for user input. `auto` must continue first-use full search until a completed `initial_full` run is recorded.
- Execute every configured role task, planned query, and pagination rule; never stop after the first result.
- Record role-level coverage with `discovery.py finalize`; never interpret shallow, blocked, or incomplete discovery as zero jobs or a completed refresh.
- Put only detail-verified, currently open, unexpired postings into the workbook; preserve unknown or closed items as leads.
- Merge jobs, rebuild the duty profile with today's new-job influence, safely deactivate, and export the one job workbook.
- Report counts even when nothing changed.

Do not attach job discovery to the interactive interview task; long searches should not clutter interview history.

## Interview task and automation

Create one normal project task for the current period, title it with the period number and date range, and pin it. The initial prompt must invoke `$adaptive-interview-coach`, load the latest resume and job workbook, state the one-question interview rules, and ask the first question.

Attach a daily proactive automation to that task. On each run:

- Continue an unresolved answer, explanation, or confirmation before starting a new question.
- Read current files again.
- Avoid repeating covered topics.
- Select a current duty-profile cluster and map it to the latest resume before creating a new question.
- Preserve the profile version, cluster, representative jobs, and resume evidence in follow-ups and weakness records.
- Ask only one main question.

## Rotate after the configured span

At the first scheduled run outside the current date range:

1. Summarize covered topics, scores, mastered weaknesses, and unresolved weaknesses from the old task and workbook.
2. Check whether the next exact task title already exists.
3. Create at most one new project task and include the inherited summary in its initial prompt.
4. Point the daily interview automation at the new task while preserving its schedule and status.
5. Pin the new task, then unpin and archive the old task.

The job workbook and weakness workbook remain in the workspace and are never rotated with tasks.

## Safety and idempotency

- Never hardcode automation IDs or task IDs in the Skill.
- Resolve IDs at runtime by exact names or returned tool results.
- Never create one interview task per day.
- Never archive the old task until the new task exists and the automation target is updated.
- If the previous question is unanswered, send a concise continuation prompt instead of stacking another question.
- Repeating `开始skill` must repair or reuse the workflow and must not reset job state, weakness history, or the current interview period.
