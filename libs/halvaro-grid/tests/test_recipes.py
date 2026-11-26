"""Recipes (plan 5.8): the answers assemble given pieces and refuse what does not belong in them."""
import pandas as pd
import pytest

import halvaro.grid as grid
from halvaro.core import Context, FrameError, StageRefusal, registry

M12 = Context(stage="month12", role="r")

RANK = pd.DataFrame({"rank": [1.0, 2.0, None], "zone_key": ["Z2", "Z1", "Z4"], "peak_percent": [118.0, 101.0, 95.0], "valid": [True, True, True]})
TEMP = pd.DataFrame({"zone_key": ["Z2"], "outdoor_c": [-12.0], "supply_temp_c": [88.0]})
DENS = pd.DataFrame({"net_key": ["a", "b"], "n_faults": [3, 0]})
PROFILE = pd.DataFrame({"zone_key": ["Z2"], "ts": ["2026-01-19 07:00"], "load_percent": [118.0]})
GAPS = pd.DataFrame({"sns_key": ["S1"], "samples": [24]})


def test_winter_peak_answer_keeps_gaps_and_labels_and_refuses_an_empty_ranking():
    a = grid.winter_peak_answer(RANK, PROFILE, TEMP, DENS, [], GAPS, context=M12)
    assert a.labels == ("synthetic data",) and len(a.gaps) == 1 and a.clusters == () and a.ranking.zone_key.tolist() == ["Z2", "Z1", "Z4"]
    assert a.temperatures.equals(TEMP) and a.fault_density.equals(DENS) and a.peak_profile.equals(PROFILE) and a.gaps.equals(GAPS), "the pieces pass through unchanged"
    with pytest.raises(FrameError, match="no rows"):
        grid.winter_peak_answer(RANK, [1, 2], TEMP, DENS, [], GAPS, context=M12)
    assert grid.winter_peak_answer(RANK, PROFILE, TEMP, DENS, [], GAPS.iloc[:0], context=M12).gaps.empty, "an empty gap list stays empty, nothing is filled"
    with pytest.raises(FrameError, match="no ranked zone"):
        grid.winter_peak_answer(RANK.assign(rank=None), PROFILE, TEMP, DENS, [], GAPS, context=M12)
    with pytest.raises(FrameError, match="no rows"):
        grid.winter_peak_answer(RANK, PROFILE.iloc[:0], TEMP, DENS, [], GAPS, context=M12)
    with pytest.raises(FrameError, match="lacks column"):
        grid.winter_peak_answer(RANK, PROFILE, TEMP.drop(columns="outdoor_c"), DENS, [], GAPS, context=M12)
    with pytest.raises(FrameError, match="clusters"):
        grid.winter_peak_answer(RANK, PROFILE, TEMP, DENS, "x", GAPS, context=M12)


STR = pd.DataFrame({"net_key": ["a", "b"], "strained": [True, False], "load_strained": [True, None]})
ZS = pd.DataFrame({"zone_key": ["Z4", "Z2"], "n_elements": [10, 20], "n_strained": [3, 1]})
PU = pd.DataFrame({"itm_key": ["I1"], "units": [2.0]})
CR = pd.DataFrame({"itm_key": ["I2", "I1", "I3"], "uom": ["pcs"] * 3, "units": [1.0, 2.0, 0.0]})


def test_grid_strain_answer_hands_over_keys_only_and_keeps_unknown_strain():
    a = grid.grid_strain_answer(STR, ZS, PU, CR, context=M12)
    assert a.item_keys == ("I1", "I2") and a.zone_keys == ("Z2", "Z4"), "sorted, the item that was never issued is not asked about"
    assert a.strained.load_strained.isna().sum() == 1 and a.labels == ("synthetic data",)
    with pytest.raises(FrameError, match="do not belong"):
        grid.grid_strain_answer(STR, ZS, PU, CR.assign(stock_on_hand=1.0), context=M12)
    with pytest.raises(FrameError, match="do not belong"):
        grid.grid_strain_answer(STR, ZS, PU, CR.assign(unit_price=1.0), context=M12)
    with pytest.raises(FrameError, match="lacks column"):
        grid.grid_strain_answer(STR.drop(columns="strained"), ZS, PU, CR, context=M12)
    with pytest.raises(FrameError, match="zone_summary.unit_cost"):
        grid.grid_strain_answer(STR, ZS.assign(unit_cost=1.0), PU, CR, context=M12)
    assert grid.grid_strain_answer(STR, ZS.assign(reorder_level=1.0, border_km=2.0), PU, CR, context=M12).item_keys == ("I1", "I2"), "whole words only: reorder and border are not order"
    with pytest.raises(FrameError, match="stock"):
        grid.grid_strain_answer(STR, ZS, PU, CR.assign(no_stock=1.0), context=M12)


RC = pd.DataFrame({"prj_key": ["P1", "P2"], "planned_length_m": [5200.0, 100.0], "as_built_length_m": [6100.5, None], "delta_m": [900.5, None], "changed": [True, False]})
SOIL = pd.DataFrame({"prj_key": ["P1", "P2"], "version": [2, 2], "soil_class": ["peat", "sand"], "share": [0.7, 1.0]})
COND = pd.DataFrame({"prj_key": ["P1", "P2"], "version": [2, 2], "crosses_poor_bearing": [True, False], "crosses_high_groundwater": [True, False]})


def test_route_facts_joins_soil_and_flags_and_marks_summary_projects():
    r = grid.route_facts(RC, SOIL, COND, pd.DataFrame({"prj_key": ["P1", "P2", "P9"]}), context=M12)
    row = r.routes.set_index("prj_key")
    assert row.loc["P1", "soil_class"] == "peat" and row.loc["P1", "soil_share"] == 0.7 and bool(row.loc["P1", "crosses_poor_bearing"]) and row.loc["P1", "delta_m"] == 900.5
    assert r.summary_projects == ("P9",) and r.labels == ("synthetic data",), "a project without a route is marked, not given values"
    with pytest.raises(FrameError, match="more than one"):
        grid.route_facts(pd.concat([RC, RC.iloc[:1]]), SOIL, COND, context=M12)
    asb = pd.concat([SOIL, SOIL.iloc[:1].assign(version=3, soil_class="clay", share=0.9)])
    assert grid.route_facts(RC, asb, COND, context=M12).routes.set_index("prj_key").loc["P1", "soil_class"] == "peat", "the as-built soil is not the planned soil"
    with pytest.raises(FrameError, match="more than one row for a project and version"):
        grid.route_facts(RC, pd.concat([SOIL, SOIL.iloc[:1]]), COND, context=M12)
    with pytest.raises(FrameError, match="does not hold"):
        grid.route_facts(RC, SOIL.assign(prj_key=["P1", "P7"]), COND, context=M12)


def test_stage_and_facade_for_recipes():
    for n in ("winter_peak_answer", "grid_strain_answer", "route_facts"):
        assert f"halvaro.grid.recipes.{n}" in registry.registered() and n in grid.__all__
    with pytest.raises(StageRefusal):
        grid.route_facts(RC, SOIL, COND, context=Context(stage="month3", role="r"))



def test_second_round_forbidden_words_in_other_spellings_and_null_keys():
    for col in ("stockLevel", "unit-price", "Order Qty"):
        with pytest.raises(FrameError, match="do not belong"):
            grid.grid_strain_answer(STR, ZS, PU, CR.assign(**{col: 1.0}), context=M12)
    with pytest.raises(FrameError, match="null itm_key"):
        grid.grid_strain_answer(STR, ZS, PU, CR.assign(itm_key=[None, "I1", "I3"]), context=M12)
    with pytest.raises(FrameError, match="null itm_key"):
        grid.grid_strain_answer(STR, ZS.assign(zone_key=[None, "Z2"]), PU, CR, context=M12)
