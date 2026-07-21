# Job filtering rules

Keep role-specific words in `.adaptive-interview-coach/config.json`. Apply filters only after collecting source results so discovery remains recall-oriented.

## Direction

- Keep a record that matches any positive keyword.
- Keep a record that matches only fuzzy keywords and suffix its title with `[方向待确认]`.
- Use negative keywords only when there is no positive match.
- Reject a record that matches neither positive nor fuzzy keywords when positive filters are configured.

## Internship and formal hiring

When `include_internships` is false, reject titles or duties containing internship signals, including convertible internships. When it is true, keep internships and preserve the exact job type.

Treat campus recruitment, graduate, full-time, and explicit cohort language as formal-hiring evidence. A formal signal does not override the user's decision to exclude internships.

## Cohort

Reject a posting that explicitly targets a cohort earlier than the configured graduation year. Keep an otherwise matching posting whose cohort is unspecified, but mark verification accordingly.

## Geography

Do not hard-filter geography unless the user explicitly configured a strict limit. Preserve the source city and use location preferences for ranking.

## Missing duties

Keep a posting without responsibilities only in the lead file. It cannot enter the main job workbook until a job-detail or official page provides duties.

## Current application availability

Keep a posting in the main workbook only when its detail or official page currently shows that applications are open. Require an open status, visible evidence, and this run's check time. An expired deadline, closed listing, search snippet, roundup-only mention, inaccessible detail, or unknown availability remains a lead.
