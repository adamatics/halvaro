# winter_peak_answer

Module `halvaro.grid.recipes`. Import: `from halvaro.grid import winter_peak_answer`.

```python
winter_peak_answer(ranking: pd.DataFrame, peak_profile: pd.DataFrame, temperatures: pd.DataFrame, density: pd.DataFrame, clusters: Sequence[FaultCluster], gaps: pd.DataFrame, *, context: halvaro.core.access.Context) -> WinterPeakAnswer
```

Use this when you need the pieces of the winter peak answer (zone ranking, peak week profile, temperatures, fault density, clusters and data gaps) checked and assembled in one result.

Assemble the winter peak answer from `rank_zones`, a peak week profile, the peak load frame with `outdoor_c` and `supply_temp_c`, `fault_density`, the clusters of `fault_clusters` or `age_group_clusters` (a list or a frame, may be empty) and `gap_report`.
Nothing new is computed: the pieces are checked for their columns and kept as they are. Gaps are listed, not dropped: an empty gap frame is returned as it is, never filled. The label 'synthetic data' is always part of the answer.

Args:
    ranking: The output of rank_zones; it needs the columns zone_key, rank, peak_percent and valid.
    peak_profile: The peak week profile with the columns zone_key, ts, load_percent or similar; at least one row.
    temperatures: The peak load frame with the columns outdoor_c and supply_temp_c.
    density: The output of fault_density; it needs the columns net_key and n_faults.
    clusters: The clusters of fault_clusters or age_group_clusters, a list, a tuple or a frame; may be empty.
    gaps: The output of gap_report; it needs the column sns_key.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    An WinterPeakAnswer with the fields ranking, peak_profile, temperatures, fault_density, clusters (a tuple), gaps and labels (the tuple holding 'synthetic data'); the frames are given back with a fresh index.

Raises:
    FrameError: a piece is not a frame or lacks a needed column; the peak week profile has no rows; the ranking has no ranked zone, because the answer would have no first place; clusters is not a list, a tuple or a frame.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import winter_peak_answer
    >>> ctx = Context(stage="month12", role="analyst")
    >>> rk = pd.DataFrame({"zone_key": ["ZONE-0001", "ZONE-0002"], "rank": [1, 2], "peak_percent": [90.0, 80.0], "valid": [True, True]})
    >>> pp = pd.DataFrame({"zone_key": ["ZONE-0001"], "ts": ["2020-01-06 00:00"], "load_percent": [88.0]})
    >>> tp = pd.DataFrame({"outdoor_c": [-3.0], "supply_temp_c": [70.0]})
    >>> dn = pd.DataFrame({"net_key": ["NET-900001"], "n_faults": [2]})
    >>> gp = pd.DataFrame({"sns_key": []})
    >>> a = winter_peak_answer(rk, pp, tp, dn, [], gp, context=ctx)
    >>> a.labels, a.clusters, len(a.gaps)
    (('synthetic data',), (), 0)

## Source columns

- `telemetry.sensor.sns_key`
- `gis.supply_zone.zone_key`
- `service.fault_event.net_key`
- `telemetry.data_quality_event.sns_key`
