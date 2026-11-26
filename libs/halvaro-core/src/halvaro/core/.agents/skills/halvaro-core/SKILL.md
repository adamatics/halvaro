---
name: halvaro-core
description: Use when a task needs a typed key, a period, a fact with its status, the working days of a region, the stage or access guard, a join with an orphan report, or the money and number rounding of Halvaro: the functions of halvaro-core.
---
# halvaro-core: keys, periods, facts, stage and access, calendar, money

Fictional company, synthetic data. This skill belongs to the installed version of the package and was generated from its docstrings.

## When to use

A task parses or checks a key or a period, reads a legal or policy value as a fact, counts working days, guards a stage or a restricted column, joins frames and reports the keys without a partner, or rounds and formats money. Check this list before you write the logic yourself.

## How to call

- Import from the package: `from halvaro.core import <function>` (names in the table below).
- The library never reads data, files, credentials or the environment. Your app loads the tables and passes them in as DataFrames.
- A legal value is a fact read with `halvaro.core.fact(id)`; never type one. A policy value is a parameter with a proposed default: name the value you used.
- Errors are errors of the library (`FrameError` and its relatives) and name the column, key or value that is wrong. Fix the input, do not catch and ignore the error.
- Functions of the access module take a `Context` (stage and role). A source above the stage is refused with `StageRefusal`, a restricted column with `RestrictedColumnRefusal`.

## Functions

| Function | Use this when | Returns |
|---|---|---|
| [`add_months`](references/add_months.md) | Use this when you need the period a number of months after, or before, a period. | `str` |
| [`add_working_days`](references/add_working_days.md) | Use this when you need the date that is a number of working days from a start date, the start date counting as the first when it is a working day. | `dt.date` |
| [`apply_theme`](references/apply_theme.md) | Use this when you need a chart to carry the colours and font of the light or dark theme. | `Any` |
| [`asof_join`](references/asof_join.md) | Use this when you need to attach to each row the version of an effective dated table that was valid on the row's date. | `pd.DataFrame` |
| [`asof_stable`](references/asof_stable.md) | Use this when you need to prove that a result as of a date does not change when a later data release is loaded, except for rows that an effective dated change may alter. | `bool` |
| [`assert_aggregate`](references/assert_aggregate.md) | Use this when a frame holds an aggregate of a restricted measure (pay, birth date) and you must check that it names no person and has no group that is too small. | `None` |
| [`caption`](references/caption.md) | Use this when a figure or a table needs the basis and as-of line under it. | `str` |
| [`cfg`](references/cfg.md) | Use this when you know the config file and the key path of a value but not its fact id. | `Fact` |
| [`check_contiguity`](references/check_contiguity.md) | Use this when a table has effective dating (valid_from, valid_to per key) and you need the rows that break the dating rules. | `pd.DataFrame` |
| [`check_key_column`](references/check_key_column.md) | Use this when you need to check that every value of a key column is a well formed key, and optionally that its prefix is one the dictionary allows for that column. | `pd.DataFrame` |
| [`check_org_integrity`](references/check_org_integrity.md) | Use this when you need to check the organisation frames for broken references, missing leads and cost centres, and wrong counts. | `pd.DataFrame` |
| [`check_polymorphic`](references/check_polymorphic.md) | Use this when a key column can hold keys of different kinds and a type column says which kind each row has, and you need the rows where the two disagree. | `pd.DataFrame` |
| [`column_prefixes`](references/column_prefixes.md) | Use this when you need the key prefixes that a column of the data dictionary may hold, taken from its foreign key target. | `tuple[str, ...]` |
| [`combine_status`](references/combine_status.md) | Use this when a result rests on several facts and needs one status for its envelope. | `str` |
| [`compare_periods`](references/compare_periods.md) | Use this when you need to order two periods written YYYY-MM. | `int` |
| [`convert`](references/convert.md) | Use this when you move whole cents between DKK, EUR and SEK on a named basis. | `Any` |
| [`cost_centre_of_team`](references/cost_centre_of_team.md) | Use this when you need the cost centre key of one team. | `str` |
| [`fact`](references/fact.md) | Use this when you need the value, the status and the source file of a fact by its id, for example a rate or a legal parameter that a function reads. | `Fact` |
| [`footer`](references/footer.md) | Use this when you need the caption line of a result envelope: basis and as-of, 'synthetic data' when the envelope says so and 'provisional legal parameter, VERIFY' when its status carries VERIFY. | `str` |
| [`format_money`](references/format_money.md) | Use this when you write one amount of one currency into a text, a table or a figure label. | `str` |
| [`format_number`](references/format_number.md) | Use this when you write a number into a text, a table or a figure label. | `str` |
| [`format_percent`](references/format_percent.md) | Use this when you write a percentage into a text, a table or a figure label. | `str` |
| [`from_cents`](references/from_cents.md) | Use this when you have whole cents and need the amount, with a missing value kept as missing. | `Any` |
| [`grade_info`](references/grade_info.md) | Use this when you need the grade level, name and bands in DKK and EUR from the grade frame. | `pd.DataFrame` |
| [`guarded_sum`](references/guarded_sum.md) | Use this when you need the sum of an amount or quantity column and must be sure that no two currencies or units are added together. | `pd.DataFrame` |
| [`interval_join`](references/interval_join.md) | Use this when you need to attach to each point in time the interval that contains it, such as a sample and the quality event that covers it. | `pd.DataFrame` |
| [`is_valid_key`](references/is_valid_key.md) | Use this when you only need to know whether a text is a valid typed key, without handling an error. | `bool` |
| [`is_working_day`](references/is_working_day.md) | Use this when you need to know whether a date is a working day in a region. | `bool` |
| [`join_report`](references/join_report.md) | Use this when you join two frames on key columns and need the keys without a partner, classed as orphan, null_key or master_not_visible_at_stage. | `JoinResult` |
| [`line_with_gaps`](references/line_with_gaps.md) | Use this when you need the points of a line with a null row inserted where the step to the next x is too large, so that a plot breaks there instead of joining across the gap. | `pd.DataFrame` |
| [`loader_contract`](references/loader_contract.md) | Use this when you need to check that an app loader (SQL or API) keeps the loading contract, and get the problems as text. | `list[str]` |
| [`map_label`](references/map_label.md) | Use this when you need the label of a map: 'synthetic data' and the basemap attribution, because the networks drawn on the map are fictional (visualisations.md). | `str` |
| [`mark_aggregate`](references/mark_aggregate.md) | Use this when you have checked an aggregate of a restricted measure and want to hand it on marked as safe to show. | `RestrictedAggregate` |
| [`master_of`](references/master_of.md) | Use this when you have a key prefix and need the entity it names and the table that is its master. | `MasterInfo` |
| [`month_end`](references/month_end.md) | Use this when you need the last calendar day of a period written YYYY-MM. | `dt.date` |
| [`month_start`](references/month_start.md) | Use this when you need the first calendar day of a period written YYYY-MM. | `dt.date` |
| [`net_working_days`](references/net_working_days.md) | Use this when you need, per person, the working days of a period, the leave days that fall on working days and the days left after leave. | `pd.DataFrame` |
| [`parse_key`](references/parse_key.md) | Use this when you have the text of a typed key such as EMP-000001 and need its prefix, number, width and family. | `KeyParts` |
| [`parse_label`](references/parse_label.md) | Use this when you have a natural label (a budget, forecast, waste or ground label) or a GL account and need its parts. | `LabelParts` |
| [`parse_period`](references/parse_period.md) | Use this when you have a period written YYYY-MM and need its year and month as numbers. | `tuple[int, int]` |
| [`period_of`](references/period_of.md) | Use this when you have a date and need its period written YYYY-MM. | `str` |
| [`period_range`](references/period_range.md) | Use this when you need every month between two periods, both included, as a list of periods. | `list[str]` |
| [`public_holidays`](references/public_holidays.md) | Use this when you need the public holidays of a year in one of the three regions. | `frozenset[dt.date]` |
| [`rdiv`](references/rdiv.md) | Use this when you divide whole cents by a whole number and the result must be whole cents too. | `Any` |
| [`reduce_chunks`](references/reduce_chunks.md) | Use this when the rows come as an iterable of frames (chunks) and you need grouped sums, counts, minima or maxima with the same result as one frame, without holding all rows at once. | `pd.DataFrame` |
| [`region_of`](references/region_of.md) | Use this when you need the calendar region (DK, DE-HH or DE-NI) of a site or of a country with one region. | `str` |
| [`release_now`](references/release_now.md) | Use this when you need the one release identity (release, now, generated_at, base seed and increment) that all loaded sources share. | `ReleaseInfo` |
| [`require_columns`](references/require_columns.md) | Use this when a function reads columns that are restricted (pay, birth date) and must refuse a session that may not read them. | `None` |
| [`require_frame_columns`](references/require_frame_columns.md) | Use this when a loaded frame must carry the source column names of a table before you use it, so a renamed or dropped column is caught early. | `None` |
| [`require_sources`](references/require_sources.md) | Use this when a function reads tables of some sources and must refuse a session whose stage does not hold them yet. | `None` |
| [`role_info`](references/role_info.md) | Use this when you need per role its department and grade, with the grade level, name and bands. | `pd.DataFrame` |
| [`rows_on`](references/rows_on.md) | Use this when a table has effective dating (valid_from, valid_to) and you need the rows that are valid on one date. | `pd.DataFrame` |
| [`source_stage`](references/source_stage.md) | Use this when you need to know at which stage a source (hr, finance, projects and so on) becomes visible to a session. | `str` |
| [`stage_banner`](references/stage_banner.md) | Use this when a stage or column refusal must be shown to the user as one plain line. | `str` |
| [`stage_matrix`](references/stage_matrix.md) | Use this when you need to prove that a function gives a result where all its sources are visible and refuses, naming the missing sources, where they are not. | `list[dict[str, Any]]` |
| [`stage_placeholder`](references/stage_placeholder.md) | Use this when you need the panel text for a chart whose source is above the stage of the session: what is missing, at which stage it appears and what the session sees. | `str` |
| [`strip_restricted`](references/strip_restricted.md) | Use this when you have a frame and must remove the restricted columns (pay, birth date) before a session that may not read them sees it. | `pd.DataFrame` |
| [`synthetic_label`](references/synthetic_label.md) | Use this when you need the text 'synthetic data' that goes in the corner of every chart, table and map, in both modes. | `str` |
| [`table_key`](references/table_key.md) | Use this when you need the columns that make up the primary key of a table, composite keys included. | `tuple[str, ...]` |
| [`team_context`](references/team_context.md) | Use this when you need per team its department, cost centre, legal entity, site, country and calendar region in one frame. | `pd.DataFrame` |
| [`team_of_cost_centre`](references/team_of_cost_centre.md) | Use this when you need the team that owns one cost centre. | `str` |
| [`to_cents`](references/to_cents.md) | Use this when you need an amount as whole cents, so that sums and comparisons are exact. | `Any` |
| [`visible_sources`](references/visible_sources.md) | Use this when you need the sources that a session at a stage can see. | `frozenset[str]` |
| [`working_days`](references/working_days.md) | Use this when you need the number of working days between two dates in a region, both days included. | `int` |
| [`year_of`](references/year_of.md) | Use this when you need the year, counted from a start month, that a period belongs to: a fiscal year or a holiday year that does not begin in January. | `int` |

## Reference pages

- One page per function in `references/` (signature, rule, arguments, returns, errors, example, facts and sources).
- `references/flat.md`: every page in one file, for an agent that reads one file.
