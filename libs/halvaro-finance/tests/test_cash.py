"""Cash (plan 5.9): hand computed forecast weeks, then the baseline release (1,222 weeks of 94 forecasts)."""
import numpy as np
import pandas as pd
import pytest

import halvaro.finance as fin
from halvaro.core import Context, FrameError, StageRefusal, registry

M3 = Context(stage="month3", role="r")
COMP = ["receipts_customers", "receipts_retention", "receipts_new_billing", "receipts_intercompany", "payments_suppliers_open", "payments_suppliers_new", "payments_net_wages",
        "payments_payroll_taxes_pensions", "payments_vat", "payments_intercompany", "net_interest"]


def _cf(floor=100.0):
    rows = []
    for w, (o, net) in enumerate([(1000.0, -300.0), (700.0, -650.0), (50.0, 20.0)], start=1):
        c = dict.fromkeys(COMP, 0.0)
        c["receipts_customers"], c["payments_vat"] = max(net, 0.0) + 0.0, min(net, 0.0)
        rows.append({"le_key": "LE-01", "forecast_date": "2025-01-31", "week_no": w, "opening_cash": o, "net_cash_flow": net, "closing_cash": o + net, "closing_cash_p10": o + net - 30.0, "closing_cash_p90": o + net + 30.0,
                     "minimum_cash_floor": floor, "rcf_limit": 500.0, "rcf_drawn": 100.0 * w, "rcf_available": 500.0 - 100.0 * w, "headroom_to_floor": o + net - floor, "headroom_to_floor_p10": o + net - 30.0 - floor,
                     "floor_breach_risk": o + net - 30.0 < floor, "actual_closing_cash_ex_rcf": o + net + (10.0 if w == 1 else 40.0 if w == 2 else np.nan), **c})
    return pd.DataFrame(rows)


def _bank():
    return pd.DataFrame({"le_key": ["LE-01", "LE-01"], "balance_date": ["2025-01-31", "2025-01-31"], "closing_balance": [600.0, 400.0]})


def test_cash_forecast_checks_each_rule_fires_and_a_clean_forecast_passes():
    assert fin.cash_forecast_checks(_cf(), _bank(), context=M3).empty
    cf = _cf()
    r = fin.cash_forecast_checks(cf.assign(opening_cash=cf.opening_cash.where(cf.week_no != 1, 1000.02)), _bank(), context=M3)
    assert "opening_differs_from_bank" in set(r.rule) and "closing_not_opening_plus_net" in set(r.rule)
    assert fin.cash_forecast_checks(cf, _bank().assign(closing_balance=[600.0, 400.003]), context=M3).empty and not fin.cash_forecast_checks(cf, _bank().assign(closing_balance=[600.0, 400.006]), context=M3).empty
    assert set(fin.cash_forecast_checks(cf, _bank().iloc[:0], context=M3).rule) == {"opening_differs_from_bank"}
    chain = cf.assign(opening_cash=cf.opening_cash.where(cf.week_no != 2, 701.0), closing_cash=cf.closing_cash.where(cf.week_no != 2, 51.0))
    assert "weekly_chain_broken" in set(fin.cash_forecast_checks(chain, _bank(), context=M3).rule)
    comp = cf.assign(payments_vat=cf.payments_vat.where(cf.week_no != 1, -310.0))
    assert fin.cash_forecast_checks(comp, _bank(), context=M3).rule.tolist() == ["components_do_not_sum"]
    band = cf.assign(closing_cash_p10=cf.closing_cash_p10.where(cf.week_no != 3, 80.0))
    assert fin.cash_forecast_checks(band, _bank(), context=M3).rule.tolist() == ["outside_band"]
    assert len(fin.cash_forecast_checks(cf.assign(opening_cash=cf.opening_cash + 1, closing_cash=cf.closing_cash + 1), _bank(), context=M3)) >= 1, "all violations are listed, not only the first"
    with pytest.raises(FrameError, match="more than one row"):
        fin.cash_forecast_checks(pd.concat([cf, cf.iloc[:1]]), _bank(), context=M3)
    with pytest.raises(FrameError, match="tolerance"):
        fin.cash_forecast_checks(cf, _bank(), chain_tolerance=-1, context=M3)


def test_liquidity_headroom_first_breach_lowest_week_and_stored_columns():
    h = fin.liquidity_headroom(_cf(), context=M3).iloc[0]
    assert (h.weeks, h.first_breach_week, h.lowest_headroom_week, h.breach_weeks) == (3, 2, 2, 2) and h.lowest_headroom_p10 == 700 - 650 - 30 - 100 and h.rcf_available_at_lowest == 300.0 and bool(h.agrees)
    assert pd.isna(fin.liquidity_headroom(_cf(floor=-1000.0), context=M3).iloc[0].first_breach_week)
    bad = _cf().assign(headroom_to_floor=lambda d: d.headroom_to_floor.where(d.week_no != 1, 5.0))
    assert not bool(fin.liquidity_headroom(bad, context=M3).iloc[0].agrees)
    with pytest.raises(FrameError, match="more than one floor"):
        fin.liquidity_headroom(_cf().assign(minimum_cash_floor=lambda d: d.minimum_cash_floor + d.week_no), context=M3)


def test_forecast_accuracy_coverage_and_error_by_horizon():
    a = fin.forecast_accuracy(_cf(), context=M3).set_index("week_no")
    assert a.loc[0, "n"] == 2 and a.loc[0, "coverage"] == 0.5 and a.loc[1, "coverage"] == 1.0 and a.loc[2, "coverage"] == 0.0, "10 is inside +-30, 40 is outside"
    assert a.loc[1, "mean_abs_error"] == 10.0 and a.loc[2, "mean_error"] == 40.0 and 3 not in a.index, "week 3 has no actual"
    assert fin.forecast_accuracy(_cf().assign(actual_closing_cash_ex_rcf=np.nan), context=M3).empty


def test_stage_registry_and_facade_for_cash():
    reg = registry.registered()
    for n in ("cash_forecast_checks", "liquidity_headroom", "forecast_accuracy"):
        assert f"halvaro.finance.cash.{n}" in reg and n in fin.__all__
    with pytest.raises(StageRefusal):
        fin.liquidity_headroom(pd.DataFrame(), context=Context(stage="day1", role="r"))
