# Adaptive interview and teaching loop

## Build each question from current evidence

Before a new daily question:

1. Locate and read the latest resume using the configured patterns.
2. Read the active rows of the configured job workbook.
3. Read the current interview task history and weakness summary.
4. Prefer a highly matched job duty that has not been covered recently.
5. Blend that duty with resume evidence and one relevant foundational topic or current interview trend.

Do not ask a generic question when a concrete resume-to-duty question is available.

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

Upsert the weakness in the workbook during the explanation turn. Append a review record after the confirmation answer. Continue only after the user demonstrates understanding or explicitly confirms it.

## Scoring

- 0: no usable understanding.
- 1: isolated fragments.
- 2: correct headline without explanation.
- 3: explains the main mechanism.
- 4: connects mechanism, trade-offs, and project evidence.
- 5: handles boundaries, alternatives, failure cases, and follow-up variants.

Do not mark a weakness mastered merely because an explanation was shown.
