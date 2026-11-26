# write_down_journal

```python
write_down_journal(manual: pd.DataFrame, prj_key: str, *, gl_key: str = 'GL-5190', context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need the write-down lines booked on one project, from the manual journals.

Rule: the rows of the manual journals on the project and on the write-down account, in the order of posting date and journal number. There is no guess from a change of margin: a project without such a row gives an empty frame.

## Args

manual: The manual journals, the output of ledger.manual_journals, with le_key, journal_no, posting_date, description, gl_key, prj_key, currency, amount and amount_dkk.
prj_key: The project key.
gl_key: The write-down account. PROPOSED default GL-5190, until the fact fin.project_accounting.write_down_gl_key exists.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with le_key, journal_no, posting_date, description, currency, amount and amount_dkk; empty when the project has no write-down.

## Raises

FrameError: a column is missing or a posting date is not a date.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import write_down_journal
>>> ctx = Context(stage="month3", role="analyst")
>>> manual = pd.DataFrame({"le_key": ["LE-01"] * 2, "journal_no": ["J-2", "J-1"], "posting_date": ["2026-03-31", "2026-02-28"], "description": ["write down"] * 2,
...                        "gl_key": ["GL-5190"] * 2, "prj_key": ["PRJ-2"] * 2, "currency": ["DKK"] * 2, "amount": [50.0, 25.0], "amount_dkk": [50.0, 25.0]})
>>> write_down_journal(manual, "PRJ-2", context=ctx)[["journal_no", "posting_date", "amount_dkk"]].to_dict("records")
[{'journal_no': 'J-1', 'posting_date': '2026-02-28', 'amount_dkk': 25.0}, {'journal_no': 'J-2', 'posting_date': '2026-03-31', 'amount_dkk': 50.0}]
>>> write_down_journal(manual, "PRJ-9", context=ctx).empty
True
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.journal_header.source`, `finance.journal_header.posting_date`, `finance.journal_line.prj_key`, `finance.journal_line.gl_key`, `finance.journal_line.amount`, `finance.journal_line.amount_dkk`.
