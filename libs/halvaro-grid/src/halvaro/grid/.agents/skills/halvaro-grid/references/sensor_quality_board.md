# sensor_quality_board

Module `halvaro.grid.quality`. Import: `from halvaro.grid import sensor_quality_board`.

```python
sensor_quality_board(daily: pd.DataFrame, *, context: halvaro.core.access.Context) -> pd.DataFrame
```

Use this when you need the availability of each sensor by ISO week as a board.

Sensors are the rows and ISO weeks the columns ('YYYY-Www'). Each cell is the mean of the daily availability_pct over the days of the week that exist, two decimals; it is null for a week without days.
Weeks follow the ISO calendar of the UTC date, so a week at the turn of the year carries the ISO year (2024-12-30 is in 2025-W01).

Args:
    daily: The telemetry.measurement_daily frame, columns sns_key, date and availability_pct, one row per sensor and date.
    context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

Returns:
    A frame indexed by sns_key with one column per ISO week from the week of the first date to the last date (weeks without days included), holding the weekly mean availability.

Raises:
    FrameError: a column of daily is missing, sns_key, date or availability_pct is null, or there is more than one row for the same sensor and date.
    StageRefusal: a source of the function is above the stage of the context.

Example:
    >>> import pandas as pd
    >>> from halvaro.core import Context
    >>> from halvaro.grid import sensor_quality_board
    >>> ctx = Context(stage="month12", role="analyst")
    >>> d = pd.DataFrame({"sns_key": "SNS-900001", "date": ["2024-12-30", "2024-12-31", "2025-01-08"], "availability_pct": [100.0, 50.0, 80.0]})
    >>> board = sensor_quality_board(d, context=ctx)
    >>> board.columns.tolist()
    ['2025-W01', '2025-W02']
    >>> board.loc["SNS-900001"].tolist()
    [75.0, 80.0]

## Source columns

- `telemetry.measurement_daily.sns_key`
- `telemetry.measurement_daily.date`
- `telemetry.measurement_daily.availability_pct`
