# rank_zones

Module `halvaro.grid.capacity`. Import: `from halvaro.grid import rank_zones`.

```python
rank_zones(summary: pd.DataFrame, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the heat zones ranked on the peak load of their root, with the electric stations listed below without a rank.

Ranks the heat zones on the peak percent of their root (valid peaks only, highest first) and lists the electric stations below with rank null and their basis, because a station percent is not comparable with a zone percent (T9).
A zone with an invalid peak is listed with rank null.

Args:
    summary: The output of peak_load, with the columns zone_key, sns_key, level, basis, peak_percent and valid.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame with the columns rank, zone_key, sns_key, level, basis, peak_percent, valid: ranked zones first (rank 1.0, 2.0, ...), then the rest sorted by zone_key and sns_key with rank null.

Raises:
    FrameError: summary is not a DataFrame or lacks one of the columns zone_key, sns_key, level, basis, peak_percent or valid.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import rank_zones
    >>> ctx = Context(stage="month12", role="analyst")
    >>> summary = pd.DataFrame({"zone_key": ["ZONE-0001", "ZONE-0003", "ZONE-0004"], "sns_key": ["SNS-900001", "SNS-900002", "SNS-900003"],
    ...                         "level": ["zone", "zone", "station"], "basis": ["load_percent", "load_percent", "station"],
    ...                         "peak_percent": [61.0, 84.0, 70.0], "valid": [True, True, True]})
    >>> out = rank_zones(summary, context=ctx)
    >>> out["zone_key"].tolist()
    ['ZONE-0003', 'ZONE-0001', 'ZONE-0004']
    >>> out["rank"].tolist()
    [1.0, 2.0, nan]

## Source columns

- `telemetry.sensor.zone_key`
- `telemetry.sensor.critical_role`
