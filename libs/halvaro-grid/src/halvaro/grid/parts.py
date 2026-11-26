"""Parts used on tickets (plan 5.8): units by item, element type and month, and the issues of the critical items.

The critical items are marked by the flag `inventory.item.critical`, never by an id list. Stock, orders, lead times and minimum stock are read by no function here (they belong to the supply answer of halvaro-delivery).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from halvaro.core import FrameError

from ._guard import staged
from ._util import _need
from ._types import Window
from ._tail import value_text


def _use(ticket_item_use: pd.DataFrame) -> pd.DataFrame:
    _need(ticket_item_use, ["tkt_key", "itm_key", "qty", "used_on", "uom"], "service.ticket_item_use")
    if ticket_item_use[["tkt_key", "itm_key"]].isna().any().any():
        raise FrameError("service.ticket_item_use has rows without a ticket or an item")
    if ticket_item_use.duplicated(["tkt_key", "itm_key", "used_on"]).any():
        raise FrameError("service.ticket_item_use has more than one row for a ticket, item and day")
    q = pd.to_numeric(ticket_item_use["qty"], errors="coerce")
    if q.isna().any() or (q < 0).any() or not np.isfinite(q).all():
        raise FrameError("service.ticket_item_use.qty must be a number of zero or more on every row")
    day = pd.to_datetime(ticket_item_use["used_on"], errors="coerce")
    if day.isna().any():
        raise FrameError("service.ticket_item_use.used_on must be a date on every row")
    return ticket_item_use.assign(qty=q.to_numpy(), day=day.dt.normalize().to_numpy())


@staged(sources=("service.ticket_item_use.itm_key", "service.ticket_item_use.qty", "service.ticket_item_use.uom", "service.ticket_item_use.used_on", "service.ticket_item_use.tkt_key",
                 "service.service_ticket.tkt_key", "service.service_ticket.net_key", "gis.grid_element.net_key", "gis.grid_element.element_type"),
        oracle="py:tests/test_service.py::test_parts_and_interface")
def part_usage(ticket_item_use: pd.DataFrame, service_ticket: pd.DataFrame, grid_element: pd.DataFrame | None = None, *, no_element: str = "none") -> pd.DataFrame:
    """Use this when you need the units of parts used on tickets by item, unit of measure, element type and month.

    The month is the month of `used_on`. The element type comes from the ticket's element (`service.service_ticket.net_key`) and `gis.grid_element`; a ticket without an element (off-grid work) gets `no_element` ('none').
    Without `grid_element` every row gets 'unknown'. Quantities of different units are never added: the unit of measure is a key column.

    Args:
        ticket_item_use: The service.ticket_item_use frame, columns tkt_key, itm_key, qty, used_on and uom.
        service_ticket: The service.service_ticket frame, columns tkt_key and net_key.
        grid_element: Optional gis.grid_element frame, columns net_key and element_type; without it the element type is 'unknown'.
        no_element: The element type given to a ticket without an element (default 'none').
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns itm_key, uom, element_type, period (YYYY-MM), units, n_lines and n_tickets, sorted by itm_key, uom, element_type and period.

    Raises:
        FrameError: a column of ticket_item_use, service_ticket or grid_element is missing; ticket_item_use has rows without a ticket or an item, more than one row for a ticket, item and day, a qty that is not a number of zero or more, or a used_on that is not a date;
            service_ticket or grid_element repeats a key; a use row's ticket is not in service_ticket; a ticket names an element that grid_element does not hold.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import part_usage
        >>> ctx = Context(stage="month12", role="analyst")
        >>> u = pd.DataFrame({"tkt_key": ["TKT-900001", "TKT-900002"], "itm_key": "ITM-900001", "qty": [2.0, 3.0], "used_on": ["2025-03-03", "2025-03-20"], "uom": "pcs"})
        >>> t = pd.DataFrame({"tkt_key": ["TKT-900001", "TKT-900002"], "net_key": ["NET-900001", None]})
        >>> g = pd.DataFrame({"net_key": ["NET-900001"], "element_type": ["valve"]})
        >>> out = part_usage(u, t, g, context=ctx)
        >>> out[["element_type", "period", "units", "n_tickets"]].to_dict("records")
        [{'element_type': 'none', 'period': '2025-03', 'units': 3.0, 'n_tickets': 1}, {'element_type': 'valve', 'period': '2025-03', 'units': 2.0, 'n_tickets': 1}]
    """
    u = _use(ticket_item_use)
    _need(service_ticket, ["tkt_key", "net_key"], "service.service_ticket")
    if service_ticket["tkt_key"].duplicated().any():
        raise FrameError("service.service_ticket has more than one row for a ticket")
    if not set(u["tkt_key"]).issubset(set(service_ticket["tkt_key"])):
        raise FrameError("service.ticket_item_use has rows for tickets that service.service_ticket does not hold")
    net = service_ticket.set_index("tkt_key")["net_key"]
    x = u.assign(net_key=u["tkt_key"].map(net))
    if grid_element is None:
        x["element_type"] = "unknown"
        x.loc[x["net_key"].isna(), "element_type"] = no_element
    else:
        _need(grid_element, ["net_key", "element_type"], "gis.grid_element")
        if grid_element["net_key"].duplicated().any():
            raise FrameError("gis.grid_element has more than one row for an element")
        et = grid_element.assign(net_key=grid_element["net_key"].astype(object), element_type=grid_element["element_type"].astype(object)).set_index("net_key")["element_type"]
        unknown = set(x["net_key"].dropna()) - set(et.index)
        if unknown:
            raise FrameError(f"service.service_ticket names elements that gis.grid_element does not hold, for example {sorted(unknown)[:3]}")
        x["element_type"] = x["net_key"].astype(object).map(et).astype(object).where(x["net_key"].notna(), no_element)
    x["period"] = x["day"].dt.strftime("%Y-%m")
    g = x.groupby(["itm_key", "uom", "element_type", "period"], as_index=False, dropna=False, observed=True).agg(units=("qty", "sum"), n_lines=("tkt_key", "size"), n_tickets=("tkt_key", "nunique"))
    return g.sort_values(["itm_key", "uom", "element_type", "period"]).reset_index(drop=True)


@staged(sources=("service.ticket_item_use.itm_key", "service.ticket_item_use.qty", "service.ticket_item_use.uom", "service.ticket_item_use.used_on", "service.ticket_item_use.tkt_key",
                 "inventory.item.itm_key", "inventory.item.critical"), facts=(), oracle="py:tests/test_service.py::test_parts_and_interface")
def critical_spares_issued(ticket_item_use: pd.DataFrame, item: pd.DataFrame, *, window: Window | None = None) -> pd.DataFrame:
    """Use this when you need the issues of the critical spare items on tickets, with the units used and the first and last day of use.

    The critical items are those with the flag `inventory.item.critical` (an item without the flag is never listed, and no id list is used). The optional `window` is two days, both included.
    A critical item with no issue in the window is listed with zero units. The minimum stock rule (policy.delivery.minimum_stock_rule) is not applied here: it belongs to halvaro-delivery.

    Args:
        ticket_item_use: The service.ticket_item_use frame, columns tkt_key, itm_key, qty, used_on and uom.
        item: The inventory.item frame, columns itm_key and critical (true or false).
        window: Optional two days (first day, last day, both included) that limit the issues by used_on.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns itm_key, uom, units, n_lines, n_tickets, first_used and last_used, sorted by itm_key and uom (a critical item without issue has a null uom, zero units and null days, last).

    Raises:
        FrameError: a column of ticket_item_use or item is missing; ticket_item_use has rows without a ticket or an item, more than one row for a ticket, item and day, a qty that is not a number of zero or more, or a used_on that is not a date;
            item repeats an itm_key, or critical has nulls or holds text or numbers; an item used on a ticket is missing from inventory.item; window is not two dates or ends before it starts.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.grid import critical_spares_issued
        >>> ctx = Context(stage="month12", role="analyst")
        >>> u = pd.DataFrame({"tkt_key": ["TKT-900001", "TKT-900002"], "itm_key": ["ITM-900001", "ITM-900002"], "qty": [2.0, 1.0], "used_on": ["2025-03-03", "2025-03-04"], "uom": "pcs"})
        >>> i = pd.DataFrame({"itm_key": ["ITM-900001", "ITM-900002", "ITM-900003"], "critical": [True, False, True]})
        >>> out = critical_spares_issued(u, i, context=ctx)
        >>> out[["itm_key", "units", "n_tickets"]].to_dict("records")
        [{'itm_key': 'ITM-900001', 'units': 2.0, 'n_tickets': 1}, {'itm_key': 'ITM-900003', 'units': 0.0, 'n_tickets': 0}]
    """
    u = _use(ticket_item_use)
    _need(item, ["itm_key", "critical"], "inventory.item")
    if item["itm_key"].duplicated().any():
        raise FrameError("inventory.item has more than one row for an item")
    if item["critical"].isna().any():
        raise FrameError("inventory.item.critical has nulls")
    if not all(isinstance(v, (bool, np.bool_)) for v in item["critical"]):
        raise FrameError("inventory.item.critical must hold true or false, not text or numbers")
    if not set(u["itm_key"]).issubset(set(item["itm_key"])):
        raise FrameError("service.ticket_item_use names items that inventory.item does not hold")
    if window is not None:
        try:
            lo, hi = pd.Timestamp(window[0]).normalize(), pd.Timestamp(window[1]).normalize()
        except (TypeError, ValueError, IndexError):
            raise FrameError(f"window must be two dates (first day, last day, both included) (got {value_text(window)})") from None
        if hi < lo:
            raise FrameError(f"window ends before it starts (got {value_text(window)})")
        u = u[u["day"].between(lo, hi)]
    crit = item[item["critical"].astype(bool)]["itm_key"]
    x = u[u["itm_key"].isin(set(crit))]
    g = x.groupby(["itm_key", "uom"], as_index=False, observed=True).agg(units=("qty", "sum"), n_lines=("tkt_key", "size"), n_tickets=("tkt_key", "nunique"), first_used=("day", "min"), last_used=("day", "max"))
    idle = sorted(set(crit) - set(g["itm_key"]))
    if idle:
        g = pd.concat([g, pd.DataFrame({"itm_key": idle, "uom": None, "units": 0.0, "n_lines": 0, "n_tickets": 0, "first_used": pd.NaT, "last_used": pd.NaT})], ignore_index=True)
    return g.sort_values(["itm_key", "uom"], na_position="last").reset_index(drop=True)
