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
