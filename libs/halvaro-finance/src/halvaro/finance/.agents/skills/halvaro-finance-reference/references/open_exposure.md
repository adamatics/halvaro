# open_exposure

```python
open_exposure(exposed_demand: pd.DataFrame, steps: pd.DataFrame, *, only_amended: bool = True, context: <class 'halvaro.core.access.Context'>) -> pd.DataFrame
```

Use this when you need the added cost of a price step on the demand that is still open, per project, in DKK.

Rule: the open quantity times the step of the item, converted to DKK at the booking rates and rounded to the cent. A purchase order line placed before the effective date was bought at the old price and carries no exposure. A free reservation is priced now. With only_amended the step of an ordinary price list change is not exposure, only the step of an amendment. The project set is the one of exposed_demand and is never rebuilt here.

## Args

exposed_demand: Frame with prj_key, sup_key, itm_key, qty_open (the name remaining is also accepted), source (po_line or reservation) and after_effective_date; a po_key column must be empty on reservation rows.
steps: The result of price_steps (or a frame with sup_key, itm_key, currency, step and step_percent, and optionally amended), one row per supplier and item.
only_amended: True counts only the steps of an amendment. Default True.
context: A halvaro.core.Context (stage and role of the session), required.

## Returns

pandas.DataFrame with prj_key, n_po_lines, exposure_po_dkk, reserved_open_qty, exposure_reserved_dkk, exposure_dkk and step_percent_max (the largest step among the priced items of the project that have an open quantity, not weighted by exposure).

## Raises

FrameError: a column is missing, steps repeats a supplier and item, a demand row has a null project or quantity (or no after_effective_date on a PO line), a source is neither po_line nor reservation, a quantity is negative, a reservation has a po_key, a priced demand row has no step row or a null step, or qty_open and remaining disagree.
StageRefusal: a source of the function is above the stage of the context.

## Example

```python
>>> import pandas as pd
>>> from halvaro.core import Context
>>> from halvaro.finance import open_exposure
>>> ctx = Context(stage="month12", role="analyst")
>>> demand = pd.DataFrame({"prj_key": ["PRJ-1"], "sup_key": ["SUP-1"], "itm_key": ["ITM-1"], "qty_open": [5.0], "source": ["po_line"], "after_effective_date": [True]})
>>> steps = pd.DataFrame({"sup_key": ["SUP-1"], "itm_key": ["ITM-1"], "currency": ["DKK"], "step": [2.0], "step_percent": [10.0]})
>>> open_exposure(demand, steps, context=ctx)[["prj_key", "n_po_lines", "exposure_dkk"]].values.tolist()
[['PRJ-1', 1, 10.0]]
```

## Facts and sources

Facts (read with `halvaro.core.fact(id)`; values and status are not repeated here): none.

Source columns: `procurement.price_list.unit_price`, `procurement.price_list.change_reason`, `procurement.price_list.valid_from`, `procurement.price_list.currency`, `procurement.po_line.qty`, `procurement.po_line.received_qty`, `inventory.reservation.qty_open`.
