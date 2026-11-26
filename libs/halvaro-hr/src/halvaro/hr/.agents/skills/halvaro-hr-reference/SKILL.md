---
name: halvaro-hr-reference
description: Use when a task needs headcount or the organisation on a date, certificate validity and renewal, staffing and availability hours, a pay difference between women and men or a payroll aggregate, or the holder of a user name: the functions of halvaro-hr other than the holiday functions.
---
# Reference of the other functions of halvaro-hr

Fictional company, synthetic data. This skill belongs to the installed version of the package and was generated from its docstrings.

## When to use

A task asks who works where on a date, who holds which certificate, how many hours a person can work, how the pay of women compares with the pay of men, or who held a user name. Pay columns are restricted: the pay functions refuse a session without access.

## How to call

- Import from the package: `from halvaro.hr import <function>` (names in the table below).
- The library never reads data, files, credentials or the environment. Your app loads the tables and passes them in as DataFrames.
- A legal value is a fact read with `halvaro.core.fact(id)`; never type one. A policy value is a parameter with a proposed default: name the value you used.
- Errors are errors of the library (`FrameError` and its relatives) and name the column, key or value that is wrong. Fix the input, do not catch and ignore the error.
- A function that reads a source above Day 1 takes an optional keyword `context`; with it, a source above its stage is refused before the function runs.

## Functions

| Function | Use this when | Returns |
|---|---|---|
| [`adjusted_gap`](references/adjusted_gap.md) | Use this when you need the pay difference between women and men after taking tenure, legal entity and grade into account, with its standard error. | `dict[str, Any]` |
| [`allocation_hours`](references/allocation_hours.md) | Use this when you need the hours that each allocation stint stands for, split into the hours up to a date and the hours after it. | `pd.DataFrame` |
| [`allocation_load`](references/allocation_load.md) | Use this when you need to see how loaded each person is over time: the allocation percents of all projects added up per day, as segments of constant load. | `pd.DataFrame` |
| [`availability_hours`](references/availability_hours.md) | Use this when you need the hours each person can work in each period: employed working days of the region, less leave, times the fte, times the hours of a day. | `pd.DataFrame` |
| [`band_position`](references/band_position.md) | Use this when you want to see where each person's pay lies in the band of the grade, in the currency of the person's term. | `pd.DataFrame` |
| [`booked_renewals`](references/booked_renewals.md) | Use this when you need the seats booked on training courses that start after the release date, to see who will renew a certificate in time. | `pd.DataFrame` |
| [`build_username_index`](references/build_username_index.md) | Use this when you need one effective dated list of usernames and pool accounts with their holders. | `pd.DataFrame` |
| [`cert_intervals`](references/cert_intervals.md) | Use this when you check coverage for many projects and want to build the validity intervals of the certificates once. | `dict[tuple[str, str], list[tuple[Any, Any]]]` |
| [`cert_status_on`](references/cert_status_on.md) | Use this when you need the status of every certificate on a date, worked out from the dates and not read from the stored status. | `pd.DataFrame` |
| [`check_term_contiguity`](references/check_term_contiguity.md) | Use this when you check the employment term history of every person for gaps, overlaps and other breaks in the dating. | `pd.DataFrame` |
| [`controlled_work_audit`](references/controlled_work_audit.md) | Use this when you need the time entries and allocation days of controlled work that have no valid certificate on the day. | `ControlledAudit` |
| [`cover_candidates`](references/cover_candidates.md) | Use this when you need the people who could cover a qualification on a project that starts on a given day, with the reasons that make a candidate less plausible. | `pd.DataFrame` |
| [`coverage_gap`](references/coverage_gap.md) | Use this when you need, for each requirement of a minimum head count, how many people of a crew hold a valid certificate and are not on leave on a date, and when the gap closes. | `pd.DataFrame` |
| [`data_now`](references/data_now.md) | Use this when you need the date of the data release (the "now" of the data) and want to refuse a date after it. | `dt.date` |
| [`education_explained_share`](references/education_explained_share.md) | Use this when you want to know how much of the adjusted pay difference goes away once education is taken into account. | `dict[str, Any]` |
| [`education_level`](references/education_level.md) | Use this when you need the highest education level of each person from the education records. | `pd.Series` |
| [`executives_on`](references/executives_on.md) | Use this when you need the holders of named executive roles on the date of an org_on frame, and the roles that nobody holds. | `Executives` |
| [`experience_summary`](references/experience_summary.md) | Use this when you need the hours, projects, roles and lead flag of each person over a roster, ranked by hours. | `pd.DataFrame` |
| [`expiring`](references/expiring.md) | Use this when you need the valid certificates that expire soon, with the first booked renewal course after the date and the days a person would be without a valid certificate. | `pd.DataFrame` |
| [`expiry_report`](references/expiry_report.md) | Use this when you need the people whose certificate for a qualification runs out on a given date: whether each has a renewal course booked, the free seats, and who is on leave during the course. | `ExpiryReport` |
| [`gap_table`](references/gap_table.md) | Use this when you want the pay difference between women and men per department or per grade in one table, with a flag for each group and a ranking. | `pd.DataFrame` |
| [`handover_report`](references/handover_report.md) | Use this when you need, around each long leave, the allocations that ended or still run at its start, the people who replace the absent person on the project, and where the person returns. | `pd.DataFrame` |
| [`headcount_on`](references/headcount_on.md) | Use this when you need the number of active people and their full time equivalents on a date, by department, team or legal entity. | `pd.DataFrame` |
| [`intake_compa_by_grade`](references/intake_compa_by_grade.md) | Use this when you want to compare women and men hired from a given date in one department, grade by grade, on their position in the pay band. | `pd.DataFrame` |
| [`intake_pay_difference`](references/intake_pay_difference.md) | Use this when you want to know whether the women hired from an intake date are paid differently from the men and from the other women of the same department. | `dict[str, Any]` |
| [`org_on`](references/org_on.md) | Use this when you need one frame with each person on a date: term, employee, team, role, grade, department, country and calendar region. | `pd.DataFrame` |
| [`overlapping_usernames`](references/overlapping_usernames.md) | Use this when you want to check that no username was held by two holders on overlapping dates. | `list[str]` |
| [`pay_frame`](references/pay_frame.md) | Use this when you need the person frame on a date with the monthly full-time rate, tenure and position in the pay band; it is the input of every pay difference function. | `pd.DataFrame` |
| [`payroll_aggregate`](references/payroll_aggregate.md) | Use this when you need the gross pay of the employment terms per legal entity, cost centre, month and currency, without employee keys and without base salary, for the tie-out with finance. | `pd.DataFrame` |
| [`planned_vs_actual_hours`](references/planned_vs_actual_hours.md) | Use this when you need the plan hours of each project against the hours booked in time entries. | `pd.DataFrame` |
| [`project_crew`](references/project_crew.md) | Use this when you need the people on a project on a date: the allocations that cover the date, or the crew plan when the project has no allocation yet. | `pd.DataFrame` |
| [`project_requirements`](references/project_requirements.md) | Use this when you need the qualifications that a project must cover, from the requirements of its project, contract, project type and roles. | `pd.DataFrame` |
| [`raw_gap`](references/raw_gap.md) | Use this when you need the raw pay difference between women and men: how much less the women are paid on average, before any adjustment. | `float` |
| [`renewal_chains`](references/renewal_chains.md) | Use this when you need to see how certificates follow each other for a person and qualification: the chains of renewals, with lapses and overlaps. | `pd.DataFrame` |
| [`resolve_assignments`](references/resolve_assignments.md) | Use this when you check who holds each asset assignment: the person or team behind each username at the start of the assignment, and whether they still hold it until the end. | `Resolution` |
| [`resolve_username`](references/resolve_username.md) | Use this when you have a username or a pool account name and a date and need to know who held it. | `dict[str, Any] | None` |
| [`skill_latest`](references/skill_latest.md) | Use this when you need the latest rating of each person and skill, with the name of the skill. | `pd.DataFrame` |
| [`staffing_candidates`](references/staffing_candidates.md) | Use this when you want the experience ranking with the staffing status of each person on one or more dates. | `pd.DataFrame` |
| [`status_on`](references/status_on.md) | Use this when you need to know, for each person, whether they have left, are on leave, are not yet hired or are available on a date. | `pd.DataFrame` |
| [`suppress_small_cells`](references/suppress_small_cells.md) | Use this when you publish a gap table and must hide the values of groups that are too small. | `pd.DataFrame` |
| [`tenure_years`](references/tenure_years.md) | Use this when you need the years of service of each person on a date. | `pd.Series` |
| [`term_changes`](references/term_changes.md) | Use this when you need the events behind the employment terms: one row per name in the change reason of each term. | `pd.DataFrame` |
| [`terms_on`](references/terms_on.md) | Use this when you need the one employment term that is valid on a date for each person, without the restricted pay column. | `pd.DataFrame` |
| [`utilisation`](references/utilisation.md) | Use this when you need project hours over availability by team and by department, for the people who hold a project role. | `pd.DataFrame` |
| [`valid_on`](references/valid_on.md) | Use this when you need the certificates that are valid on a date, one row per person and qualification. | `pd.DataFrame` |
| [`with_education`](references/with_education.md) | Use this when you want the education level of each person next to the pay frame, so that it can be used as a control in the adjusted gap. | `pd.DataFrame` |

## Reference pages

- One page per function in `references/` (signature, rule, arguments, returns, errors, example, facts and sources).
- `references/flat.md`: every page in one file, for an agent that reads one file.
