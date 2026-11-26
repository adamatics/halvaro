# answer_pack

Module `halvaro.esg.data_requests`. Import: `from halvaro.esg import answer_pack`.

```python
answer_pack(req: pd.DataFrame, totals: pd.DataFrame, targets: pd.DataFrame, *, context: halvaro.core.access.Context) -> dict[str, Any]
```

Use this when you need the numbers to answer a customer questionnaire: the scope totals, the months covered, the targets and the notes.

The numbers a questionnaire needs, no document text: for the request row `req` (one row) the scope totals `totals` (the output of scope_totals, one entity row 'ALL' and a year), both scope 2
methods side by side and never added, the months covered, the restatement note when the totals are on the current basis, and the targets with their basis. The two scope 2 values are never summed.

Args:
    req: One row of the request with the columns cus_key and request_no.
    totals: One row of scope_totals for the entity 'ALL' (le_key, when present, must be 'ALL') with the columns year, months, scope1, scope2_location, scope2_market and scope3, and optionally basis; none of months and the scope values may be null.
    targets: The energy-esg.target table with the columns target_no, scope, baseline_year, target_year, reduction_percent, basis and status.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A dict with the keys request (cus_key and request_no as a tuple), year, months, scope1, scope2_location, scope2_market, scope3 (floats), targets (the target rows as a list of dicts, sorted by target_no) and notes (a list of texts: the basis of the totals, that scope 2 is given by both methods and not added, that the emission factors are synthetic, and the number of months when the year has fewer than 12).

Raises:
    FrameError: req, totals or targets lacks a needed column.
    FrameError: req or totals does not have exactly one row; totals is not the whole company (le_key other than 'ALL'); year, months or a scope value in totals is null.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import answer_pack
    >>> ctx = Context(stage="month12", role="analyst")
    >>> req = pd.DataFrame({"cus_key": ["CUS-900001"], "request_no": [1]})
    >>> totals = pd.DataFrame({"le_key": ["ALL"], "year": [2031], "months": [12], "scope1": [100.0], "scope2_location": [50.0],
    ...                        "scope2_market": [20.0], "scope3": [300.0], "basis": ["current"]})
    >>> targets = pd.DataFrame({"target_no": [1], "scope": ["1"], "baseline_year": [2029], "target_year": [2035],
    ...                         "reduction_percent": [40.0], "basis": ["absolute"], "status": ["proposed"]})
    >>> pack = answer_pack(req, totals, targets, context=ctx)
    >>> pack["request"], pack["scope2_location"], pack["scope2_market"]
    (('CUS-900001', 1), 50.0, 20.0)
    >>> pack["notes"][0]
    'totals are on the current basis: earlier years may have been restated'

## Source columns

- `energy-esg.emission_line.kgco2e`
- `energy-esg.target.target_no`
