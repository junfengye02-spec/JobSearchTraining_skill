# Automation and task lifecycle

Use Codex app task and automation tools when available. If they are unavailable, keep the same workflow runnable manually and explain that scheduled delivery requires a supporting Codex surface.

## One-command startup

When the user says `开始skill`, perform setup immediately and end to end:

1. Initialize or inspect the current workspace.
2. Detect whether this Codex surface exposes task and automation creation. If it does, create or update the exact-name job refresh automation immediately, before the long first search.
3. Create or reuse the current-period interview task, pin it, then create or update the exact-name daily interview automation and attach it to that task. Defer its first question until step 5.
4. Run job discovery. On first use, keep `initial_full` mode active until all per-query, per-entry, company-audit, source, and role checks pass and the persistent retry queues are empty; a small partial result is not completion. If this turn is interrupted, the already-created job automation continues the same `initial_full` backlog.
5. Ask the first interview question using the latest available duty profile, then return concrete created or reused task and automation results plus any pending discovery work.

Do not ask for values already available in the resume, existing workbook, config, or environment. Only pause when the target role cannot be inferred because no readable resume or equivalent profile data exists.

Skill installation has no startup side effects. Do not claim automations exist merely because the repository was installed. The user must start the Skill, either explicitly (recommended: `$adaptive-interview-coach 开始skill`) or with an equivalent natural-language request, on a Codex desktop or web surface with scheduling tools. CLI or IDE use may initialize files and run manual refreshes, but must report scheduling as unavailable when those tools are absent.

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
- Fill independent `query_runs`, `entry_runs`, complete 牛客 company enumeration, and official `company_audits`; retry everything exposed by the plan's persistent `retry_queue`.
- Put only detail-verified, currently open, unexpired postings into the workbook; preserve unknown/inaccessible items as leads and resolve authoritatively closed or expired leads with structured evidence.
- Merge jobs, rebuild the duty profile with today's new-job influence, safely deactivate, and export the one job workbook.
- Report counts even when nothing changed.

Do not attach job discovery to the interactive interview task; long searches should not clutter interview history.

## Interview task and automation

Create one normal project task for the current period, title it with the period number and date range, and pin it. Its prompt must invoke `$adaptive-interview-coach`, load the latest resume and job workbook, and state the one-question interview rules. During one-command bootstrap, use a setup-only initial prompt that explicitly waits without asking a question; after the first refresh attempt, send a follow-up asking the first question from the latest available duty profile. Outside bootstrap, the initial prompt may ask the first question immediately.

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
