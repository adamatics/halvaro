# manual_journals

```python
manual_journals(journal_header: pd.DataFrame, journal_line: pd.DataFrame, *, gl_key: str | None = None, prj_key: str | None = None, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need the lines of the journals that were posted by hand, optionally only those on one account or one project.

Rule: the journals whose header source is manual; their lines with the date and description of the header.

## Args

journal_header: Frame finance.journal_header with le_key, journal_no, source, posting_date and description.
journal_line: Frame finance.journal_line with le_key, journal_no, line_no, gl_key, prj_key, amount, amount_dkk and currency.
gl_key: Keep only the lines on this account. Optional.
prj_key: Keep only the lines on this project. Optional.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with le_key, journal_no, line_no, posting_date, description, gl_key, prj_key, currency, amount and amount_dkk of each line.

## Raises

FrameError: a column is missing or a manual journal is listed twice in the header frame.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import manual_journals
>>> ctx = Context(stage="month12", role="analyst")
>>> header = pd.DataFrame({"le_key": ["LE-01"] * 2, "journal_no": [1, 2], "source": ["manual", "auto"], "posting_date": ["2026-03-01"] * 2, "description": ["x", "y"]})
>>> lines = pd.DataFrame({"le_key": ["LE-01"] * 4, "journal_no": [1, 1, 2, 2], "line_no": [1, 2, 1, 2], "gl_key": ["GL-1", "GL-2"] * 2, "prj_key": [None] * 4,
...                       "amount": [10.0, -10.0, 5.0, -5.0], "amount_dkk": [10.0, -10.0, 5.0, -5.0], "currency": ["DKK"] * 4})
>>> manual_journals(header, lines, context=ctx)[["journal_no", "gl_key", "amount"]].values.tolist()
[[1, 'GL-1', 10.0], [1, 'GL-2', -10.0]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.journal_header.le_key`, `finance.journal_header.journal_no`, `finance.journal_header.source`, `finance.journal_header.posting_date`, `finance.journal_header.description`, `finance.journal_line.le_key`, `finance.journal_line.journal_no`, `finance.journal_line.line_no`, `finance.journal_line.gl_key`, `finance.journal_line.prj_key`, `finance.journal_line.amount`, `finance.journal_line.amount_dkk`, `finance.journal_line.currency`.
