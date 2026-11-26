# halvaro-core: keys, periods, facts, stage and access, calendar, money, flat reference

# add_months

```python
add_months(period: str, n: int) -> str
```

Use this when you need the period a number of months after, or before, a period.

## Args

period: A period as text, for example "2026-11".
n: Number of months to move. Negative moves back; zero returns the same period.

## Returns

str: the period YYYY-MM, with the year carried over.

## Raises

PeriodError: the text is not a period of the form YYYY-MM, or the result is outside the years 0001 to 9999.

## Example

```python
>>> from halvaro.core import add_months
>>> add_months("2026-11", 3), add_months("2026-01", -1)
('2027-02', '2025-12')
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# add_working_days

```python
add_working_days(start: dt.date, n: int, region: str) -> dt.date
```

Use this when you need the date that is a number of working days from a start date, the start date counting as the first when it is a working day.

Rule: the n-th working day on or after start. Weekends and the public holidays of the region are skipped.

## Args

start: The first day to look at.
n: Which working day, 1 or more. With 1 the result is the start itself when it is a working day.
region: DK, DE-HH or DE-NI.

## Returns

datetime.date: the n-th working day on or after start.

## Raises

FrameError: n is less than 1.
UnknownRegion: the region is none of DK, DE-HH and DE-NI.

## Example

```python
>>> import datetime as dt
>>> from halvaro.core import add_working_days
>>> friday = dt.date(2026, 3, 13)
>>> add_working_days(friday, 1, "DK"), add_working_days(friday, 2, "DK")
(datetime.date(2026, 3, 13), datetime.date(2026, 3, 16))
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `legal.public_holidays.DK_store_bededag_abolished_from`, `legal.public_holidays.DE_reformationstag_from`.

Source columns: none (inputs are passed in).

# apply_theme

```python
apply_theme(figure: Any, mode: str = 'light') -> Any
```

Use this when you need a chart to carry the colours and font of the light or dark theme.

Rule: the theme tokens of the mode (proposed, they wait for a design review) are set on the figure. A plotly figure (one with update_layout) gets the paper and plot background, the text colour and font, the categorical colours as colorway and the grid colour on both axes. A matplotlib figure (one with axes and set_facecolor) gets the background on the figure and every axes, the text colour on ticks, axis labels and title, and the grid colour. The same figure object is returned.

## Args

figure: A plotly figure or a matplotlib figure.
mode: "light" or "dark". Default "light" (proposed).

## Returns

Any: the figure that was passed in, changed in place.

## Raises

FrameError: the mode is neither light nor dark (checked first), or the figure is neither a plotly nor a matplotlib figure.

## Example

```python
>>> from halvaro.core import apply_theme
>>> class Fig:
...     def update_layout(self, **settings):
...         self.layout = settings
...     def update_xaxes(self, **settings):
...         pass
...     def update_yaxes(self, **settings):
...         pass
>>> fig = Fig()
>>> apply_theme(fig, "dark") is fig
True
>>> fig.layout["paper_bgcolor"], len(fig.layout["colorway"])
('#14181D', 6)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# asof_join

```python
asof_join(left: pd.DataFrame, right: pd.DataFrame, date_column: str, key: str | Sequence[str], valid_from: str = 'valid_from', valid_to: str = 'valid_to', suffix: str = '_r') -> pd.DataFrame
```

Use this when you need to attach to each row the version of an effective dated table that was valid on the row's date.

Rule: every left row keeps its place. It gets the right row with the same key whose valid_from is the latest on or before the left date, provided its valid_to is empty or on or after that date; otherwise the right columns are empty. A left date written YYYY-MM counts as the first day of that month. The right frame must have no overlapping, reversed or doubly open rows; gaps are allowed and give empty right columns.

## Args

left: The table that needs the lookup, one row per event.
right: The effective dated table, one row per version, with the two date columns.
date_column: Name of the column in left that holds the date, a date or a YYYY-MM period text.
key: Column name, or list of column names, that exist in both frames and identify the thing.
valid_from: Name of the start column of right. Default "valid_from".
valid_to: Name of the end column of right; empty means open. Default "valid_to".
suffix: Added to the name of a right column that has the same name as a left column (the key columns excepted). Default "_r".

## Returns

pandas.DataFrame: the columns of left in their order, then the other columns of right (including its valid_from and valid_to), one row per left row in the order of left with a fresh index.

## Raises

PeriodError: the right frame has overlapping, reversed or doubly open rows.
FrameError: right lacks the valid_from or valid_to column.
KeyError: date_column or a key column is missing from left, or a key column is missing from right.
FrameError: the left date column contains a null.
ValueError: the dates of the left column or of the date columns of right are text that is not a date.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import asof_join
>>> left = pd.DataFrame({"k": ["A", "A", "B"], "month": ["2026-02", "2026-04", "2026-02"]})
>>> right = pd.DataFrame({"k": ["A", "A"], "valid_from": ["2026-01-01", "2026-03-01"], "valid_to": ["2026-02-28", None], "rate": [10, 20]})
>>> asof_join(left, right, "month", "k")["rate"].tolist()
[10.0, 20.0, nan]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# asof_stable

```python
asof_stable(call: Callable[[Mapping[str, pd.DataFrame], dt.date], Any], baseline: Mapping[str, pd.DataFrame], later: Mapping[str, pd.DataFrame], as_of: dt.date, *, key: str, allowed_keys: Iterable[Any] = ()) -> bool
```

Use this when you need to prove that a result as of a date does not change when a later data release is loaded, except for rows that an effective dated change may alter.

Rule: the call is run on the baseline frames and on the later frames with the same date. Both results (or the value of each, when it is an envelope) must have the same columns. They are then matched on the key column: a key present on one side only, or with a different value in any shared column (two empty values are equal), counts as changed. Changed keys that are not in allowed_keys fail the check. Row order does not matter.

## Args

call: A function that takes a mapping of frames and the date and returns a frame, or an envelope whose value is a frame.
baseline: The frames of the baseline release, as {"source.table": frame}.
later: The frames of the later release, in the same form.
as_of: The date given to the call for both releases.
key: Name of the column that identifies a row in the result.
allowed_keys: Values of the key column whose rows may differ. Default none.

## Returns

bool: True when the check passes (a failure raises instead).

## Raises

AssertionError: the two results have different columns, or rows differ for a key that is not allowed.
KeyError: the key is not a column of a result.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.core import asof_stable
>>> base = {"t": pd.DataFrame({"k": ["A", "B"], "v": [1, 2]})}
>>> later = {"t": pd.DataFrame({"k": ["A", "B"], "v": [1, 3]})}
>>> call = lambda frames, day: frames["t"]
>>> asof_stable(call, base, later, dt.date(2026, 6, 30), key="k", allowed_keys=["B"])
True
>>> asof_stable(call, base, later, dt.date(2026, 6, 30), key="k")
Traceback (most recent call last):
...
AssertionError: results at 2026-06-30 differ between releases for k ['B']
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# assert_aggregate

```python
assert_aggregate(frame: pd.DataFrame, restricted_column: str, group_columns: Sequence[str] = (), min_group: int | None = None, count_column: str | None = None) -> None
```

Use this when a frame holds an aggregate of a restricted measure (pay, birth date) and you must check that it names no person and has no group that is too small.

Rule: the frame is refused when any column or index level holds an EMP key in at least one value (text columns are read as text; numbers, dates and durations are skipped). When min_group is given, every row of count_column must be at least min_group, and a row with no count is refused as well. group_columns is not read by the check; it is only carried by mark_aggregate.

## Args

frame: The aggregate, one row per group.
restricted_column: The column that holds the restricted measure; it must be a column of the frame.
group_columns: The columns the aggregate is grouped by. Optional; not used by the check itself.
min_group: The smallest number of people a group may have. Optional; without it the group sizes are not checked.
count_column: The column with the number of people per group. Needed when min_group is given.

## Returns

None: nothing happens when the frame passes the guard.

## Raises

FrameError: restricted_column is not a column of the frame, min_group is given without a count_column that exists in the frame, or count_column does not hold numbers.
AggregateRefusal: a column or index level holds an EMP key, or one or more groups have a count below min_group or no count.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import assert_aggregate
>>> frame = pd.DataFrame({"grade": ["A", "B"], "measure": [10.0, 20.0], "people": [3, 1]})
>>> assert_aggregate(frame, "measure", ["grade"], min_group=1, count_column="people")
>>> assert_aggregate(frame, "measure", ["grade"], min_group=2, count_column="people")
Traceback (most recent call last):
...
halvaro.core.errors.AggregateRefusal: 1 groups have fewer than 2 people or no count; suppress them or widen the grouping.
>>> by_person = pd.DataFrame({"emp_key": ["EMP-000001"], "measure": [10.0]})
>>> assert_aggregate(by_person, "measure")
Traceback (most recent call last):
...
halvaro.core.errors.AggregateRefusal: measure sits next to person keys in column(s) emp_key. Group by department, grade or similar and drop the person key.
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# caption

```python
caption(basis: str | None, as_of: dt.date | pd.Timestamp | str | None) -> str
```

Use this when a figure or a table needs the basis and as-of line under it.

Rule: the line is "<basis>, as of <date>". A missing basis is written "basis not stated" and a missing date "as-of not stated"; neither is left out.

## Args

basis: What the figures are (for example "actual cost"), or None.
as_of: The as-of date as a date, a timestamp or an ISO date text, or None.

## Returns

str: the caption line.

## Raises

FrameError: as_of is neither empty, a date, a timestamp nor an ISO date text.

## Example

```python
>>> import datetime as dt
>>> from halvaro.core import caption
>>> caption("actual cost", dt.date(2026, 11, 30)), caption(None, None)
('actual cost, as of 2026-11-30', 'basis not stated, as-of not stated')
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# cfg

```python
cfg(file: str, path: str) -> Fact
```

Use this when you know the config file and the key path of a value but not its fact id.

Rule: the file is mapped to the prefix of its facts and the call is the same as fact(prefix + "." + path).

## Args

file: The config file as the snapshot names it, for example "config/world.yaml".
path: The key path inside the file, for example "fx_eur_dkk_fixed".

## Returns

Fact: the fact at that path (id, value, status and file).

## Raises

FactNotFound: the file is not a fact file (the message lists the known files), or no fact has that path.

## Example

```python
>>> from halvaro.core import cfg
>>> cfg("config/world.yaml", "fx_eur_dkk_fixed").id
'world.fx_eur_dkk_fixed'
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# check_contiguity

```python
check_contiguity(frame: pd.DataFrame, key: str | Sequence[str], valid_from: str = 'valid_from', valid_to: str = 'valid_to', convention: str = 'day_after', table: str = '') -> pd.DataFrame
```

Use this when a table has effective dating (valid_from, valid_to per key) and you need the rows that break the dating rules.

Rule: per key the rows are ordered by valid_from. A row is reversed when valid_to is before valid_from, two_open when a key has more than one open row (valid_to empty), open_not_last when an open row is followed by another row, overlap when the next row starts before the previous one ends, and gap when it starts later. With convention "day_after" the next row starts the day after valid_to; with "touching" it starts on the same day.

## Args

frame: The table, one row per version.
key: Column name, or list of column names, that identify the thing the rows are versions of.
valid_from: Name of the start column. Default "valid_from".
valid_to: Name of the end column; empty means open. Default "valid_to".
convention: "day_after" or "touching". Default "day_after".
table: A label written into the table column of the result, for example "hr.employment_term".

## Returns

pandas.DataFrame: one row per violation with the columns table, key, rule and detail; empty when the dating is clean.

## Raises

FrameError: the frame has no valid_from or valid_to column (the names are the arguments).
PeriodError: the convention is neither day_after nor touching.
ValueError: a date column holds text that is not a date (the parsing error of pandas, a ValueError).

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import check_contiguity
>>> frame = pd.DataFrame({"k": ["A", "A"], "valid_from": ["2026-01-01", "2026-02-05"], "valid_to": ["2026-01-31", None]})
>>> check_contiguity(frame, "k")[["key", "rule", "detail"]].to_dict("records")
[{'key': 'A', 'rule': 'gap', 'detail': 'next row starts 2026-02-05, previous ends 2026-01-31'}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# check_key_column

```python
check_key_column(frame: pd.DataFrame, column: str, target: str | None = None, allow_null: bool = False) -> pd.DataFrame
```

Use this when you need to check that every value of a key column is a well formed key, and optionally that its prefix is one the dictionary allows for that column.

Rule: each null is a violation "null" unless allow_null is set (one per null row). Each distinct non null value is checked once: a natural label (BUD, FC, GND, WST) must match the pattern of its kind, any other value must look like PREFIX-digits (else "bad_format"), carry a prefix of the key design (else "unknown_prefix") and match the pattern of that prefix (else "bad_format"). When target names a dictionary column that is a foreign key, a well formed key whose prefix is not one of the allowed prefixes of that column is a "wrong_prefix". A target without a foreign key adds no prefix check.

## Args

frame: The frame that holds the key column.
column: The name of the key column in the frame.
target: The dictionary column as source.table.column whose allowed prefixes apply. Optional; it also names the table in the result.
allow_null: True when null keys are allowed. Optional, default False.

## Returns

pandas.DataFrame: the violations with the columns table, key, rule and detail, sorted by those columns; empty when all keys pass. The table is the target when given, else the column name; the key of a null is empty text.

## Raises

FrameError: the column is not a column of the frame, or target is given and is not a column of the data dictionary.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import check_key_column
>>> frame = pd.DataFrame({"k": ["EMP-000001", "EMP-1", "DEP-01", None]})
>>> check_key_column(frame, "k", "competence.crew_plan.emp_key")[["key", "rule"]]
         key          rule
0                     null
1     DEP-01  wrong_prefix
2      EMP-1    bad_format
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# check_org_integrity

```python
check_org_integrity(team: pd.DataFrame, department: pd.DataFrame, site: pd.DataFrame, cost_centre: pd.DataFrame | None = None, expected: dict[str, int] | None = None) -> pd.DataFrame
```

Use this when you need to check the organisation frames for broken references, missing leads and cost centres, and wrong counts.

Rule: one violation row is written per broken rule, with the rule count (the row count differs from the expected count, or a key is repeated), no_cost_centre, cost_centre_not_unique (shared by several teams), no_lead, dangling (the department or site key of a team is not in its frame) or pairing (only when cost_centre is passed: the cost centre of a team is missing there or points to another team). A team without a cost centre therefore also gets a pairing row when cost_centre is passed. A clean organisation gives an empty frame.

## Args

team: Team frame (hr.team) with team_key, dep_key, cost_centre_key, site_key and lead_emp_key.
department: Department frame (hr.department) with dep_key.
site: Site frame (hr.site) with site_key.
cost_centre: Optional cost centre frame (finance.cost_centre) with cc_key and team_key. Without it the pairing rule is not checked.
expected: Optional expected row counts as a dict with the keys teams, departments and sites. Without it (or when empty) the counts of the snapshot are used.

## Returns

pandas.DataFrame: one row per violation with the columns table, key, rule and detail, sorted by those four columns; empty when nothing is broken.

## Raises

FrameError: the team frame lacks a column, or the cost centre frame lacks cc_key or team_key.
KeyError: the department frame lacks dep_key, the site frame lacks site_key, or expected lacks one of teams, departments and sites.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import check_org_integrity
>>> team = pd.DataFrame({"team_key": ["T1", "T2"], "dep_key": ["D1", "D1"], "cost_centre_key": ["CC-1", "CC-2"], "site_key": ["S1", "S1"], "lead_emp_key": ["EMP-X", None]})
>>> department, site = pd.DataFrame({"dep_key": ["D1"]}), pd.DataFrame({"site_key": ["S1"]})
>>> found = check_org_integrity(team, department, site, expected={"teams": 2, "departments": 1, "sites": 1})
>>> found.to_dict("records")
[{'table': 'hr.team', 'key': 'T2', 'rule': 'no_lead', 'detail': 'team has no lead'}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.team.team_key`, `hr.team.lead_emp_key`, `hr.department.dep_key`, `hr.site.site_key`.

# check_polymorphic

```python
check_polymorphic(frame: pd.DataFrame, key_column: str, type_column: str, mapping: Mapping[Any, str | None] | None = None) -> pd.DataFrame
```

Use this when a key column can hold keys of different kinds and a type column says which kind each row has, and you need the rows where the two disagree.

Rule: for each distinct pair of type and key (rows with a null key are skipped) the prefix is the text of the key before the first dash. With a mapping the type must be a key of the mapping and the prefix must equal its value; a value None means the type is free text and is not checked. Without a mapping the type value itself is the expected prefix. A type that is not in the mapping gives "unknown_type", a prefix that differs gives "wrong_prefix".

## Args

frame: The frame that holds both columns.
key_column: The column with the keys.
type_column: The column with the type of each key.
mapping: A mapping from a type value to the expected prefix, or None for a type that is not checked. Optional; without it the type column holds the prefix.

## Returns

pandas.DataFrame: the violations with the columns table, key, rule and detail, sorted by those columns; the table is the name of the key column. Empty when all rows agree.

## Raises

FrameError: key_column or type_column is not a column of the frame.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import check_polymorphic
>>> frame = pd.DataFrame({"t": ["employee", "external", "employee"], "k": ["EMP-000001", "CNT-000001", "CNT-000002"]})
>>> check_polymorphic(frame, "k", "t", {"employee": "EMP", "external": "CNT"})[["key", "rule", "detail"]]
          key          rule                                  detail
0  CNT-000002  wrong_prefix  t='employee' implies EMP, key has CNT
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# column_prefixes

```python
column_prefixes(column: str) -> tuple[str, ...]
```

Use this when you need the key prefixes that a column of the data dictionary may hold, taken from its foreign key target.

Rule: the prefixes are read from the dictionary for the column; a polymorphic column has several, and a column that is no foreign key has none.

## Args

column: The dictionary column as source.table.column, for example "competence.crew_plan.emp_key".

## Returns

tuple: the allowed prefixes as text, for example ('EMP',); empty when the column is no foreign key.

## Raises

FrameError: the column is not a column of the data dictionary.

## Example

```python
>>> from halvaro.core import column_prefixes
>>> column_prefixes("competence.crew_plan.emp_key")
('EMP',)
>>> column_prefixes("competence.crew_plan.nothing")
Traceback (most recent call last):
...
halvaro.core.errors.FrameError: competence.crew_plan.nothing is not a column of the data dictionary; use source.table.column
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# combine_status

```python
combine_status(statuses: Iterable[str]) -> str
```

Use this when a result rests on several facts and needs one status for its envelope.

Rule: VERIFY beats verified, synthetic is kept next to it, and both are reported. A proposed fact counts as VERIFY because the owner has not decided it. Without any fact the status is ok.

## Args

statuses: The statuses of the facts the result used (verified, VERIFY, synthetic or proposed).

## Returns

str: "ok", "synthetic", "VERIFY" or "VERIFY+synthetic".

## Raises

Nothing is raised: a text that is none of the four statuses is ignored.

## Example

```python
>>> from halvaro.core import combine_status
>>> combine_status(["verified", "VERIFY"]), combine_status([]), combine_status(["proposed", "synthetic"])
('VERIFY', 'ok', 'VERIFY+synthetic')
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# compare_periods

```python
compare_periods(a: str, b: str) -> int
```

Use this when you need to order two periods written YYYY-MM.

## Args

a: The first period.
b: The second period.

## Returns

int: -1 when a is before b, 0 when they are equal, 1 when a is after b.

## Raises

PeriodError: a or b is not a period of the form YYYY-MM.

## Example

```python
>>> from halvaro.core import compare_periods
>>> compare_periods("2026-02", "2026-11"), compare_periods("2026-11", "2026-11"), compare_periods("2027-01", "2026-11")
(-1, 0, 1)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# convert

```python
convert(cents: Any, from_currency: str, to_currency: str, *, basis: str) -> Any
```

Use this when you move whole cents between DKK, EUR and SEK on a named basis.

Rule: the booking basis uses the fixed booking rates of core; group_pay uses the fixed EUR to DKK rate of the fact world.fx_eur_dkk_fixed and knows DKK and EUR only. The cents are multiplied by the rate of the from currency and divided by the rate of the to currency with rdiv, so the result is rounded half away from zero. There is no default basis.

## Args

cents: Whole cents, one value, an array or a Series.
from_currency: DKK, EUR or SEK.
to_currency: DKK, EUR or SEK.
basis: "booking" or "group_pay".

## Returns

The converted cents, of the shape of the input.

## Raises

BasisError: the basis is not available (the daily basis needs a rate frame), or a currency has no rate on the basis.

## Example

```python
>>> from halvaro.core import convert, fact
>>> rate = fact("world.fx_eur_dkk_fixed").value
>>> int(convert(10000, "EUR", "DKK", basis="booking")) == round(10000 * rate), int(convert(500, "DKK", "DKK", basis="booking"))
(True, 500)
>>> convert(100, "DKK", "EUR", basis="daily")
Traceback (most recent call last):
...
halvaro.core.errors.BasisError: basis 'daily' is not available; use 'booking' or 'group_pay' (the daily basis needs a rate frame and comes with core 0.2)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `world.fx_eur_dkk_fixed`, `world.fx_sek_dkk_fixed`.

Source columns: none (inputs are passed in).

# cost_centre_of_team

```python
cost_centre_of_team(team: pd.DataFrame, team_key: str) -> str
```

Use this when you need the cost centre key of one team.

Rule: the team frame is searched for the team key and the cost centre key of that one row is returned. A team that is missing or listed more than once is refused, never guessed.

## Args

team: Team frame (hr.team) with team_key and cost_centre_key.
team_key: The key of the team, for example "T1".

## Returns

str: the cost centre key of the team, for example "CC-1".

## Raises

FrameError: the frame lacks a column, or the team key does not match exactly one row.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import cost_centre_of_team
>>> team = pd.DataFrame({"team_key": ["T1", "T2"], "cost_centre_key": ["CC-1", "CC-2"]})
>>> cost_centre_of_team(team, "T2")
'CC-2'
>>> cost_centre_of_team(team, "T9")
Traceback (most recent call last):
...
halvaro.core.errors.FrameError: team T9 has 0 rows in hr.team; expected 1
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.team.team_key`, `hr.team.cost_centre_key`.

# fact

```python
fact(fact_id: str) -> Fact
```

Use this when you need the value, the status and the source file of a fact by its id, for example a rate or a legal parameter that a function reads.

Rule: the fact comes from the snapshot of the config files and the authored decisions. Its status (verified, VERIFY, synthetic or proposed) travels with the value, and the caller reports it. A fact that holds a date is returned as a datetime.date.

## Args

fact_id: The id of the fact, for example "world.fx_eur_dkk_fixed".

## Returns

Fact: id, value, status (verified, VERIFY, synthetic or proposed) and file of the fact.

## Raises

FactNotFound: the id is unknown. The message names up to three close ids.

## Example

```python
>>> from halvaro.core import fact
>>> f = fact("world.fx_eur_dkk_fixed")
>>> f.id, f.status in ("verified", "VERIFY", "synthetic", "proposed")
('world.fx_eur_dkk_fixed', True)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# footer

```python
footer(envelope: Envelope) -> str
```

Use this when you need the caption line of a result envelope: basis and as-of, 'synthetic data' when the envelope says so and 'provisional legal parameter, VERIFY' when its status carries VERIFY.

Rule: the caption of the envelope's basis and as_of, then 'synthetic data' when envelope.synthetic is true (a missing attribute counts as true), then the VERIFY label when the text VERIFY occurs
in envelope.status (so VERIFY and VERIFY+synthetic both qualify, and so does a proposed fact whose status carries it); the parts are joined with "; ".

## Args

envelope: The result envelope (any object with the attributes basis, as_of, synthetic and status; a missing attribute is read as empty, and synthetic as true).

## Returns

str: the footer text.

## Raises

FrameError: the as_of of the envelope is not empty, a date, a timestamp or an ISO date text (YYYY-MM-DD).

## Example

```python
>>> import datetime as dt
>>> from halvaro.core import Envelope, footer
>>> footer(Envelope(value=1, basis="actual cost", as_of=dt.date(2026, 11, 30), status="VERIFY", synthetic=True))
'actual cost, as of 2026-11-30; synthetic data; provisional legal parameter, VERIFY'
>>> footer(Envelope(value=1, basis="actual cost", as_of=dt.date(2026, 11, 30), synthetic=False))
'actual cost, as of 2026-11-30'
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# format_money

```python
format_money(amount: Any, currency: str, scale: str | None = None, decimals: int | None = None) -> str
```

Use this when you write one amount of one currency into a text, a table or a figure label.

Rule: the currency code, a space and the amount rounded half away from zero; with scale k, m or bn the amount is divided by a thousand, a million or a billion and the letter is appended. Decimals default to 0, or 1 when scaled. A sum over two currencies is refused upstream (see guarded_sum).

## Args

amount: One number; None and NaN give n/a.
currency: DKK, EUR or SEK.
scale: None, "k", "m" or "bn".
decimals: The number of decimals, a whole number from 0 to 6. Default 0, or 1 with a scale.

## Returns

str: the text, for example DKK 1,235.

## Raises

FrameError: the currency is not DKK, EUR or SEK, the scale is not allowed, or amount is not one number.

## Example

```python
>>> from halvaro.core import format_money
>>> format_money(1234.5, "DKK"), format_money(1234567.0, "EUR", "m")
('DKK 1,235', 'EUR 1.2m')
>>> format_money(1.0, "XXX")
Traceback (most recent call last):
...
halvaro.core.errors.FrameError: currency 'XXX' is not one of DKK, EUR, SEK
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# format_number

```python
format_number(x: Any, decimals: int = 0) -> str
```

Use this when you write a number into a text, a table or a figure label.

Rule: thousands separator comma, decimal point, rounding half away from zero, a minus sign and no scientific notation. None and NaN give n/a.

## Args

x: One number; None and NaN are allowed.
decimals: The number of decimals, a whole number from 0 to 6. Default 0.

## Returns

str: the text, for example 1,235 for 1234.5 with no decimals.

## Raises

FrameError: x is not one number (a list or a text), or decimals is not a whole number from 0 to 6.

## Example

```python
>>> from halvaro.core import format_number
>>> format_number(1234.5, 1), format_number(-1234567.891), format_number(None)
('1,234.5', '-1,234,568', 'n/a')
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# format_percent

```python
format_percent(x: Any, decimals: int = 1, *, ratio: bool = False) -> str
```

Use this when you write a percentage into a text, a table or a figure label.

Rule: the number with the sign %. x is already in percent (12.345 gives 12.3%); with ratio=True x is a share (0.12345 gives 12.3%). Rounding half away from zero. None and NaN give n/a.

## Args

x: One number; None and NaN are allowed.
decimals: The number of decimals, a whole number from 0 to 6. Default 1.
ratio: True when x is a share of one and not a percent. Default False.

## Returns

str: the text with the percent sign.

## Raises

FrameError: x is not one number, or decimals is not a whole number from 0 to 6.

## Example

```python
>>> from halvaro.core import format_percent
>>> format_percent(12.345), format_percent(0.256, ratio=True), format_percent(None)
('12.3%', '25.6%', 'n/a')
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# from_cents

```python
from_cents(cents: Any) -> Any
```

Use this when you have whole cents and need the amount, with a missing value kept as missing.

Rule: cents divided by 100. A null (None, NaN, pd.NA) stays NaN and is never turned into a number.

## Args

cents: One whole number of cents, a list or array of them, or a Series; the index of a Series is kept.

## Returns

The amounts as floats: a number for one value, an array for an array, a Series for a Series.

## Raises

This function raises no error of its own; a value that is not a number raises the error of numpy.

## Example

```python
>>> from halvaro.core import from_cents
>>> float(from_cents(123456))
1234.56
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# grade_info

```python
grade_info(grade: pd.DataFrame) -> pd.DataFrame
```

Use this when you need the grade level, name and bands in DKK and EUR from the grade frame.

Rule: the seven grade columns are taken from the grade frame as they are. Nothing is converted, checked or dropped, and the rows keep their order.

## Args

grade: Grade frame (hr.grade) with gra_key, level, name, band_min_dkk, band_max_dkk, band_min_eur and band_max_eur.

## Returns

pandas.DataFrame: a copy with the columns gra_key, level, name, band_min_dkk, band_max_dkk, band_min_eur and band_max_eur, one row per row of the grade frame; other columns of the input are left out.

## Raises

FrameError: the grade frame lacks one of the seven columns.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import grade_info
>>> grade = pd.DataFrame({"gra_key": ["G1"], "level": [3], "name": ["Grade 3"], "band_min_dkk": [10], "band_max_dkk": [20], "band_min_eur": [1], "band_max_eur": [2], "extra": ["x"]})
>>> grade_info(grade).columns.tolist()
['gra_key', 'level', 'name', 'band_min_dkk', 'band_max_dkk', 'band_min_eur', 'band_max_eur']
>>> int(grade_info(grade)["band_max_dkk"].iloc[0])
20
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.grade.gra_key`, `hr.grade.level`.

# guarded_sum

```python
guarded_sum(frame: pd.DataFrame, value: str, *, by: str | Iterable[str] = (), guard: str | Iterable[str] | None = None) -> pd.DataFrame
```

Use this when you need the sum of an amount or quantity column and must be sure that no two currencies or units are added together.

Rule: the value column is summed per group of the by columns as the plain sum of the stored numbers, with no rounding and no conversion to cents. Each guard column (default: currency, unit or both, whichever the frame has) may hold at most one distinct non null value inside each group; a group that mixes values is refused. Group on the guard column to get one sum per currency. Null values are skipped and an all null group sums to 0. Groups with a null key are kept.

## Args

frame: The rows to sum.
value: The column to sum.
by: The column or columns to group by, a name or a list. Optional; without it the result is one row with the sum of all rows.
guard: The column or columns that must not mix inside a group. Optional; default currency and unit when the frame has them.

## Returns

pandas.DataFrame: the by columns followed by the value column, one row per group sorted by the by columns; one row with only the value column when by is empty.

## Raises

FrameError: the value column, a by column or a guard column is missing, or the frame has no guard column at all and none was named.
SumGuardError: a group has more than one distinct value in a guard column.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import guarded_sum
>>> frame = pd.DataFrame({"currency": ["DKK", "DKK", "EUR"], "amount": [1.5, 2.25, 4.0]})
>>> guarded_sum(frame, "amount", by="currency")
  currency  amount
0      DKK    3.75
1      EUR    4.00
>>> guarded_sum(frame, "amount")
Traceback (most recent call last):
...
halvaro.core.errors.SumGuardError: the rows to sum carry more than one currency (DKK, EUR); group by currency or convert first (core.convert).
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# interval_join

```python
interval_join(points: pd.DataFrame, intervals: pd.DataFrame, *, point_ts: str = 'ts', start: str = 'from_ts', end: str = 'to_ts', key: str | Sequence[str] | None = None, inclusive_end: bool = True, how: str = 'left') -> pd.DataFrame
```

Use this when you need to attach to each point in time the interval that contains it, such as a sample and the quality event that covers it.

Rule: a point matches an interval when start <= ts and either end is empty (an open interval) or ts <= end (ts < end without inclusive_end). With key the key columns must also be equal. A point inside two intervals appears twice. With how "left" a point without an interval is kept with empty interval columns, with "inner" it is dropped. The join runs as one merge on the key (a cross join without key), so pass a chunk of points when there are millions.

## Args

points: The points, one row per point, with the timestamp column and the key columns.
intervals: The intervals, one row per interval, with the start and end columns and the key columns.
point_ts: Name of the timestamp column of points. Default "ts".
start: Name of the start column of intervals. Default "from_ts".
end: Name of the end column of intervals; empty means open. Default "to_ts".
key: Column name, or list of column names, present in both frames that must match as well. Optional.
inclusive_end: Whether a point at the end moment is inside. Default True.
how: "left" or "inner". Default "left".

## Returns

pandas.DataFrame: the columns of points, then the other columns of intervals (a name that is also a point column gets the suffix _iv), ordered by the position of the point and then the interval start, with a fresh index.

## Raises

FrameError: how is neither left nor inner, or a frame lacks a needed column.
TypeError: the timestamps cannot be compared, for example one side is time zone aware and the other is not.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import interval_join
>>> points = pd.DataFrame({"ts": [5, 12]})
>>> intervals = pd.DataFrame({"from_ts": [0], "to_ts": [5], "label": ["X"]})
>>> interval_join(points, intervals)["label"].tolist()
['X', nan]
>>> interval_join(points, intervals, inclusive_end=False, how="inner").shape[0]
0
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# is_valid_key

```python
is_valid_key(text: Any, prefix: str | None = None) -> bool
```

Use this when you only need to know whether a text is a valid typed key, without handling an error.

Rule: the text must be a key of a prefix of the key list with the digits of its width; with a prefix it must be a key of that prefix.

## Args

text: The text to test; a value that is not a text is not a key.
prefix: The prefix the key must have. Optional.

## Returns

bool: True for a valid key, False for anything else.

## Raises

Nothing is raised: a text that is not a key gives False.

## Example

```python
>>> from halvaro.core import is_valid_key
>>> is_valid_key("EMP-000001"), is_valid_key("EMP-1"), is_valid_key("EMP-000001", "GL")
(True, False, False)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# is_working_day

```python
is_working_day(day: dt.date, region: str) -> bool
```

Use this when you need to know whether a date is a working day in a region.

Rule: a working day is Monday to Friday that is no public holiday of the region. The holidays come from public_holidays, which carries the status of the facts it reads (VERIFY).

## Args

day: The date.
region: DK, DE-HH or DE-NI.

## Returns

bool: True on a working day, False on a weekend or a public holiday.

## Raises

UnknownRegion: the region is none of DK, DE-HH and DE-NI.

## Example

```python
>>> import datetime as dt
>>> from halvaro.core import is_working_day
>>> is_working_day(dt.date(2026, 3, 11), "DK"), is_working_day(dt.date(2026, 3, 14), "DK")
(True, False)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `legal.public_holidays.DK_store_bededag_abolished_from`, `legal.public_holidays.DE_reformationstag_from`.

Source columns: none (inputs are passed in).

# join_report

```python
join_report(left: pd.DataFrame, right: pd.DataFrame, on: str | Sequence[str] | None = None, *, left_on: str | Sequence[str] | None = None, right_on: str | Sequence[str] | None = None, how: str = 'left', context: Context | None = None, strict: bool | str = False, validate: str | None = None, suffixes: tuple[str, str] = ('', '_right')) -> JoinResult
```

Use this when you join two frames on key columns and need the keys without a partner, classed as orphan, null_key or master_not_visible_at_stage.

Rule: a null key never matches; it is reported as null_key and its row follows the matched rows. A key whose master source is above the stage of `context` is not an orphan (master_not_visible_at_stage). With strict=True orphans raise UnmatchedKeys on the sides the join has to complete (left for how="left", right for how="right", both otherwise); strict="left" or "right" checks one side whatever the join.

## Args

left: The left frame.
right: The right frame.
on: Key column name, or list of names, present in both frames. Use it or left_on and right_on, not both.
left_on: Key column name or names of the left frame.
right_on: Key column name or names of the right frame, as many as left_on.
how: "inner", "left", "right" or "outer". Default "left".
context: The caller, to tell an orphan from a key whose master is not visible at its stage. Optional.
strict: False, True, "left" or "right". Default False.
validate: Passed to pandas merge, for example "one_to_one". Optional.
suffixes: Suffixes for columns that exist on both sides. Default ("", "_right").

## Returns

JoinResult: .frame is the joined DataFrame, .report is an UnmatchedReport with left_only, right_only and counts (rows, keys, keys without partner, null key rows).

## Raises

FrameError: how or strict is not one of the allowed values, the key columns are not named correctly, a key column is missing in a frame or is called "class".
UnmatchedKeys: strict is set and a checked side has orphan keys.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import join_report
>>> left = pd.DataFrame({"k": ["A", "B", None]})
>>> right = pd.DataFrame({"k": ["A", "C"], "v": [1, 2]})
>>> result = join_report(left, right, on="k")
>>> list(result.frame.columns), result.report.counts["left_only_keys"], result.report.counts["right_only_keys"]
(['k', 'v'], 2, 1)
>>> result.report.left_only.to_dict("records")
[{'k': 'B', 'class': 'orphan'}, {'k': None, 'class': 'null_key'}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# line_with_gaps

```python
line_with_gaps(x: Iterable[Any] | pd.Series, y: Iterable[Any] | pd.Series, *, interval: float | dt.timedelta | None = None, factor: float = 1.5) -> pd.DataFrame
```

Use this when you need the points of a line with a null row inserted where the step to the next x is too large, so that a plot breaks there instead of joining across the gap.

Rule: the points are sorted by x (stable). Where the step to the next x is strictly more than the threshold, a row is inserted with x halfway through the gap and y null; a gap is never filled
with zero and a null y stays null. The threshold is `factor` times `interval` when the caller passes the sampling interval, else `factor` times the median step (1.5 is proposed). Rows with a NaN x sort last and are kept. With fewer than two points the sorted points are returned as they are.

## Args

x: The x values (numbers or dates), as a list, array or Series.
y: The y values, one per x.
interval: The sampling interval, a number or a timedelta for dates; None takes the median step.
factor: How many intervals a step may take before the line breaks (proposed 1.5).

## Returns

pandas.DataFrame with the columns x and y, sorted by x, with a row of null y added in every gap.

## Raises

FrameError: x or y is a scalar or a text and not a list, array or Series, x holds text or other values that are neither numbers nor dates, the interval is not a timedelta for dates or not a number for numbers, x and y differ in length, or the interval (given or median) is zero, negative or unknown; a median step of zero raises it even when a real gap exists (pass interval=).

## Example

```python
>>> from halvaro.core import line_with_gaps
>>> line_with_gaps([1, 2, 3, 6, 7], [10, 20, 30, 60, 70]).to_dict("list")
{'x': [1.0, 2.0, 3.0, 4.5, 6.0, 7.0], 'y': [10.0, 20.0, 30.0, nan, 60.0, 70.0]}
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# loader_contract

```python
loader_contract(loader: Any, expected_columns: Mapping[str, list[str]], *, context: Context | None = None, restricted_columns: Iterable[str] = (), where: Mapping[str, tuple[str, Any]] | None = None) -> list[str]
```

Use this when you need to check that an app loader (SQL or API) keeps the loading contract, and get the problems as text.

Rule: for each table the loader is called and checked: the column names are exactly the expected ones, in order; no timestamp column is time zone aware; the columns argument returns just the first two expected columns (only those two are requested); a where condition (column equal to value) is honoured; no restricted column is present when the context does not allow restricted access; and the chunks of iter_chunks put together equal load. One problem is written per broken check. Only the first load call of a table is guarded: a table that fails it is a problem and the other checks of that table are skipped; exceptions raised by later load calls or by iter_chunks propagate. Dtype checks are not run.

## Args

loader: An object with load(source, table, columns=None, where=None) and iter_chunks(source, table, columns=None, where=None), both returning frames.
expected_columns: The exact source column names per table, as {"source.table": [columns]}.
context: The caller. The restricted check runs only when it is given and does not allow restricted access. Default None.
restricted_columns: Names of the restricted columns. Default none.
where: Optional equality conditions as {"source.table": (column, value)}.

## Returns

list: the problems as text, one per broken check, each starting with the table name; empty when the loader passes.

## Raises

ValueError: a table name in expected_columns does not have the form source.table.
KeyError: a where column is not a column of the loaded table.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import loader_contract
>>> class Loader:
...     frame = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
...     def load(self, source, table, columns=None, where=None):
...         return self.frame if columns is None else self.frame[columns]
...     def iter_chunks(self, source, table, columns=None, where=None):
...         yield self.frame.iloc[:1]
...         yield self.frame.iloc[1:]
>>> loader_contract(Loader(), {"s.t": ["a", "b"]})
[]
>>> loader_contract(Loader(), {"s.t": ["b", "a"]})
["s.t: columns ['a', 'b'] differ from ['b', 'a']"]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# map_label

```python
map_label() -> str
```

Use this when you need the label of a map: 'synthetic data' and the basemap attribution, because the networks drawn on the map are fictional (visualisations.md).

Rule: the text SYNTHETIC_LABEL, a semicolon and a space, then the attribution text with a copyright sign and 'OpenStreetMap contributors'; nothing is computed.

## Args

None: the function takes no input.

## Returns

str: the label, "synthetic data; " followed by the attribution.

## Raises

None: the function takes no input and has no error path.

## Example

```python
>>> from halvaro.core import map_label
>>> map_label().startswith("synthetic data; ")
True
>>> map_label().endswith("OpenStreetMap contributors")
True
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# mark_aggregate

```python
mark_aggregate(frame: pd.DataFrame, restricted_column: str, group_columns: Sequence[str] = (), min_group: int | None = None, count_column: str | None = None) -> RestrictedAggregate
```

Use this when you have checked an aggregate of a restricted measure and want to hand it on marked as safe to show.

Rule: the frame is first checked with assert_aggregate (same arguments, same refusals); when it passes, it is wrapped unchanged together with the column name, the group columns as a tuple and min_group.

## Args

frame: The aggregate, one row per group.
restricted_column: The column that holds the restricted measure; it must be a column of the frame.
group_columns: The columns the aggregate is grouped by. Optional; kept as a tuple in the result.
min_group: The smallest number of people a group may have. Optional; kept in the result.
count_column: The column with the number of people per group. Needed when min_group is given.

## Returns

RestrictedAggregate: a record with the fields frame, restricted_column, group_columns (a tuple) and min_group.

## Raises

FrameError: restricted_column is not a column of the frame, min_group is given without a count_column that exists in the frame, or count_column does not hold numbers.
AggregateRefusal: a column or index level holds an EMP key, or one or more groups have a count below min_group or no count.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import mark_aggregate
>>> frame = pd.DataFrame({"grade": ["A", "B"], "measure": [10.0, 20.0], "people": [3, 2]})
>>> marked = mark_aggregate(frame, "measure", ["grade"], min_group=2, count_column="people")
>>> marked.restricted_column, marked.group_columns, marked.min_group, len(marked.frame)
('measure', ('grade',), 2, 2)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# master_of

```python
master_of(prefix: str) -> MasterInfo
```

Use this when you have a key prefix and need the entity it names and the table that is its master.

Rule: the prefix is looked up in the master list of the design (master-of.yaml): the entity, the source, the table, the key column and the stage at which the master becomes visible.

## Args

prefix: A key prefix such as EMP.

## Returns

MasterInfo: prefix, entity, source, table, column and stage.

## Raises

KeyFormatError: the prefix has no master.

## Example

```python
>>> from halvaro.core import master_of
>>> info = master_of("EMP")
>>> info.source, info.table, info.stage
('hr', 'employee', 'day1')
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# month_end

```python
month_end(period: str) -> dt.date
```

Use this when you need the last calendar day of a period written YYYY-MM.

## Args

period: A period as text, for example "2026-02".

## Returns

datetime.date: the last day of that month, leap years included.

## Raises

PeriodError: the text is not a period of the form YYYY-MM with a month from 01 to 12.

## Example

```python
>>> from halvaro.core import month_end
>>> month_end("2026-02")
datetime.date(2026, 2, 28)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# month_start

```python
month_start(period: str) -> dt.date
```

Use this when you need the first calendar day of a period written YYYY-MM.

## Args

period: A period as text, for example "2026-02".

## Returns

datetime.date: the first day of that month.

## Raises

PeriodError: the text is not a period of the form YYYY-MM.

## Example

```python
>>> from halvaro.core import month_start
>>> month_start("2026-02")
datetime.date(2026, 2, 1)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# net_working_days

```python
net_working_days(persons: pd.DataFrame, leave: pd.DataFrame, start: dt.date, end: dt.date, *, person_key: str = 'emp_key', region_column: str = 'region', leave_types: Sequence[str] | None = None) -> pd.DataFrame
```

Use this when you need, per person, the working days of a period, the leave days that fall on working days and the days left after leave.

Rule: working days are counted per person with is_working_day for the region of that person, from start to end, both days included, and carry the status of the facts that calendar reads (VERIFY). A leave record covers its start and end days both included; the records of one person are merged day by day, so overlapping leave is counted once, and only days that are also working days count as leave days. Leave days outside the period are ignored. net_days is working_days minus leave_days.

## Args

persons: One row per person with the person key and the region, for example DK.
leave: Leave records with the person key, start, end and, when leave_types is used, leave_type.
start: First day of the period.
end: Last day of the period; it must not be before start (an empty range fails inside numpy).
person_key: The name of the person key column in both frames. Optional, default emp_key.
region_column: The name of the region column in persons. Optional, default region.
leave_types: The leave types to count. Optional; without it every record counts.

## Returns

pandas.DataFrame: one row per row of persons, in that order, with the columns person_key, region_column, working_days, leave_days and net_days (whole numbers).

## Raises

FrameError: persons lacks the person key or the region column, leave lacks the person key, start or end, end is before start, or a leave record that is read has a null start or end.
UnknownRegion: a region in persons is none of DK, DE-HH and DE-NI.
KeyError: leave_types is given but leave has no leave_type column.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.core import net_working_days
>>> persons = pd.DataFrame({"emp_key": ["EMP-000001", "EMP-000002"], "region": ["DK", "DK"]})
>>> leave = pd.DataFrame({"emp_key": ["EMP-000001"] * 3,
...                       "start": [dt.date(2026, 3, 10), dt.date(2026, 3, 11), dt.date(2026, 3, 14)],
...                       "end": [dt.date(2026, 3, 11), dt.date(2026, 3, 12), dt.date(2026, 3, 15)]})
>>> net_working_days(persons, leave, dt.date(2026, 3, 9), dt.date(2026, 3, 15))
      emp_key region  working_days  leave_days  net_days
0  EMP-000001     DK             5           3         2
1  EMP-000002     DK             5           0         5
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `legal.public_holidays.DK_store_bededag_abolished_from`, `legal.public_holidays.DE_reformationstag_from`.

Source columns: `hr.leave_record.start`, `hr.leave_record.end`, `hr.leave_record.leave_type`.

# parse_key

```python
parse_key(text: str) -> KeyParts
```

Use this when you have the text of a typed key such as EMP-000001 and need its prefix, number, width and family.

Rule: the text must be a prefix of the key list, a dash and digits of the width the prefix has. Natural labels such as GL accounts are read by parse_label, not here.

## Args

text: The key as text.

## Returns

KeyParts: prefix, number (a whole number), width (the number of digits), family and entity.

## Raises

KeyFormatError: the text is not a typed key, the prefix is not known, or the digits do not match the width of the prefix.

## Example

```python
>>> from halvaro.core import parse_key
>>> parse_key("EMP-000001")
KeyParts(prefix='EMP', number=1, width=6, family='transactional', entity='employee')
>>> parse_key("EMP-1")
Traceback (most recent call last):
...
halvaro.core.errors.KeyFormatError: 'EMP-1' does not match ^EMP-[0-9]{6}$ (width 6, family transactional)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# parse_label

```python
parse_label(text: str) -> LabelParts
```

Use this when you have a natural label (a budget, forecast, waste or ground label) or a GL account and need its parts.

Rule: the text before the first dash picks the label kind; the label must match the pattern of its kind. A GL account is read as a key of the GL prefix.

## Args

text: The label as text.

## Returns

LabelParts: prefix, text, source, table and column of the master.

## Raises

KeyFormatError: the text is not a known label or does not match the pattern of its kind.

## Example

```python
>>> from halvaro.core import parse_label
>>> label = parse_label("GL-7000")
>>> label.prefix, label.table
('GL', 'gl_account')
>>> parse_label("XX-1")
Traceback (most recent call last):
...
halvaro.core.errors.KeyFormatError: 'XX-1' is not a natural label; known: ...
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# parse_period

```python
parse_period(text: str) -> tuple[int, int]
```

Use this when you have a period written YYYY-MM and need its year and month as numbers.

## Args

text: The period as text, for example "2026-11".

## Returns

tuple: (year, month) as two whole numbers.

## Raises

PeriodError: the text is not a period of the form YYYY-MM with a month from 01 to 12 and a year from 0001 to 9999.

## Example

```python
>>> from halvaro.core import parse_period
>>> parse_period("2026-11")
(2026, 11)
>>> parse_period("2026-13")
Traceback (most recent call last):
...
halvaro.core.errors.PeriodError: '2026-13' is not a period; expected YYYY-MM such as 2026-11, with a year from 0001 to 9999
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# period_of

```python
period_of(day: dt.date) -> str
```

Use this when you have a date and need its period written YYYY-MM.

## Args

day: A date (a datetime.date or a timestamp).

## Returns

str: the period, for example 2026-03.

## Raises

PeriodError: day is not a date or a timestamp (a text, for example).

## Example

```python
>>> import datetime as dt
>>> from halvaro.core import period_of
>>> period_of(dt.date(2026, 3, 31))
'2026-03'
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# period_range

```python
period_range(first: str, last: str) -> list[str]
```

Use this when you need every month between two periods, both included, as a list of periods.

Rule: the list runs from first to last in steps of one month. When last is before first the list is empty.

## Args

first: The first period as text, for example "2026-11".
last: The last period as text.

## Returns

list: the periods YYYY-MM from first to last, oldest first; empty when last is before first.

## Raises

PeriodError: first or last is not a period of the form YYYY-MM.

## Example

```python
>>> from halvaro.core import period_range
>>> period_range("2026-11", "2027-02")
['2026-11', '2026-12', '2027-01', '2027-02']
>>> period_range("2027-02", "2026-11")
[]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# public_holidays

```python
public_holidays(year: int, region: str) -> frozenset[dt.date]
```

Use this when you need the public holidays of a year in one of the three regions.

Rule: the dates are computed from the Easter date and the fixed dates of the region. The parameters are provisional (VERIFY) and the functions that read them carry that status.

## Args

year: The calendar year.
region: DK, DE-HH or DE-NI.

## Returns

frozenset: the holidays as datetime.date values, all in the year.

## Raises

UnknownRegion: the region is none of DK, DE-HH and DE-NI.

## Example

```python
>>> from halvaro.core import public_holidays
>>> days = public_holidays(2026, "DK")
>>> all(d.year == 2026 for d in days), type(days).__name__
(True, 'frozenset')
>>> public_holidays(2026, "XX")
Traceback (most recent call last):
...
halvaro.core.errors.UnknownRegion: region 'XX' is unknown; use one of DK, DE-HH, DE-NI
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `legal.public_holidays.DK_store_bededag_abolished_from`, `legal.public_holidays.DE_reformationstag_from`.

Source columns: none (inputs are passed in).

# rdiv

```python
rdiv(a: Any, b: int) -> Any
```

Use this when you divide whole cents by a whole number and the result must be whole cents too.

Rule: integer division rounded half away from zero, so 7 divided by 2 is 4 and minus 7 divided by 2 is minus 4. The divisor should be positive; this is not checked, so a zero divisor gives 0 with a numpy warning.

## Args

a: The dividend, one whole number or an array of them.
b: The divisor, a positive whole number.

## Returns

The quotient as whole numbers, of the shape of a.

## Raises

ValueError: a is a text or cannot be converted to numbers (the error of numpy when it converts the values).

## Example

```python
>>> from halvaro.core import rdiv
>>> int(rdiv(7, 2)), int(rdiv(-7, 2)), int(rdiv(6, 4))
(4, -4, 2)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# reduce_chunks

```python
reduce_chunks(chunks: Iterable[pd.DataFrame], by: str | Sequence[str], aggregations: Mapping[str, tuple[str, str]]) -> pd.DataFrame
```

Use this when the rows come as an iterable of frames (chunks) and you need grouped sums, counts, minima or maxima with the same result as one frame, without holding all rows at once.

Rule: each chunk is reduced on its own per group, then the partial results are combined (sum for sum and count, min of minima, max of maxima), so memory is one chunk plus one row per group. count counts the non null values. Groups with a null key are kept. The result is sorted by the by columns. With no by columns the result has one row over all chunks. An empty chunk adds nothing; when every chunk is empty the result has no rows.

## Args

chunks: The frames to reduce, for example read one after the other. At least one frame is needed; an empty frame is fine.
by: The column or columns to group by, a name or a list. An empty list gives one row over all rows.
aggregations: A mapping from an output column to a pair (input column, function), the function being sum, count, min or max.

## Returns

pandas.DataFrame: the by columns followed by the output columns in the order of aggregations, one row per group, sorted by the by columns.

## Raises

FrameError: chunks is one frame and not an iterable of frames; an aggregation is not a (column, function) pair; a function is none of sum, count, min and max; no chunk was given; or a chunk lacks a by column or an input column (the message names the chunk number).

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import reduce_chunks
>>> first = pd.DataFrame({"g": ["x", "x", "y"], "v": [1, 2, 3], "w": [1, 2, None]})
>>> second = pd.DataFrame({"g": ["y", "z"], "v": [10, 20], "w": [None, 4]})
>>> reduce_chunks([first, second], "g", {"total": ("v", "sum"), "n": ("w", "count")})
   g  total  n
0  x      3  2
1  y     13  0
2  z     20  1
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# region_of

```python
region_of(site_key: str | None = None, *, country: str | None = None) -> str
```

Use this when you need the calendar region (DK, DE-HH or DE-NI) of a site or of a country with one region.

Rule: a site key gives the region of that site. A country gives its region only when it has exactly one (Denmark); Germany has two, so the site key of the person's team is needed.

## Args

site_key: The key of a site, for example "SITE-05". Optional.
country: DK, when no site key is given.

## Returns

str: the region.

## Raises

UnknownRegion: the site key is not a known site, the country is DE (two regions, pass the site key) or the country has no region.

## Example

```python
>>> from halvaro.core import region_of
>>> region_of("SITE-05"), region_of(country="DK")
('DE-HH', 'DK')
>>> region_of(country="DE")
Traceback (most recent call last):
...
halvaro.core.errors.UnknownRegion: country DE has two regions (DE-HH, DE-NI); pass the site key of the person's team
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.site.site_key`, `hr.site.country`.

# release_now

```python
release_now(data_releases: Mapping[str, pd.DataFrame]) -> ReleaseInfo
```

Use this when you need the one release identity (release, now, generated_at, base seed and increment) that all loaded sources share.

Rule: each data_release frame must hold exactly one row. The five values are compared as text across the sources and must be equal; the result is then built from them, with now as a date, generated_at as a timestamp and increment as a whole number.

## Args

data_releases: The data_release frame of each source as {source: frame}, with the columns release, now, generated_at, base_seed and increment.

## Returns

ReleaseInfo: a named tuple with release (text), now (date), generated_at (timestamp), base_seed (as stored) and increment (whole number).

## Raises

FrameMissing: no frame was passed.
FrameError: a frame does not have exactly one row, increment is not a whole number, or now or generated_at is not a date.
ReleaseMismatch: the sources disagree on one of the five values.
KeyError: a frame lacks one of the five columns.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import release_now
>>> row = {"release": ["r1"], "now": ["2026-11-30"], "generated_at": ["2026-12-01 08:00:00"], "base_seed": ["seed-a"], "increment": [2]}
>>> info = release_now({"hr": pd.DataFrame(row), "finance": pd.DataFrame(row)})
>>> info.release, info.now.isoformat(), info.increment
('r1', '2026-11-30', 2)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.data_release.release`.

# require_columns

```python
require_columns(context: Context, columns: Sequence[str]) -> None
```

Use this when a function reads columns that are restricted (pay, birth date) and must refuse a session that may not read them.

Rule: only the columns that the data dictionary lists as restricted count. When the context has restricted access nothing happens.

## Args

context: The caller (stage, role and whether restricted columns may be read).
columns: Column ids of the form source.table.column, for example "hr.employment_term.base_salary".

## Returns

None: nothing happens when no column is restricted or the context may read them.

## Raises

RestrictedColumnRefusal: a column is restricted and the context has no restricted access; the message names the column, the role and the stage.

## Example

```python
>>> from halvaro.core import Context, require_columns
>>> analyst = Context(stage="day1", role="analyst")
>>> require_columns(analyst, ["hr.employee.emp_key"])
>>> require_columns(analyst, ["hr.employment_term.base_salary"])
Traceback (most recent call last):
...
halvaro.core.errors.RestrictedColumnRefusal: Column hr.employment_term.base_salary is restricted; role analyst at stage day1 may not read it. Use an aggregate above the minimum group size or a role with restricted access.
>>> require_columns(Context(stage="day1", role="analyst", restricted_ok=True), ["hr.employment_term.base_salary"])
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# require_frame_columns

```python
require_frame_columns(frame: pd.DataFrame, source_table: str, columns: Sequence[str] | str) -> None
```

Use this when a loaded frame must carry the source column names of a table before you use it, so a renamed or dropped column is caught early.

Rule: the table must be a 'source.table' of the data dictionary, every named column must be a column of that table in the dictionary, and every named column must exist in the frame. Extra columns in the frame are fine.

## Args

frame: The loaded frame of the table.
source_table: The table as source.table, for example "hr.employee".
columns: The column names the caller needs, as a list or a single name.

## Returns

None: nothing happens when all named columns are in the dictionary and in the frame.

## Raises

FrameError: source_table is not a source.table of the data dictionary, a named column is not a column of that table in the dictionary, or a named column is missing in the frame.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import require_frame_columns
>>> frame = pd.DataFrame({"emp_key": ["EMP-000001"], "hire_date": ["2020-01-01"]})
>>> require_frame_columns(frame, "hr.employee", ["emp_key", "hire_date"])
>>> require_frame_columns(frame, "hr.employee", ["emp_key", "email"])
Traceback (most recent call last):
...
halvaro.core.errors.FrameError: the frame for hr.employee lacks column(s) email; it has emp_key, hire_date. Load the source column names without renaming them.
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# require_sources

```python
require_sources(context: Context, sources: Sequence[str], function: str | None = None) -> None
```

Use this when a function reads tables of some sources and must refuse a session whose stage does not hold them yet.

Rule: the sources are reduced to their source name (the part before the first dot). Every source whose stage is above the stage of the context is named in the refusal together with the stage where it appears.

## Args

context: The caller (stage, role, release date, restricted access).
sources: Source names or table names such as "hr.employee" or "finance".
function: The name of the calling function, written into the refusal. Optional.

## Returns

None: nothing happens when every source is visible at the stage of the context.

## Raises

StageRefusal: one or more sources appear at a later stage than the context holds.
FrameError: a source name is unknown, for example "zz"; the message lists the known sources.

## Example

```python
>>> from halvaro.core import Context, require_sources
>>> day1 = Context(stage="day1", role="analyst")
>>> require_sources(day1, ["hr.employee"])
>>> require_sources(day1, ["finance.journal_line"], function="trial_balance")
Traceback (most recent call last):
...
halvaro.core.errors.StageRefusal: Sources finance appear at stage month3; the session holds stage day1 (trial_balance). Ask for a session at stage month3 or use only the sources of stage day1.
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# role_info

```python
role_info(role: pd.DataFrame, grade: pd.DataFrame) -> pd.DataFrame
```

Use this when you need per role its department and grade, with the grade level, name and bands.

Rule: the grade columns of grade_info are joined to the role frame on the grade key as a left join, so a role whose grade is not in the grade frame keeps its row and gets empty grade columns. The grade name arrives as name_grade because the role has a name of its own.

## Args

role: Role frame (hr.role) with role_key, name, dep_key and gra_key.
grade: Grade frame (hr.grade) with gra_key, level, name and the four band columns.

## Returns

pandas.DataFrame: role_key, name, dep_key, gra_key, level, name_grade, band_min_dkk, band_max_dkk, band_min_eur and band_max_eur, one row per role in the order of the role frame (as long as gra_key is unique in the grade frame).

## Raises

FrameError: the role frame or the grade frame lacks a column.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import role_info
>>> role = pd.DataFrame({"role_key": ["R1", "R2"], "name": ["Analyst", "Lead"], "dep_key": ["D1", "D1"], "gra_key": ["G1", "G9"]})
>>> grade = pd.DataFrame({"gra_key": ["G1"], "level": [3], "name": ["Grade 3"], "band_min_dkk": [10], "band_max_dkk": [20], "band_min_eur": [1], "band_max_eur": [2]})
>>> info = role_info(role, grade)
>>> info[["role_key", "gra_key", "level", "name_grade"]].to_dict("records")
[{'role_key': 'R1', 'gra_key': 'G1', 'level': 3.0, 'name_grade': 'Grade 3'}, {'role_key': 'R2', 'gra_key': 'G9', 'level': nan, 'name_grade': nan}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.role.role_key`, `hr.role.dep_key`, `hr.role.gra_key`, `hr.grade.level`.

# rows_on

```python
rows_on(frame: pd.DataFrame, on: dt.date, key: str | Sequence[str] | None = None, valid_from: str = 'valid_from', valid_to: str = 'valid_to') -> pd.DataFrame
```

Use this when a table has effective dating (valid_from, valid_to) and you need the rows that are valid on one date.

Rule: a row is valid on the date when valid_from is on or before it and valid_to is empty or on or after it. With key, two valid rows of the same key are refused instead of both being returned.

## Args

frame: The table, one row per version, with the two date columns.
on: The date.
key: Column name, or list of column names, that identify the thing the rows are versions of. Optional; without it no check for two valid rows is made.
valid_from: Name of the start column. Default "valid_from".
valid_to: Name of the end column; empty means open. Default "valid_to".

## Returns

pandas.DataFrame: the rows of the frame that are valid on the date, in the order of the frame.

## Raises

FrameError: a date column is missing from the frame.
AmbiguousKey: key is given and two rows with the same key are valid on the date.

## Example

```python
>>> import datetime as dt
>>> import pandas as pd
>>> from halvaro.core import rows_on
>>> versions = pd.DataFrame({"k": ["A", "A", "B"], "valid_from": ["2026-01-01", "2026-02-01", "2026-01-01"], "valid_to": ["2026-12-31", None, None]})
>>> rows_on(versions, dt.date(2026, 1, 15))["k"].tolist()
['A', 'B']
>>> rows_on(versions, dt.date(2026, 3, 1), key="k")
Traceback (most recent call last):
...
halvaro.core.errors.AmbiguousKey: Key A matches 2 candidates: valid_from=2026-01-01, valid_from=2026-02-01. Pass a date or a more specific key.
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# source_stage

```python
source_stage(source: str) -> str
```

Use this when you need to know at which stage a source (hr, finance, projects and so on) becomes visible to a session.

## Args

source: The name of the source, for example "hr".

## Returns

str: the stage, one of day1, month3 and month12.

## Raises

FrameError: the source is not known; the message lists the known sources.

## Example

```python
>>> from halvaro.core import source_stage
>>> source_stage("hr"), source_stage("finance")
('day1', 'month3')
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# stage_banner

```python
stage_banner(refusal: HalvaroError) -> str
```

Use this when a stage or column refusal must be shown to the user as one plain line.

Rule: a StageRefusal gives the missing sources, the stage where they appear and the stage the session holds. A RestrictedColumnRefusal gives the column, the role and the stage. Any other error gives its own message text.

## Args

refusal: The error that was raised, normally a StageRefusal or a RestrictedColumnRefusal.

## Returns

str: one line of text.

## Raises

This function raises no error of its own.

## Example

```python
>>> from halvaro.core import StageRefusal, stage_banner
>>> stage_banner(StageRefusal(["finance"], "month3", "day1"))
'Needs finance (appears at stage month3). This session holds stage day1.'
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# stage_matrix

```python
stage_matrix(function_id: str, frames: Mapping[str, pd.DataFrame], call: Callable[[dict[str, pd.DataFrame], Context], Any], *, role: str = 'test', stages: Sequence[str] | None = None, strict: bool = True) -> list[dict[str, Any]]
```

Use this when you need to prove that a function gives a result where all its sources are visible and refuses, naming the missing sources, where they are not.

Rule: for each stage the call is run with only those frames whose source the stage can see. A stage that sees every registered source of the function must give a result; a stage that misses a source must raise StageRefusal naming exactly the missing sources. A result where a refusal was expected, a refusal naming other sources, or a refusal at a stage that misses none is not ok; any other exception from call propagates.

## Args

function_id: The id of a registered function, for example "halvaro.core.org.cost_centre_of_team".
frames: The frames to offer, as {"source.table": frame}.
call: A function that takes the visible frames (a dict of the same form) and a Context, and runs the function under test.
role: The role written into the Context. Default "test".
stages: The stages to run, in order. Default: all stages of the snapshot.
strict: Whether a row that is not ok raises AssertionError. Default True.

## Returns

list: one dict per stage with the keys stage, expected ("result" or "refusal"), outcome ("result" or "refusal") and ok (True or False).

## Raises

HalvaroError: the function id is not registered.
ProfileError: a stage is not a known stage.
AssertionError: strict is true and a stage did not behave as expected.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import cost_centre_of_team, stage_matrix
>>> frames = {"hr.team": pd.DataFrame({"team_key": ["T1"], "cost_centre_key": ["CC-1"]})}
>>> rows = stage_matrix("halvaro.core.org.cost_centre_of_team", frames, lambda visible, ctx: cost_centre_of_team(visible["hr.team"], "T1"), stages=["day1", "month3"])
>>> [(r["stage"], r["outcome"], r["ok"]) for r in rows]
[('day1', 'result', True), ('month3', 'result', True)]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# stage_placeholder

```python
stage_placeholder(refusal: Exception) -> str
```

Use this when you need the panel text for a chart whose source is above the stage of the session: what is missing, at which stage it appears and what the session sees.

Rule: the one-line stage banner of the refusal followed by "The chart is not drawn."; nothing is estimated or drawn.

## Args

refusal: The StageRefusal that the data call raised; any other exception type is rejected.

## Returns

str: the panel text.

## Raises

FrameError: refusal is not a StageRefusal.

## Example

```python
>>> from halvaro.core import StageRefusal, stage_placeholder
>>> stage_placeholder(StageRefusal(["finance.invoice.amount"], "month3", "day1"))
'Needs finance.invoice.amount (appears at stage month3). This session holds stage day1. The chart is not drawn.'
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# strip_restricted

```python
strip_restricted(frame: pd.DataFrame, context: Context) -> pd.DataFrame
```

Use this when you have a frame and must remove the restricted columns (pay, birth date) before a session that may not read them sees it.

Rule: when the context has restricted access the frame is returned as it is. Otherwise every column whose header, read after its last dot, equals the bare name of a restricted column of the data dictionary is dropped, so a qualified header such as 'table.column' or the full 'source.table.column' id cannot carry it past the guard. Other columns, their order and the rows are kept.

## Args

frame: The frame to clean.
context: The caller (stage, role and whether restricted columns may be read).

## Returns

pandas.DataFrame: the frame without the restricted columns, or the same frame when the context may read them.

## Raises

This function raises no error of its own.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context, strip_restricted
>>> frame = pd.DataFrame({"emp_key": ["EMP-000001"], "hr.employee.birth_date": [0], "team": ["A"]})
>>> list(strip_restricted(frame, Context(stage="day1", role="analyst")).columns)
['emp_key', 'team']
>>> list(strip_restricted(frame, Context(stage="day1", role="analyst", restricted_ok=True)).columns)
['emp_key', 'hr.employee.birth_date', 'team']
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# synthetic_label

```python
synthetic_label() -> str
```

Use this when you need the text 'synthetic data' that goes in the corner of every chart, table and map, in both modes.

Rule: returns the constant text SYNTHETIC_LABEL; nothing is computed.

## Args

None: the function takes no input.

## Returns

str: the text "synthetic data".

## Raises

None: the function takes no input and has no error path.

## Example

```python
>>> from halvaro.core import synthetic_label
>>> synthetic_label()
'synthetic data'
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# table_key

```python
table_key(source_table: str) -> tuple[str, ...]
```

Use this when you need the columns that make up the primary key of a table, composite keys included.

Rule: the key columns are read from the table keys of the release, in the order they are listed there.

## Args

source_table: The table as source.table, for example "competence.crew_plan".

## Returns

tuple: the names of the key columns, one for a simple key and several for a composite key.

## Raises

FrameError: the table is not a table of the release.

## Example

```python
>>> from halvaro.core import table_key
>>> table_key("competence.crew_plan")
('prj_key', 'emp_key')
>>> table_key("competence.nothing")
Traceback (most recent call last):
...
halvaro.core.errors.FrameError: competence.nothing is not a table of the release; use source.table
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# team_context

```python
team_context(team: pd.DataFrame, site: pd.DataFrame) -> pd.DataFrame
```

Use this when you need per team its department, cost centre, legal entity, site, country and calendar region in one frame.

Rule: the site frame is joined to the team frame on the site key; the region is read from the site key by region_of.

## Args

team: Team frame (hr.team) with team_key, dep_key, cost_centre_key, legal_entity_key and site_key.
site: Site frame (hr.site) with site_key and country.

## Returns

pandas.DataFrame: the five team columns, country and region, one row per team in the order of the team frame.

## Raises

FrameError: a frame lacks a column.
UnknownRegion: a team has a site that has no region.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import team_context
>>> team = pd.DataFrame({"team_key": ["T1"], "dep_key": ["D1"], "cost_centre_key": ["CC-1"], "legal_entity_key": ["LE-01"], "site_key": ["SITE-05"]})
>>> site = pd.DataFrame({"site_key": ["SITE-05"], "country": ["DE"]})
>>> team_context(team, site)[["team_key", "country", "region"]].to_dict("records")
[{'team_key': 'T1', 'country': 'DE', 'region': 'DE-HH'}]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.team.team_key`, `hr.team.dep_key`, `hr.team.cost_centre_key`, `hr.team.legal_entity_key`, `hr.team.site_key`, `hr.site.country`.

# team_of_cost_centre

```python
team_of_cost_centre(team: pd.DataFrame, cost_centre_key: str) -> str
```

Use this when you need the team that owns one cost centre.

Rule: the team frame is searched for the cost centre key and the team key of that one row is returned. A cost centre that is missing or shared by several teams is refused, never guessed.

## Args

team: Team frame (hr.team) with team_key and cost_centre_key.
cost_centre_key: The cost centre key, for example "CC-1".

## Returns

str: the key of the team that has the cost centre, for example "T1".

## Raises

FrameError: the frame lacks a column, or the cost centre does not belong to exactly one team.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import team_of_cost_centre
>>> team = pd.DataFrame({"team_key": ["T1", "T2"], "cost_centre_key": ["CC-1", "CC-2"]})
>>> team_of_cost_centre(team, "CC-2")
'T2'
>>> team_of_cost_centre(team, "CC-9")
Traceback (most recent call last):
...
halvaro.core.errors.FrameError: cost centre CC-9 belongs to 0 teams; expected 1
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `hr.team.team_key`, `hr.team.cost_centre_key`.

# to_cents

```python
to_cents(amount: Any) -> Any
```

Use this when you need an amount as whole cents, so that sums and comparisons are exact.

Rule: the amount times 100 rounded to a whole number; a tie goes to the even cent (0.125 is 12.5 cents and gives 12). A null, an infinite amount or an amount whose cents do not fit in 64 bits is refused.

## Args

amount: One amount, a list or array of amounts, or a Series; the index of a Series is kept.

## Returns

The integer cents: a whole number for one amount, an array for an array, a Series for a Series.

## Raises

FrameError: an amount is null, infinite, or has cents that do not fit in 64 bits; the message says how many.

## Example

```python
>>> from halvaro.core import to_cents
>>> int(to_cents(1234.56)), int(to_cents(0.125)), int(to_cents(-0.125))
(123456, 12, -12)
>>> to_cents(float("nan"))
Traceback (most recent call last):
...
halvaro.core.errors.FrameError: to_cents got 1 null amount(s); cents are whole numbers and a null has no cents. Drop or fill the nulls first
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# visible_sources

```python
visible_sources(stage: str) -> frozenset[str]
```

Use this when you need the sources that a session at a stage can see.

Rule: the stages are cumulative, so a later stage sees everything an earlier stage sees.

## Args

stage: The stage, one of day1, month3 and month12.

## Returns

frozenset: the names of the visible sources.

## Raises

ProfileError: the stage is not one of day1, month3 and month12.

## Example

```python
>>> from halvaro.core import visible_sources
>>> "hr" in visible_sources("day1"), "finance" in visible_sources("day1"), "finance" in visible_sources("month3")
(True, False, True)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).

# working_days

```python
working_days(start: dt.date, end: dt.date, region: str) -> int
```

Use this when you need the number of working days between two dates in a region, both days included.

Rule: each day of the range is counted when is_working_day is true for the region. A range whose end is before its start has no days and the result is zero.

## Args

start: First day of the range.
end: Last day of the range.
region: DK, DE-HH or DE-NI.

## Returns

int: the number of working days in [start, end].

## Raises

UnknownRegion: the region is none of DK, DE-HH and DE-NI, also for an empty range.

## Example

```python
>>> import datetime as dt
>>> from halvaro.core import working_days
>>> working_days(dt.date(2026, 3, 9), dt.date(2026, 3, 13), "DK")
5
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `legal.public_holidays.DK_store_bededag_abolished_from`, `legal.public_holidays.DE_reformationstag_from`.

Source columns: none (inputs are passed in).

# year_of

```python
year_of(period: str, start_month: int) -> int
```

Use this when you need the year, counted from a start month, that a period belongs to: a fiscal year or a holiday year that does not begin in January.

Rule: a period from the start month on belongs to the year it is in; an earlier period belongs to the year before. With start month 1 this is the calendar year.

## Args

period: A period as text, for example "2026-03".
start_month: The month in which the year starts, from 1 to 12. The caller gets it from a fact or a setting of its own.

## Returns

int: the year that starts in the start month and contains the period.

## Raises

PeriodError: the start month is not from 1 to 12, or the period is not of the form YYYY-MM.

## Example

```python
>>> from halvaro.core import year_of
>>> year_of("2026-03", 9), year_of("2026-10", 9), year_of("2026-03", 1)
(2025, 2026, 2026)
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: none (inputs are passed in).
