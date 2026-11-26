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
