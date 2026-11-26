# band_position

```python
band_position(frame: pd.DataFrame, grade: pd.DataFrame, *, context: Context, as_of: dt.date | None = None, bands_year: int = 2026) -> pd.DataFrame
```

Use this when you want to see where each person's pay lies in the band of the grade, in the currency of the person's term.

Rule: vs_midpoint is the rate over the band midpoint (the compa ratio); position_in_band is (rate less band minimum) over (maximum less minimum), so below 0 or above 1 is outside the band; in_band says whether it is inside. With as_of before bands_year (proposed 2026, the year the bands are set at) a warning says that the position is understated. The pay columns are restricted: the role must be allowed to read pay (a Context with restricted access), and a frame without the pay columns is refused.

## Args

frame: A pay frame (the output of pay_frame) with emp_key, gender (only F and M rows count), grade_key, currency, rate_local and compa.
grade: Grade frame (hr.grade) with gra_key and the band limits in DKK and EUR.
context: The caller; the role must be allowed to read pay.
as_of: The date the position is read at. Optional.
bands_year: The year the bands are set at. Default 2026 (proposed).

## Returns

pandas.DataFrame with emp_key, grade_key, currency, rate_local, band_min, band_mid, band_max, vs_midpoint, position_in_band and in_band.

## Raises

RestrictedColumnRefusal: the role may not read pay, or the frame has no pay columns.
FrameError: a column is missing, a grade is held twice or not at all, a term is not in DKK or EUR, or a band maximum is not above its minimum.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> access = Context(stage="month12", role="analyst", restricted_ok=True)
>>> from halvaro.hr import band_position
>>> people = pd.DataFrame({"emp_key": ["EMP-000001"], "gender": ["F"], "grade_key": ["GRA-4"], "currency": ["DKK"], "rate_local": [45000.0], "compa": [1.0]})
>>> grade = pd.DataFrame({"gra_key": ["GRA-4"], "level": [4], "band_min_dkk": [40000.0], "band_max_dkk": [50000.0], "band_min_eur": [5000.0], "band_max_eur": [6700.0]})
>>> band_position(people, grade, context=access)[["band_mid", "vs_midpoint", "position_in_band", "in_band"]].values.tolist()
[[45000.0, 1.0, 0.5, True]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): `world.fx_eur_dkk_fixed`.

Source columns: `hr.employment_term.base_salary`, `hr.employment_term.fte`, `hr.employment_term.currency`, `hr.employee.gender`, `hr.employee.hire_date`, `hr.employee.legal_entity_key`, `hr.team.dep_key`, `hr.grade.level`, `hr.grade.band_min_dkk`, `hr.grade.band_max_dkk`, `hr.grade.band_min_eur`, `hr.grade.band_max_eur`.
