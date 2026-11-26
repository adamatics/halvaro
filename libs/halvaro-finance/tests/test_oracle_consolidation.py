"""Oracle tests of consolidation.translation_check: hand worked cent rounding, the rate tolerance boundary, and the baseline trial balance recomputed line by line with exact decimals."""
from decimal import ROUND_HALF_UP, Decimal

import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import Context, FrameError, fact

M12 = Context(stage="month12", role="r")
COLS = ["period", "n_lines", "sum_dkk", "sum_recomputed_dkk", "rounding_dkk", "max_line_rounding_dkk"]
FX = "world.fx_eur_dkk_fixed"


def _tb(rows):
    """rows: (le_key, period, gl_key, currency, closing_balance, closing_balance_dkk)."""
    return pd.DataFrame(rows, columns=["le_key", "period", "gl_key", "currency", "closing_balance", "closing_balance_dkk"])


def _cents(balance, rate) -> Decimal:
    """Balance times rate in exact decimals, rounded to the cent with ties away from zero."""
    return (Decimal(repr(float(balance))) * Decimal(repr(float(rate)))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def test_oracle_translation_check_hand_cent_ties_month_filter_and_currency_filter():
    """route: hand worked lines at a rate of 2.5 (ties at the half cent), the expected sums and gaps written out by hand."""
    tb = _tb([
        ("LE-02", "2025-12", "GL-1", "EUR", 0.25, 0.62),         # 0.625 rounds away from zero to 0.63, stored 0.62: gap -0.01
        ("LE-02", "2025-12", "GL-2", "EUR", -0.25, -0.62),       # -0.625 rounds to -0.63, stored -0.62: gap +0.01
        ("LE-02", "2025-12", "GL-3", "EUR", 1000.01, 2500.02),   # 2500.025 rounds to 2500.03, stored 2500.02: gap -0.01
        ("LE-02", "2025-12", "GL-4", "EUR", 40.0, 100.0),        # exact
        ("LE-01", "2025-12", "GL-5", "DKK", 5.0, 5.0),           # not a EUR line
        ("LE-02", "2025-06", "GL-1", "EUR", 4.0, 10.0),          # another month
        ("LE-02", "2024-12", "GL-1", "EUR", 8.0, 20.0),
    ])
    before = tb.copy(deep=True)
    r = fin.translation_check(tb, eur_rate=2.5, context=M12)
    v = r.value
    assert list(v.columns) == COLS and v.period.tolist() == ["2024-12", "2025-12"]
    assert v.n_lines.tolist() == [1, 4], "the DKK line and the other month are not counted"
    assert v.sum_dkk.tolist() == [20.0, 2600.02], "0.62 - 0.62 + 2500.02 + 100.00"
    assert v.sum_recomputed_dkk.tolist() == [20.0, 2600.03], "0.63 - 0.63 + 2500.03 + 100.00"
    assert v.rounding_dkk.tolist() == [0.0, -0.01] and v.max_line_rounding_dkk.tolist() == [0.0, 0.01]
    assert r.facts_used == (), "an explicit rate reads no fact"
    pd.testing.assert_frame_equal(tb, before)
    june = fin.translation_check(tb, month=6, eur_rate=2.5, context=M12).value
    assert june.period.tolist() == ["2025-06"] and june.n_lines.tolist() == [1] and june.sum_dkk.tolist() == [10.0] and june.rounding_dkk.tolist() == [0.0]
    assert fin.translation_check(tb, month=1, eur_rate=2.5, context=M12).value.empty


def test_oracle_translation_check_hand_rate_is_the_fact_when_none_is_given():
    """route: stored DKK built from exact decimals at the fixed rate read through the fact id plus known offsets of whole cents, the gaps are the offsets."""
    f = fact(FX)
    offsets = {"GL-1": Decimal("0.00"), "GL-2": Decimal("0.03"), "GL-3": Decimal("-0.02"), "GL-4": Decimal("0.00")}
    bal = {"GL-1": 0.25, "GL-2": 12345.67, "GL-3": -980.4, "GL-4": 3.0}
    rec = {k: _cents(b, f.value) for k, b in bal.items()}
    tb = _tb([("LE-02", "2025-12", k, "EUR", bal[k], float(rec[k] + offsets[k])) for k in bal])
    r = fin.translation_check(tb, context=M12)
    v = r.value.iloc[0]
    msg = f"{FX} read as {f.value} ({f.status})"
    assert r.facts_used == ((FX, f.value, f.status),) and r.status == "ok", msg
    assert v.n_lines == 4, msg
    assert abs(v.sum_recomputed_dkk - float(sum(rec.values()))) < 0.005, msg
    assert abs(v.sum_dkk - float(sum(rec[k] + offsets[k] for k in bal))) < 0.005, msg
    assert abs(v.rounding_dkk - float(sum(offsets.values()))) < 0.005 and abs(v.max_line_rounding_dkk - 0.03) < 0.005, msg


def test_oracle_translation_check_rate_tolerance_and_small_line_boundary():
    """route: hand frames at rate 2.5 whose implied rate sits on either side of the tolerance, and a line of exactly one euro that the implied rate leaves out."""
    inside = _tb([("LE-02", "2025-12", "GL-1", "EUR", 1000.0, 2500.5)])        # implied 2.5005, gap 0.0005
    assert fin.translation_check(inside, eur_rate=2.5, context=M12).value.n_lines.tolist() == [1]
    outside = _tb([("LE-02", "2025-12", "GL-1", "EUR", 1000.0, 2502.5)])       # implied 2.5025, gap 0.0025
    with pytest.raises(FrameError, match="2025-12"):
        fin.translation_check(outside, eur_rate=2.5, context=M12)
    assert fin.translation_check(outside, eur_rate=2.5, rate_tolerance=0.01, context=M12).value.rounding_dkk.tolist() == [2.5]
    with pytest.raises(FrameError, match="2025-12"):
        fin.translation_check(outside, eur_rate=2.5, rate_tolerance=0.001, context=M12)
    one = _tb([("LE-02", "2025-12", "GL-1", "EUR", 1.0, 9.99)])                 # a balance of 1 is not above 1: left out of the implied rate
    assert fin.translation_check(one, eur_rate=2.5, context=M12).value.max_line_rounding_dkk.tolist() == [7.49]
    with pytest.raises(FrameError, match="2025-12"):
        fin.translation_check(_tb([("LE-02", "2025-12", "GL-1", "EUR", 1.01, 9.99)]), eur_rate=2.5, context=M12)
    with pytest.raises(FrameError, match="not the fixed rate"):
        fin.translation_check(_tb([("LE-02", "2025-12", "GL-1", "EUR", 1000.0, 7460.0)]), eur_rate=2.5, context=M12)


def _is_tie(balance, rate) -> bool:
    """True when balance times rate is exactly half a cent (exact decimals)."""
    return abs((Decimal(repr(float(balance))) * Decimal(repr(float(rate))) * 100) % 1) == Decimal("0.5")


def test_oracle_translation_check_hand_half_cent_tie_on_a_large_balance_rounds_away_from_zero():
    """route: one large line and its mirror whose exact product is half a cent, the expected recomputation written with exact decimals at the fact rate."""
    f = fact(FX)
    rate = float(f.value)
    pos, neg = 143684.25, -88582.75
    assert _is_tie(pos, rate) and _is_tie(neg, rate), f"the two balances are half cent ties at {FX} = {f.value}"
    want_pos, want_neg = _cents(pos, rate), _cents(neg, rate)
    assert want_pos > Decimal(repr(pos)) * Decimal(repr(rate)) and want_neg < Decimal(repr(neg)) * Decimal(repr(rate)), "ties go away from zero"
    tb = _tb([("LE-02", "2025-12", "GL-1", "EUR", pos, float(want_pos)), ("LE-02", "2025-12", "GL-2", "EUR", neg, float(want_neg))])
    v = fin.translation_check(tb, context=M12).value.iloc[0]
    msg = f"{FX} read as {f.value} ({f.status}); recomputed {want_pos} and {want_neg}"
    assert abs(v.sum_recomputed_dkk - float(want_pos + want_neg)) < 0.0001, msg
    assert v.rounding_dkk == 0.0 and v.max_line_rounding_dkk == 0.0, msg
