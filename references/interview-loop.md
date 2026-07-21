# Adaptive interview and teaching loop

## Build each question from current evidence

Before a new daily question:

1. Locate and read the latest resume using the configured patterns.
2. Read the current `职责画像`, regenerated from all active job responsibilities after the latest refresh.
3. Read the current interview task history and weakness summary.
4. Select a high-priority duty cluster not covered recently; consider `新增` and `上升` trends produced by today's new jobs.
5. Map the summarized duty to one resume project, skill claim, metric, missing capability, or known weakness.
6. Use foundational knowledge or a current interview trend only when it tests that duty-profile-to-resume relationship.

Do not ask a generic question when a concrete resume-to-duty-profile question is available. Keep an internal provenance tuple for every main question:

```text
profile generated_at + duty cluster/category + representative jobs + resume evidence or gap
```

Show a short `职责画像依据` line with the duty summary, coverage or priority, and representative jobs before the question. Do not show the answer.

When no profile can be built from verified active duties, never invent one. Trigger or await job refresh, use overdue weakness review first, and clearly label a resume-only fallback if a question is still required.

## Seven-day emphasis

- Day 1: resume project depth and personal contribution.
- Day 2: language fundamentals, runtime, and concurrency.
- Day 3: application framework, database, cache, messaging, and distributed systems.
- Day 4: AI application engineering, agents, retrieval, tools, evaluation, and safety.
- Day 5: algorithm reasoning and implementation in the configured language.
- Day 6: system design tied to a real target duty.
- Day 7: mixed pressure interview and unresolved weaknesses.

Adapt this sequence to the user's role. Ask one main question at a time and wait for the answer.

## Evaluate the answer

Probe for:

- Correct facts and causal reasoning.
- Trade-offs, boundaries, and failure cases.
- Evidence of personal contribution rather than team-level claims.
- Measurement method behind every numerical result.
- Code complexity, concurrency safety, data consistency, and operational behavior where relevant.

## Teach before continuing

When a weakness appears, stop new questions and follow this order:

1. Quote or identify the exact weak part of the answer.
2. State the correct conclusion.
3. Explain the intuition and underlying mechanism.
4. Connect it to the user's resume project or a concrete code/system example.
5. Provide a concise interview-ready answer structure and keywords.
6. Explain common follow-up traps.
7. Ask one confirmation question or request a restatement.

Upsert the weakness in the workbook during the explanation turn. Its source must include the duty profile version, cluster summary, representative jobs, and resume evidence or gap. Append a review record after the confirmation answer. Continue only after the user demonstrates understanding or explicitly confirms it.

## Scoring

- 0: no usable understanding.
- 1: isolated fragments.
- 2: correct headline without explanation.
- 3: explains the main mechanism.
- 4: connects mechanism, trade-offs, and project evidence.
- 5: handles boundaries, alternatives, failure cases, and follow-up variants.

Do not mark a weakness mastered merely because an explanation was shown.
