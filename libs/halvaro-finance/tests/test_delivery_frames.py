"""Finance reads the delivery frames as they are (HF-02, HF-09; library-plans/README.md dependency table): `remaining` for the open quantity,
a null after_effective_date on a free reservation, and stock orders without project in open_po_lines."""
import numpy as np
import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import Context, FrameError

M12 = Context(stage="month12", role="r")


def _price(rows):
    return pd.DataFrame(rows, columns=["sup_key", "itm_key", "unit_price", "currency", "change_reason"])


def _steps():
    return fin.price_steps(_price([("S1", "I1", 100.0, "EUR", "list"), ("S1", "I2", 10.0, "DKK", "list")]), _price([("S1", "I1", 118.0, "EUR", "framework_amendment"), ("S1", "I2", 11.0, "DKK", "framework_amendment")]), context=M12)


def _delivery_demand():
    """The shape of delivery.ExposedDemand.combined: `remaining`, and a null flag on the reservation row."""
    c = ["prj_key", "sup_key", "itm_key", "remaining", "source", "after_effective_date"]
    return pd.DataFrame([("P1", "S1", "I1", 10.0, "po_line", True), ("P1", "S1", "I2", 100.0, "reservation", np.nan), ("P2", "S1", "I2", 40.0, "po_line", True)], columns=c)


def test_open_exposure_takes_the_delivery_frame_as_it_is_and_equals_the_adapted_one():
    d = _delivery_demand()
    adapted = d.rename(columns={"remaining": "qty_open"}).assign(after_effective_date=lambda x: x.after_effective_date.fillna(False).astype(bool))
    pd.testing.assert_frame_equal(fin.open_exposure(d, _steps(), context=M12), fin.open_exposure(adapted, _steps(), context=M12))
    assert fin.open_exposure(d, _steps(), context=M12).set_index("prj_key").loc["P1", "exposure_reserved_dkk"] == 100.0


def test_open_exposure_still_needs_the_flag_on_a_po_line_and_one_open_quantity():
    d = _delivery_demand()
    with pytest.raises(FrameError, match="after_effective_date"):
        fin.open_exposure(d.assign(after_effective_date=np.nan), _steps(), context=M12)
    with pytest.raises(FrameError, match="different numbers"):
        fin.open_exposure(d.assign(qty_open=d["remaining"] + 1), _steps(), context=M12)
    # the same numbers under both names are accepted, also with a null and with an int/float mix
    same = d.assign(qty_open=d["remaining"].astype(float) + 1e-12)
    fin.open_exposure(same, _steps(), context=M12)
    with pytest.raises(FrameError, match="qty_open"):
        fin.open_exposure(d.drop(columns="remaining"), _steps(), context=M12)


def _orders():
    pl = pd.DataFrame({"po_key": ["PO-1", "PO-2", "PO-3"], "line_no": [1, 1, 1], "unit_price": [100.0, 50.0, 20.0], "currency": ["DKK", "DKK", "DKK"], "cst_key": ["C-1", "C-2", "C-3"]})
    po = pd.DataFrame({"po_key": ["PO-1", "PO-2", "PO-3"], "delivery_type": ["project_site", "project_site", "warehouse"]})
    return pl, po


def test_committed_cost_takes_open_po_lines_as_they_are_and_drops_stock_orders_without_project():
    pl, po = _orders()
    open_ = pd.DataFrame({"po_key": ["PO-1", "PO-2", "PO-3"], "line_no": [1, 1, 1], "prj_key": ["P1", "P2", None], "remaining": [10.0, 2.0, 7.0]})
    c = fin.committed_cost(open_, pl, po, context=M12)
    assert c.groupby("prj_key").committed_dkk.sum().to_dict() == {"P1": 1000.0, "P2": 100.0}, "the stock order PO-3 has no project and is another delivery type"


def test_committed_cost_still_needs_a_project_on_a_project_site_line():
    pl, po = _orders()
    open_ = pd.DataFrame({"po_key": ["PO-1"], "line_no": [1], "prj_key": [None], "remaining": [10.0]})
    with pytest.raises(FrameError, match="prj_key"):
        fin.committed_cost(open_, pl, po, context=M12)
    spot = pd.DataFrame({"po_key": ["PO-2"], "line_no": [1], "prj_key": ["P2"], "remaining": [3.0]})
    c = fin.committed_cost(open_.assign(prj_key="P1"), pl, po, spot_orders=spot, context=M12)
    assert round(c.committed_dkk.sum(), 2) == 1150.0 and c.spot.any(), "spot_orders may use `remaining` too"
