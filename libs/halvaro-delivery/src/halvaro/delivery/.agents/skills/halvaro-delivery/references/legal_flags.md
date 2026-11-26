# legal_flags

Module `halvaro.delivery.contracts`. Import: `from halvaro.delivery import legal_flags`.

```python
legal_flags(clause: pd.DataFrame, contract: pd.DataFrame, project: pd.DataFrame, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the clauses that carry a verify mark or a legal note, with the works warranty years checked against the legal value of the project's country.

The verify mark and the legal note always agree in the data. For the works warranty clauses (clause_type warranty, variant works, parameter warranty_years) the warranty years are compared with the legal fact of the project's country (DK or DE: legal.contracts.warranty_years.DK and legal.contracts.warranty_years.DE): warranty_expected and warranty_matches. A works warranty of a contract with no project, or of another country, has no check (null). Columns: con_key, clause_no, clause_type, variant, verify, legal_note, country, warranty_years, warranty_expected, warranty_matches, fact_status (the status of the fact used: VERIFY for the provisional legal values).

Args:
    clause: The contracts.clause frame; it needs con_key, clause_no, clause_type, variant, param_name, param_value, verify and legal_note.
    contract: The contracts.contract frame, one row per con_key; it needs con_key and prj_key.
    project: The projects.project frame, one row per prj_key; it needs prj_key and country.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A DataFrame with con_key, clause_no, clause_type, variant, verify, legal_note, country, warranty_years, warranty_expected, warranty_matches (nullable boolean) and fact_status, sorted by con_key and clause_no, index reset.

Raises:
    FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; the contract or project frame repeats its key; clause.verify has nulls.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import legal_flags
    >>> ctx = Context(stage="month12", role="analyst")
    >>> clause = pd.DataFrame({"con_key": ["CON-900001", "CON-900001"], "clause_no": [1, 2], "clause_type": ["warranty", "payment"],
    ...                        "variant": ["works", "std"], "param_name": ["warranty_years", "days"], "param_value": [5.0, 30.0],
    ...                        "verify": [True, False], "legal_note": ["check", None]})
    >>> con = pd.DataFrame({"con_key": ["CON-900001"], "prj_key": ["PRJ-900001"]})
    >>> prj = pd.DataFrame({"prj_key": ["PRJ-900001"], "country": ["DK"]})
    >>> out = legal_flags(clause, con, prj, context=ctx)
    >>> out[["clause_no", "country"]].values.tolist()
    [[1, 'DK']]
    >>> bool(out["warranty_expected"].notna().iloc[0])
    True

## Source columns

- `contracts.clause.con_key`
- `contracts.clause.clause_no`
- `contracts.clause.clause_type`
- `contracts.clause.variant`
- `contracts.clause.param_name`
- `contracts.clause.param_value`
- `contracts.clause.param2_name`
- `contracts.clause.param2_value`
- `contracts.clause.valid_from`
- `contracts.clause.valid_to`
- `contracts.clause.verify`
- `contracts.clause.legal_note`
- `contracts.contract.prj_key`
- `projects.project.country`

## Facts read

Read with `halvaro.core.fact(id)`; a fact with status proposed or VERIFY is provisional.

- `legal.contracts.warranty_years.DK`
- `legal.contracts.warranty_years.DE`
