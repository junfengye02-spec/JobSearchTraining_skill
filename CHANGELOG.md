# Changelog

## 2.0.0 - 2026-09-04

- Expand first-run discovery with direct 牛客校招 surfaces, up to eight aliases per role, larger candidate/page budgets, watch companies, and optional high-growth-company discovery.
- Require independent evidence for every planned query, entry URL, company enumeration, and official company audit before a search can be marked complete.
- Persist unfinished job leads and company audits across runs, invalidate legacy shallow-completion history, and keep automatic mode in `initial_full` until both retry queues are cleared.
- Create recurring job and interview automations before the long initial backfill so interrupted bootstrap runs still have a scheduled continuation.
- Add regression tests for shallow-report rejection, strict completion, persistent retries, automatic mode switching, and workspace v2 state.
