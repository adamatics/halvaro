# expected_waste_lines

Module `halvaro.esg.recompute`. Import: `from halvaro.esg import expected_waste_lines`.

```python
expected_waste_lines(w: pd.DataFrame, f: pd.DataFrame, *, restate: Mapping[str, Any] | None = None, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the scope 3.5 waste emission lines that the waste records of each site, month and fraction should produce.

Waste lines (scope 3.5) from the waste records: tonnes times the factor of the fraction (category waste_<fraction>, region EU) valid on the first of the month. Same columns as expected_lines_s123 (ref_key is the site, subcategory the fraction, category waste_generated, unit t). The plan's oracle is one sided (a lower or missing line passes), recompute_diff checks both ways.

Args:
    w: The energy-esg.waste_record table with the columns site_key, period (text YYYY-MM), fraction and tonnes; one row per site, period and fraction.
    f: The energy-esg.emission_factor table with the columns efac_key, category, carrier, region, method, kgco2e_per_unit, valid_from, valid_to and factor_set.
    restate: None for the factors of the first day of each month, or a mapping with exactly the keys year and factor_date for the restated basis of that year, as in expected_lines_s123.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns of expected_lines_s123 (ref_key, period, scope, ghg_category, method, category, subcategory, quantity, unit, efac_key, factor, expected_kg), sorted by ref_key, period and subcategory; rows with zero tonnes give no line, and the frame is empty when there is none.

Raises:
    FrameError: w or f is not a frame or lacks a needed column; w has more than one row for a site, period and fraction; tonnes is null or negative.
    FrameError: restate is not a mapping with exactly the keys year and factor_date, the restate year has no period in the data, or a period is not text YYYY-MM.
    FrameError: a line has no valid factor or more than one valid factor on the first of its month.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.esg import expected_waste_lines
    >>> ctx = Context(stage="month12", role="analyst")
    >>> cols = ["efac_key", "category", "carrier", "region", "method", "kgco2e_per_unit", "valid_from", "valid_to", "factor_set"]
    >>> F = pd.DataFrame([("EF-900003", "waste_scrap", None, "EU", None, 12.5, "2031-01-01", None, "FS-A")], columns=cols)
    >>> W = pd.DataFrame({"site_key": ["SITE-900001"], "period": ["2031-03"], "fraction": ["scrap"], "tonnes": [3.0]})
    >>> out = expected_waste_lines(W, F, context=ctx)
    >>> out[["ref_key", "subcategory", "unit", "expected_kg"]].to_dict("records")
    [{'ref_key': 'SITE-900001', 'subcategory': 'scrap', 'unit': 't', 'expected_kg': 37.5}]

## Source columns

- `energy-esg.waste_record.site_key`
- `energy-esg.waste_record.period`
- `energy-esg.waste_record.fraction`
- `energy-esg.waste_record.tonnes`
- `energy-esg.emission_factor.efac_key`
- `energy-esg.emission_factor.category`
- `energy-esg.emission_factor.carrier`
- `energy-esg.emission_factor.region`
- `energy-esg.emission_factor.method`
- `energy-esg.emission_factor.kgco2e_per_unit`
- `energy-esg.emission_factor.valid_from`
- `energy-esg.emission_factor.valid_to`
- `energy-esg.emission_factor.factor_set`
