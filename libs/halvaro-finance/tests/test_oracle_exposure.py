"""Oracle tests of exposure_open.exposure_bridge (imported through the package): hand worked bridge rows and the bridge properties on seeded random frames."""
import random

import numpy as np
import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import Context, FrameError

M12 = Context(stage="month12", role="r")
OUT_COLS = ["prj_key", "open_po_dkk", "open_reserved_dkk", "open_dkk", "finance_dkk", "difference", "received_or_timing_dkk", "reserved_dkk"]


def _open(rows):
    """rows: (prj_key, exposure_po_dkk, exposure_reserved_dkk); exposure_dkk is their sum."""
    return pd.DataFrame({"prj_key": [r[0] for r in rows], "exposure_po_dkk": [r[1] for r in rows], "exposure_reserved_dkk": [r[2] for r in rows], "exposure_dkk": [r[1] + r[2] for r in rows]})


def _fin(rows):
    return pd.DataFrame({"prj_key": [r[0] for r in rows], "price_exposure_dkk": [r[1] for r in rows]})


def test_oracle_exposure_bridge_hand_rows_for_projects_in_one_or_both_definitions():
    """route: hand worked projects, the bridge columns written out by hand per project, including a project in only one of the two results."""
    o = _open([("P3", 10.0, 0.0), ("P1", 100.25, 40.5), ("P2", 0.0, 25.0)])
    f = _fin([("P4", 70.0), ("P1", 150.0)])
    o0, f0 = o.copy(deep=True), f.copy(deep=True)
    b = fin.exposure_bridge(o, f, context=M12)
    assert list(b.columns) == OUT_COLS and b.prj_key.tolist() == ["P1", "P2", "P3", "P4"], "sorted by project, the union of both results"
    by = b.set_index("prj_key")
    assert by.loc["P1"].tolist() == [100.25, 40.5, 140.75, 150.0, 9.25, 49.75, 40.5], "finance 150.00 less open 140.75; less the open po part 100.25; reserved as given"
    assert by.loc["P2"].tolist() == [0.0, 25.0, 25.0, 0.0, -25.0, 0.0, 25.0], "no finance row: finance side 0"
    assert by.loc["P3"].tolist() == [10.0, 0.0, 10.0, 0.0, -10.0, -10.0, 0.0], "no finance row: finance side 0, the open po part is not on the finance side"
    assert by.loc["P4"].tolist() == [0.0, 0.0, 0.0, 70.0, 70.0, 70.0, 0.0], "no open row: open side 0"
    pd.testing.assert_frame_equal(o, o0)
    pd.testing.assert_frame_equal(f, f0)


def test_oracle_exposure_bridge_difference_is_rounded_to_the_cent_and_negative_values_pass_through():
    """route: hand frames whose float sums carry noise below the cent, and a finance exposure below the open one."""
    o = _open([("P1", 0.1, 0.2), ("P2", 5.0, 2.0)])
    f = _fin([("P1", 0.3), ("P2", -4.5)])
    b = fin.exposure_bridge(o, f, context=M12).set_index("prj_key")
    assert b.loc["P1", "difference"] == 0.0, "0.3 less (0.1 + 0.2) is noise, not a difference"
    assert b.loc["P1", "received_or_timing_dkk"] == 0.2 and b.loc["P2", "difference"] == -11.5 and b.loc["P2", "received_or_timing_dkk"] == -9.5 and b.loc["P2", "reserved_dkk"] == 2.0


def test_oracle_exposure_bridge_identity_and_sums_on_seeded_random_frames():
    """route: seeded random frames in whole cents, expected per project from plain dictionaries in integer cents, plus the identity, the column sums and the order independence."""
    rng = random.Random(20260)
    keys = [f"PRJ-{i:06d}" for i in range(1, 41)]
    open_keys, fin_keys = rng.sample(keys, 28), rng.sample(keys, 26)
    po = {k: rng.randint(0, 5_000_000) for k in open_keys}
    rs = {k: rng.randint(0, 2_000_000) for k in open_keys}
    fc = {k: rng.randint(-100_000, 6_000_000) for k in fin_keys}
    o = pd.DataFrame({"prj_key": open_keys, "exposure_po_dkk": [po[k] / 100 for k in open_keys], "exposure_reserved_dkk": [rs[k] / 100 for k in open_keys],
                      "exposure_dkk": [(po[k] + rs[k]) / 100 for k in open_keys]})
    f = pd.DataFrame({"prj_key": fin_keys, "price_exposure_dkk": [fc[k] / 100 for k in fin_keys]})
    b = fin.exposure_bridge(o, f, context=M12)
    union = sorted(set(open_keys) | set(fin_keys))
    assert b.prj_key.tolist() == union
    for r in b.itertuples():
        p, s, c = po.get(r.prj_key, 0), rs.get(r.prj_key, 0), fc.get(r.prj_key, 0)
        got = [round(x * 100) for x in (r.open_po_dkk, r.open_reserved_dkk, r.open_dkk, r.finance_dkk, r.difference, r.received_or_timing_dkk, r.reserved_dkk)]
        assert got == [p, s, p + s, c, c - p - s, c - p, s], r.prj_key
        assert round(r.difference * 100) == round(r.received_or_timing_dkk * 100) - round(r.reserved_dkk * 100), "the bridge steps add up to the gap"
    assert round(b.difference.sum() * 100) == sum(fc.values()) - sum(po.values()) - sum(rs.values()), "the gaps add up to the two totals"
    assert round(b.finance_dkk.sum() * 100) == sum(fc.values()) and round(b.open_dkk.sum() * 100) == sum(po.values()) + sum(rs.values())
    shuffled = fin.exposure_bridge(o.sample(frac=1, random_state=3).reset_index(drop=True), f.sample(frac=1, random_state=4).reset_index(drop=True), context=M12)
    pd.testing.assert_frame_equal(b, shuffled)


def test_oracle_exposure_bridge_empty_sides_and_refusals():
    """route: hand frames: one side empty gives the other side with zeros, a repeated project or a null amount is refused."""
    o = _open([("P1", 3.0, 4.0)])
    only_open = fin.exposure_bridge(o, _fin([]), context=M12)
    assert only_open.values.tolist() == [["P1", 3.0, 4.0, 7.0, 0.0, -7.0, -3.0, 4.0]]
    only_fin = fin.exposure_bridge(_open([]), _fin([("P2", 9.0)]), context=M12)
    assert only_fin.values.tolist() == [["P2", 0.0, 0.0, 0.0, 9.0, 9.0, 9.0, 0.0]]
    assert fin.exposure_bridge(_open([]), _fin([]), context=M12).empty
    with pytest.raises(FrameError, match="more than one row"):
        fin.exposure_bridge(pd.concat([o, o]), _fin([("P1", 1.0)]), context=M12)
    with pytest.raises(FrameError, match="more than one row"):
        fin.exposure_bridge(o, _fin([("P1", 1.0), ("P1", 2.0)]), context=M12)
    with pytest.raises(FrameError, match="null"):
        fin.exposure_bridge(o, _fin([("P1", np.nan)]), context=M12)
    with pytest.raises(FrameError, match="null"):
        fin.exposure_bridge(o.assign(exposure_reserved_dkk=np.nan), _fin([("P1", 1.0)]), context=M12)
    with pytest.raises(FrameError, match="lacks column"):
        fin.exposure_bridge(o.drop(columns="exposure_dkk"), _fin([("P1", 1.0)]), context=M12)
