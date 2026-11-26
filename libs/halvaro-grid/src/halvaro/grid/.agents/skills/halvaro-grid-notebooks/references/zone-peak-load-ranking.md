# From load samples to a ranking of zones

Notebook `notebooks/zone-peak-load-ranking.ipynb` of halvaro-grid, as text without outputs. Generated from the notebook; run the notebook to see the results.

**Question.** How do hourly load samples of a heat zone become a peak per zone, and which zones rank highest once a zone with too many suspect samples is left out?

## Functions used

| Function | Use this when | Reference |
|---|---|---|
| `zone_load_percent` | you need the load in percent of the design per heat zone (its root pump) and per electric station, with the quality flag of every sample. | [zone_load_percent](../../halvaro-grid/references/zone_load_percent.md) |
| `peak_load` | you need the peak load of each heat zone (its root) and each electric station, with its time, validity and the outdoor and supply temperature at the peak. | [peak_load](../../halvaro-grid/references/peak_load.md) |
| `rank_zones` | you need the heat zones ranked on the peak load of their root, with the electric stations listed below without a rank. | [rank_zones](../../halvaro-grid/references/rank_zones.md) |

## Steps

A heat zone reports its load as a percent of the design, one sample per hour, each with a quality flag. `zone_load_percent` puts the samples of a zone on one basis, `peak_load` rolls them up to the peak of each zone and says whether the zone has enough good samples, and `rank_zones` ranks the zones that count. The notebook builds its own small frames, so it needs no data.

```python
import pandas as pd

from halvaro.core import Context
from halvaro.grid import peak_load, rank_zones, zone_load_percent

ctx = Context(stage="month12", role="analyst")
sensor = pd.DataFrame({"sns_key": ["SNS-900001", "SNS-900002"], "zone_key": ["ZONE-0001", "ZONE-0003"], "sensor_type": ["load_percent"] * 2,
                       "interval_s": [3600] * 2, "critical_role": ["root_pump"] * 2, "rated_value": [100.0] * 2, "station_key": ["WST-900001"] * 2})
hours = ["2026-01-10 00:00", "2026-01-10 01:00", "2026-01-10 02:00"]
samples = pd.DataFrame({"sns_key": ["SNS-900001"] * 3 + ["SNS-900002"] * 3, "ts": hours * 2, "value": [60.0, 61.0, 55.0, 70.0, 84.0, 90.0],
                        "quality_flag": ["ok", "ok", "ok", "ok", "ok", "suspect"]})
samples
```

Step 1. The samples of both zones on one basis. A sample flagged suspect gets no load value.

```python
load = zone_load_percent(samples, sensor, context=ctx)
load[["zone_key", "ts", "quality_flag", "ok", "load_percent"]]
```

Step 2. The peak of each zone, with the share of samples that were good. A zone below the completeness limit is not valid.

```python
weather = pd.DataFrame({"station_key": ["WST-900001"] * 3, "ts": hours, "temp_c": [-3.0, -5.0, -4.0]})
peaks = peak_load(load, sensor, weather, context=ctx)
peaks[["zone_key", "peak_percent", "completeness", "valid", "outdoor_c"]]
```

Step 3. The ranking. The zone with the higher peak is not ranked, because a third of its samples were suspect.

```python
ranking = rank_zones(peaks, context=ctx)
ranking[["rank", "zone_key", "peak_percent", "valid"]]
```

Check. The peak of each zone equals the largest good sample, computed here with pandas. The ranking holds only valid zones, in the order of their peaks.

```python
good = samples[samples["quality_flag"] == "ok"].merge(sensor[["sns_key", "zone_key"]], on="sns_key")
by_hand = good.groupby("zone_key")["value"].max()
assert peaks.set_index("zone_key")["peak_percent"].to_dict() == by_hand.to_dict()
ranked = ranking.dropna(subset=["rank"])
assert ranked["valid"].all() and ranked["peak_percent"].is_monotonic_decreasing
assert set(ranking.loc[ranking["rank"].isna(), "zone_key"]) == set(peaks.loc[~peaks["valid"], "zone_key"])
```
