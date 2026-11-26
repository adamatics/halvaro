# exposure_bridge

```python
exposure_bridge(open_exposure_result: pd.DataFrame, finance_exposure_result: pd.DataFrame, *, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need to explain the gap between the open quantity and the finance definitions of the price exposure, per project.

Rule: difference is the finance exposure less the open exposure. received_or_timing_dkk is the finance exposure less the open purchase order part (what finance counts on lines already received or booked in another month) and reserved_dkk is what only the open definition counts. By construction difference equals received_or_timing_dkk less reserved_dkk, to the cent. A project in one result only is listed with 0 on the other side.

## Args

open_exposure_result: The result of open_exposure, with prj_key, exposure_po_dkk, exposure_reserved_dkk and exposure_dkk, one row per project.
finance_exposure_result: The result of finance_exposure, with prj_key and price_exposure_dkk, one row per project.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with prj_key, open_po_dkk, open_reserved_dkk, open_dkk, finance_dkk, difference, received_or_timing_dkk and reserved_dkk, sorted by project.

## Raises

FrameError: a column is missing, a result has more than one row for a project, or an amount is null.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import exposure_bridge
>>> ctx = Context(stage="month12", role="analyst")
>>> opened = pd.DataFrame({"prj_key": ["PRJ-1"], "exposure_po_dkk": [10.0], "exposure_reserved_dkk": [4.0], "exposure_dkk": [14.0]})
>>> finance = pd.DataFrame({"prj_key": ["PRJ-1"], "price_exposure_dkk": [30.0]})
>>> exposure_bridge(opened, finance, context=ctx)[["difference", "received_or_timing_dkk", "reserved_dkk"]].values.tolist()
[[16.0, 20.0, 4.0]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `finance.project_financials.price_exposure`, `procurement.po_line.received_qty`, `inventory.reservation.qty_open`.
