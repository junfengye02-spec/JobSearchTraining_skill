# Company discovery and official audits

Use company discovery to increase recall without lowering the evidence standard for workbook-ready jobs.

## Required company set

Audit all of these companies during `initial_full`:

1. Every company visible after exhausting the direct 牛客校招日程、校招推荐 and岗位搜索 surfaces.
2. Every company named by the user in `profile.watch_companies`.
3. Every company attached to a candidate from any of the four source groups.
4. Every unfinished company from the previous plan's `retry_queue.pending_company_audits`.

Do not sample or cap the 牛客 company enumeration. A safety limit may pause the run, but then set `enumeration_complete=false`, persist every company audit already discovered, and keep the search in `initial_full` mode so the next run restarts and completes enumeration.

## Official verification

For each company, search the official career domain, official recruitment account announcement, and the company's recruiting-system pages with the configured cohort, season, and every canonical role plus its aliases. Record:

- the exact company-specific queries;
- the official or search pages actually opened;
- check time;
- `verified` when a matching current recruiting surface was found;
- `no_match` only after the planned official search completed without a matching current role;
- `deferred`, `blocked`, or `error` when work remains.

A company audit is discovery evidence, not automatically a job candidate. Add a job only after its detail page supplies complete duties and current-open evidence.

## Optional high-growth expansion

Run this expansion only when `profile.include_high_growth_companies` is true. It is additive to the four required source groups and must not replace them.

Discover companies from current, public funding announcements, recognized growth-company lists, incubator or accelerator portfolios, and product launches. Require at least two independent signals before prioritizing an unfamiliar company: one company-growth signal and one current hiring signal. Store the supporting URLs and dates in the audit record. Never describe a company as high-growth from reputation alone.

Use the same official verification and job-readiness rules. If the expansion hits time or access limits, persist its companies for a later run; do not let optional expansion make a completed required four-source run appear empty or erase verified jobs.
