# price_adjustment_terms

Module `halvaro.delivery.contracts`. Import: `from halvaro.delivery import price_adjustment_terms`.

```python
price_adjustment_terms(clause: pd.DataFrame, contract: pd.DataFrame, as_of: DateLike | None = None, *, context: halvaro.core.access.Context) -> PriceTerms
```

Use this when you need the price adjustment terms of the contracts (pass-through percent and threshold percent) and the customer project contracts that have no price clause.

The price adjustment clauses are returned with their parameters read by name: variant, pass_through_percent (the clause parameter of that name, `param_name`) and threshold_percent (`param2_name`), the first parameter and the second as they are, and n_price_clauses of the contract (a supplier contract can have several, a customer contract one). Customer project contracts with no price clause are returned in `without_clause` (the generator test cannot see them). With as_of only clauses valid on the date. The threshold is returned and applied nowhere (policy.pricing.pass_through_threshold_is_deductible, proposed).

Args:
    clause: The contracts.clause frame; it needs con_key, clause_no, clause_type, variant, param_name, param_value, param2_name, param2_value, valid_from and valid_to.
    contract: The contracts.contract frame, one row per con_key; it needs con_key, type and price_type.
    as_of: Optional day (a date, a Timestamp or an ISO text); when given, only clauses valid on it are used. None (the default) uses all price clauses.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A PriceTerms named tuple. `terms` has con_key, clause_no, variant, param_name, param_value, param2_name, param2_value, valid_from, valid_to, pass_through_percent, threshold_percent, n_price_clauses, type and price_type, sorted by con_key and clause_no. `without_clause` has con_key, type and price_type of the customer_project contracts with no price clause.

Raises:
    FrameError: a frame is not a DataFrame, has duplicate column names or lacks a needed column; the contract frame repeats a con_key; valid_from or valid_to holds a value that is not a date; as_of (when given) is a number, has a time zone or is not a date.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.delivery import price_adjustment_terms
    >>> ctx = Context(stage="month12", role="analyst")
    >>> cols = ["con_key", "clause_no", "clause_type", "variant", "param_name", "param_value", "param2_name", "param2_value", "valid_from", "valid_to"]
    >>> clause = pd.DataFrame([["CON-900001", 1, "price_adjustment", "index", "pass_through_percent", 80.0, "threshold_percent", 2.0, "2025-01-01", None]], columns=cols)
    >>> con = pd.DataFrame({"con_key": ["CON-900001", "CON-900002"], "type": ["customer_project", "customer_project"], "price_type": ["fixed", "fixed"]})
    >>> res = price_adjustment_terms(clause, con, context=ctx)
    >>> res.terms[["pass_through_percent", "threshold_percent"]].values.tolist()
    [[80.0, 2.0]]
    >>> res.without_clause["con_key"].tolist()
    ['CON-900002']

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
- `contracts.contract.type`
- `contracts.contract.price_type`
