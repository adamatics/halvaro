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
