"""ESG scoring of Halvaro itself, environment pillar (plan 5.11, gated, PROPOSED). The estate holds no scoring method: every threshold here is a keyword or a proposed policy fact
(`policy.esg.scoring_*`, status proposed) that the owner has not decided, and every result says so (status VERIFY+synthetic). The score is a demonstration of how a score could be built from
the numbers the library already owns. It is not a statement about CSRD or ESRS, it is not an assurance and it is not for external use while factors are synthetic or a VERIFY fact is open.
"""
from __future__ import annotations

import dataclasses
from typing import Any, Mapping, NamedTuple, Sequence, cast

import numpy as np
import pandas as pd

from halvaro.core import FrameError, fact, make_envelope

from ._guard import staged, unwrapped
from ._util import Provenance, _day, _need
from ._types import DateLike
from .activity import electricity_contract_share
from .audit_targets import audit_schedule, target_progress

_FACT_OF = {"band_a_min": "policy.esg.scoring_band_a_min", "band_b_min": "policy.esg.scoring_band_b_min", "band_c_min": "policy.esg.scoring_band_c_min",
            "missing_data_min_weight": "policy.esg.scoring_missing_data_min_weight", "basis": "policy.esg.scoring_basis", "external_use": "policy.esg.scoring_external_use"}
_POLICY_KEYS = ("band_a_min", "band_b_min", "band_c_min", "missing_data_min_weight", "basis", "external_use")
INDICATORS = ("scope1", "scope2_location", "scope3", "project_intensity", "renewable_electricity_share", "epd_coverage", "audit_currency")
_GLIDE = {"scope1": "1", "scope2_location": "2_location", "scope3": "3", "project_intensity": "project_intensity"}
LABEL = "demo score on synthetic data, not for external use, no statement about CSRD or ESRS"

_T = tuple(f"energy-esg.target.{c}" for c in ("target_no", "scope", "baseline_year", "target_year", "baseline_value", "target_value"))
_L = tuple(f"energy-esg.emission_line.{c}" for c in ("le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period"))
_IV = (*_T, *_L, *(f"energy-esg.energy_consumption.{c}" for c in ("mtr_key", "period", "quantity", "unit", "contract_type")),
       *(f"energy-esg.item_epd.{c}" for c in ("itm_key", "valid_from", "valid_to", "source")), *(f"energy-esg.energy_audit.{c}" for c in ("site_key", "audit_date", "due_date", "status")))
_SC = ("energy-esg.target.baseline_value", "energy-esg.target.target_value")


def _prov(value: Any, function: str, sources: Sequence[str], facts: Sequence[Any] = (), *warnings: str) -> Provenance:
    env = make_envelope(value, function, facts=facts, sources=sources, warnings=("proposed scoring, synthetic data: " + LABEL, *warnings), cls=Provenance)
    return cast(Provenance, dataclasses.replace(env, status="VERIFY+synthetic", synthetic=True))


def _policy(policy: Mapping[str, Any] | None) -> tuple[dict[str, Any], list[Any]]:
    """The scoring policy: facts policy.esg.scoring_* (proposed), each key overridable by the mapping. Returns (values, facts read)."""
    given = dict(policy or {})
    unknown = sorted(set(given) - set(_POLICY_KEYS))
    if unknown:
        raise FrameError(f"unknown policy keys {unknown}; known: {', '.join(_POLICY_KEYS)}")
    vals: dict[str, Any] = {}
    used: list[Any] = []
    for k in _POLICY_KEYS:
        if k in given:
            vals[k] = given[k]
        else:
            f = fact(_FACT_OF[k])
            vals[k], used = f.value, [*used, f]
    a, b, c, m = (vals[k] for k in ("band_a_min", "band_b_min", "band_c_min", "missing_data_min_weight"))
    if not all(isinstance(x, (int, float, np.number)) and not isinstance(x, bool) for x in (a, b, c, m)):
        raise FrameError("band limits and the missing data share must be numbers")
    if not (0 <= c < b < a <= 100):
        raise FrameError("band limits must satisfy 0 <= C < B < A <= 100")
    if not (0 < m <= 1):
        raise FrameError("missing_data_min_weight must be above 0 and at most 1")
    return vals, used


def _band(score: Any, vals: Mapping[str, Any]) -> str | None:
    if score is None or pd.isna(score):
        return None
    return "A" if score >= vals["band_a_min"] else "B" if score >= vals["band_b_min"] else "C" if score >= vals["band_c_min"] else "D"


def _share(num: float, den: float) -> float:
    return float(num) / float(den) if den and not np.isnan(den) and den > 0 else np.nan


@staged(sources=_IV, facts=(), oracle="py:repo_tests/test_oracle_score_release.py::test_oracle_indicator_values_equal_direct_pandas_readings_of_the_baseline")
def indicator_values(T: pd.DataFrame, L: pd.DataFrame, C: pd.DataFrame, M: pd.DataFrame, E: pd.DataFrame, A: pd.DataFrame, as_of: DateLike, *, year: int | None = None, cycle_years: int = 4,
                     intensity_actual: float | None = None, epd_marker: str = "supplier EPD") -> Provenance:
    """Use this when you need the seven environment indicator values (glide path and share indicators) before they are scored.

    The seven indicator values as facts, no judgement. Four are glide path indicators from
    `target_progress` (scope 1, scope 2 location, scope 3, project intensity): value = achieved reduction over the required reduction at `year` (PROPOSED reading: (baseline - actual) / (baseline - glide value) at that year,
    current factor basis; a value above 1 is possible and is clipped only when scored), null when the year has fewer than 12 months of lines or the required reduction is zero. `intensity_actual` is the per route metre median, which
    this library does not hold (it comes from halvaro-delivery); without it the project intensity value is null. Three are shares: renewable electricity (kWh on a renewable_certified contract over all
    electricity kWh in `year`), EPD coverage (share of the items valid on the day whose `item_epd.source` contains `epd_marker`, PROPOSED), audit currency (share of audited sites that are not overdue, `cycle_years`
    is the VERIFY keyword of audit_schedule). `year` defaults to the year before `as_of`, as in target_progress. The result has the status VERIFY+synthetic.

    Args:
        T: The energy-esg.target table with the columns target_no, scope, baseline_year, target_year, baseline_value and target_value.
        L: The energy-esg.emission_line table with the columns le_key, period, scope, category, line_no, method, ghg_category, kgco2e, is_superseded and restated_from_period.
        C: The energy-esg.energy_consumption table with the columns mtr_key, period, quantity, unit and contract_type.
        M: The energy-esg.energy_meter table with the columns mtr_key, carrier, unit and site_key.
        E: The energy-esg.item_epd table with the columns itm_key, valid_from, valid_to and source.
        A: The energy-esg.energy_audit table with the columns site_key, audit_date, due_date and status.
        as_of: The day (date, Timestamp, ISO text or YYYY-MM) of the reading; the items and audits are taken as of this day.
        year: The whole year of the readings; the year before as_of when None.
        cycle_years: The audit cycle in whole years (the VERIFY keyword of audit_schedule).
        intensity_actual: The per route metre median of the year, from halvaro-delivery; None leaves the project intensity value null.
        epd_marker: The text that item_epd.source must contain for an item to count as covered (PROPOSED).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        Provenance (status VERIFY+synthetic) whose value is a frame with the columns indicator, kind ('glide' or 'share'), value, baseline, actual, glide_value, n and note, one row per indicator in the order scope1, scope2_location, scope3, project_intensity, renewable_electricity_share, epd_coverage, audit_currency; a value that cannot be read is null and the note says why.

    Raises:
        FrameError: T lacks a column, has a target twice, has no rows, has nulls in a baseline or target value or year, a target scope that is not known, or a target that ends before its baseline year; year is not a whole year; as_of is a number, not a date, or has a time zone.
        FrameError: L lacks a column or is not a valid emission line frame (is_superseded has nulls, a line key is repeated, kgco2e is null, a scope is not 1, 2 or 3, a scope 3 line has no known ghg_category, a scope 2 line has another method than location or market, a restated line has no supersedes_line_no).
        FrameError: C or M lacks a column, has a meter or a meter and period twice, has a period that is not text YYYY-MM, a non numeric or null quantity, a consumption row of an unknown meter or of another unit than its meter, an electricity meter without site_key, electricity not in kWh or without a contract_type.
        FrameError: E lacks a column; A lacks a column, has a null status or site_key, a completed audit without an audit date, an open audit without a due date, two open audits for a site, a value that is not a date, or cycle_years is not a whole number from 1 to 100.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import indicator_values
        >>> ctx = Context(stage="month12", role="analyst")
        >>> cols = ["le_key", "period", "scope", "category", "line_no", "method", "ghg_category", "kgco2e", "is_superseded", "restated_from_period"]
        >>> L = pd.DataFrame([("LE-900001", f"{y}-{m:02d}", 1, "stationary_combustion", 1, None, None, kg, False, None)
        ...                   for y, kg in ((2029, 100.0), (2031, 70.0)) for m in range(1, 13)], columns=cols)
        >>> T = pd.DataFrame({"target_no": [1], "scope": ["1"], "baseline_year": [2029], "target_year": [2035],
        ...                   "baseline_value": [1200.0], "target_value": [600.0]})
        >>> C = pd.DataFrame({"mtr_key": ["MTR-900001", "MTR-900002"], "period": ["2031-01", "2031-01"], "quantity": [300.0, 100.0],
        ...                   "unit": ["kWh", "kWh"], "contract_type": ["renewable_certified", "grid_mix"]})
        >>> M = pd.DataFrame({"mtr_key": ["MTR-900001", "MTR-900002"], "carrier": ["electricity", "electricity"],
        ...                   "unit": ["kWh", "kWh"], "site_key": ["SITE-900001", "SITE-900001"]})
        >>> E = pd.DataFrame({"itm_key": ["ITM-900001", "ITM-900002"], "valid_from": ["2030-01-01", "2030-01-01"],
        ...                   "valid_to": [None, None], "source": ["supplier EPD", "estimate"]})
        >>> A = pd.DataFrame({"site_key": ["SITE-900001"], "audit_date": ["2030-06-01"], "due_date": [None], "status": ["completed"]})
        >>> r = indicator_values(T, L, C, M, E, A, "2032-02-01", context=ctx)
        >>> r.status
        'VERIFY+synthetic'
        >>> r.value.set_index("indicator")["value"].round(2).loc[["scope1", "renewable_electricity_share", "epd_coverage", "audit_currency"]].tolist()
        [1.8, 0.75, 0.5, 1.0]
    """
    d = _day(as_of, "as_of")
    y = d.year - 1 if year is None else int(year)
    prog = unwrapped(target_progress)(T, L, d, year=y).value
    rows = []
    for ind, sc in _GLIDE.items():
        r = prog[prog["scope"].astype(str) == sc]
        if r.empty:
            rows.append((ind, "glide", np.nan, np.nan, np.nan, np.nan, 0, f"no target with scope {sc}"))
            continue
        r = r.iloc[0]
        actual = intensity_actual if ind == "project_intensity" else r["actual"]
        base, glide = float(r["baseline_value"]), float(r["glide_value"])
        months = r.get("months", np.nan)
        note = ""
        if actual is None or pd.isna(actual):
            val, note = np.nan, "no actual: the per route metre median comes from halvaro-delivery" if ind == "project_intensity" else "no lines in the year"
        elif ind != "project_intensity" and (pd.isna(months) or months < 12):
            val, note = np.nan, f"only {0 if pd.isna(months) else int(months)} months of lines in {y}"
        elif base - glide <= 0:
            val, note = np.nan, "no required reduction yet on the glide path"
        else:
            val = (base - float(actual)) / (base - glide)
        rows.append((ind, "glide", val, base, np.nan if actual is None else float(actual), glide, int(0 if pd.isna(months) else months) if ind != "project_intensity" else 0, note))
    ecs = unwrapped(electricity_contract_share)(C, M)
    ecs = getattr(ecs, "value", ecs)
    ey = ecs[ecs["period"].astype(str).str[:4] == str(y)]
    rows.append(("renewable_electricity_share", "share", _share(ey["renewable_kwh"].sum(), ey["kwh"].sum()), np.nan, np.nan, np.nan, int(ey["period"].nunique()),
                 "" if len(ey) else f"no electricity consumption in {y}"))
    _need(E, ["itm_key", "valid_from", "valid_to", "source"], "energy-esg.item_epd")
    vf, vt = pd.to_datetime(E["valid_from"]), pd.to_datetime(E["valid_to"])
    live = E[(vf <= d) & (vt.isna() | (vt >= d))]
    has = live["source"].astype(str).str.contains(epd_marker, regex=False)
    rows.append(("epd_coverage", "share", _share(has.sum(), len(live)), np.nan, np.nan, np.nan, int(len(live)), "" if len(live) else "no item with an EPD row on the day"))
    sch = unwrapped(audit_schedule)(A, d, cycle_years=cycle_years).value
    rows.append(("audit_currency", "share", _share((~sch["overdue"].astype(bool)).sum(), len(sch)), np.nan, np.nan, np.nan, int(len(sch)), "" if len(sch) else "no audited site"))
    out = pd.DataFrame(rows, columns=["indicator", "kind", "value", "baseline", "actual", "glide_value", "n", "note"])
    return _prov(out, "halvaro.esg.score.indicator_values", _IV, (), f"year {y}, current factor basis, as of {d.date()}")


@staged(sources=_SC, facts=tuple(_FACT_OF[k] for k in _POLICY_KEYS), oracle="py:tests/test_oracle_score.py::test_oracle_score_indicators_scores_and_bands_follow_the_proposed_limits")
def score_indicators(v: pd.DataFrame, policy: Mapping[str, Any] | None = None) -> Provenance:
    """Use this when you need each indicator value turned into a score from 0 to 100 and a band from A to D.

    A glide indicator scores its value times 100 (achieved over required reduction), a share indicator its share times 100, both clipped to 0 to 100 (PROPOSED,
    policy.esg.scoring_thresholds); a null value stays null and gets no band. Bands: A from policy.esg.scoring_band_a_min (80), B from band_b_min (60), C from band_c_min (40), else D. `policy` is a
    mapping that replaces any of the policy keys (band_a_min, band_b_min, band_c_min, missing_data_min_weight, basis, external_use); the rest come from the proposed facts.
    Properties (tested): scores between 0 and 100, monotonic in the value, deterministic.

    Args:
        v: The output of indicator_values (a Provenance or its frame) with the columns indicator, kind ('glide' or 'share') and value.
        policy: A mapping that replaces any of the policy keys band_a_min, band_b_min, band_c_min, missing_data_min_weight, basis and external_use; None to take every key from the proposed policy facts.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        Provenance (status VERIFY+synthetic, the policy facts that were read) whose value is a frame with the columns indicator, kind, value, score (0 to 100, rounded to 2 decimals) and band (A, B, C, D, or null when the score is null), in the order of v.

    Raises:
        FrameError: v lacks indicator, kind or value; an indicator is twice in v; a kind is not glide or share.
        FrameError: policy has a key that is not known; a band limit or missing_data_min_weight is not a number; the band limits do not satisfy 0 <= C < B < A <= 100; missing_data_min_weight is not above 0 and at most 1.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import score_indicators
        >>> ctx = Context(stage="month12", role="analyst")
        >>> v = pd.DataFrame({"indicator": ["scope1", "epd_coverage", "audit_currency"], "kind": ["glide", "share", "share"], "value": [1.4, 0.5, None]})
        >>> out = score_indicators(v, context=ctx).value
        >>> out[["indicator", "score", "band"]].values.tolist()
        [['scope1', 100.0, 'A'], ['epd_coverage', 50.0, 'C'], ['audit_currency', nan, None]]
    """
    v = v.value if isinstance(v, Provenance) else v
    _need(v, ["indicator", "kind", "value"], "indicator frame")
    if v["indicator"].duplicated().any():
        raise FrameError("the indicator frame has an indicator twice")
    bad = sorted(set(v["kind"]) - {"glide", "share"})
    if bad:
        raise FrameError(f"unknown indicator kind {bad}; known: glide, share")
    vals, used = _policy(policy)
    out = v[["indicator", "kind", "value"]].copy()
    out["score"] = (out["value"].astype(float) * 100.0).clip(0.0, 100.0).round(2)
    out["band"] = [_band(s, vals) for s in out["score"]]
    return _prov(out.reset_index(drop=True), "halvaro.esg.score.score_indicators", _SC, used)


class Scorecard(NamedTuple):
    """Weighted score of the scored indicators: `score` and `band` (null when too little weight is present), `indicators` (indicator, score, band, weight), `missing` (indicators without a score),
    `weight_present`, `version`, `as_of`, `basis` (the policy text), `external_use` (the policy text), `label` (demo label), `status` (VERIFY+synthetic) and `facts_used`."""
    score: float | None
    band: str | None
    indicators: pd.DataFrame
    missing: tuple[str, ...]
    weight_present: float
    version: str
    as_of: pd.Timestamp
    basis: str
    external_use: str
    label: str
    status: str
    facts_used: tuple[Any, ...]


@staged(sources=_SC, facts=tuple(_FACT_OF[k] for k in _POLICY_KEYS), oracle="py:tests/test_oracle_score.py::test_oracle_scorecard_is_the_weighted_mean_over_the_weight_present")
def scorecard(s: pd.DataFrame, policy: Mapping[str, Any] | None = None, *, as_of: DateLike, weights: Mapping[str, Any] | None = None, version: str = "v0 proposed") -> Scorecard:
    """Use this when you need the weighted overall score and band of the scored indicators, with the missing data list and the demo label.

    The weighted overall score, band, missing data list, version, as-of and the demo label. Indicators without a score are listed in `missing` and left out; the score is the weighted mean over the weight that is present, and is null (and so is the band) when the present
    weight is below policy.esg.scoring_missing_data_min_weight (0.7). The `version` names the policy version (effective dated, change needs sign-off: policy.esg.scoring_governance, not coded).

    Args:
        s: The output of score_indicators (a Provenance or its frame) with the columns indicator and score.
        policy: A mapping that replaces any of the policy keys band_a_min, band_b_min, band_c_min, missing_data_min_weight, basis and external_use; None to take every key from the proposed policy facts.
        as_of: The day (date, Timestamp, ISO text or YYYY-MM) that is printed on the scorecard.
        weights: Mapping from each indicator to its weight (default equal: the proposed policy.esg.scoring_weights); it must name exactly the indicators of s, be non negative and sum to 1.
        version: The name of the policy version that is printed on the scorecard.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A Scorecard with score (null when too little weight is present) and band, indicators (a frame with indicator, score, band and weight), missing (the indicators without a score), weight_present, version, as_of, basis (the policy text), external_use (the policy text), label (the demo label), status (VERIFY+synthetic) and facts_used.

    Raises:
        FrameError: s lacks indicator or score; an indicator is twice in s; as_of is a number, not a date, or has a time zone.
        FrameError: policy has a key that is not known; a band limit or missing_data_min_weight is not a number; the band limits do not satisfy 0 <= C < B < A <= 100; missing_data_min_weight is not above 0 and at most 1.
        FrameError: weights does not name exactly the indicators of s, has a negative weight, or does not sum to 1.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import scorecard
        >>> ctx = Context(stage="month12", role="analyst")
        >>> s = pd.DataFrame({"indicator": ["scope1", "epd_coverage"], "score": [90.0, 50.0]})
        >>> card = scorecard(s, as_of="2032-02-01", weights={"scope1": 0.5, "epd_coverage": 0.5}, context=ctx)
        >>> card.score, card.band, card.missing, card.weight_present
        (70.0, 'B', (), 1.0)
        >>> s2 = pd.DataFrame({"indicator": ["scope1", "epd_coverage", "audit_currency"], "score": [90.0, 50.0, None]})
        >>> thin = scorecard(s2, as_of="2032-02-01", context=ctx)
        >>> thin.score, thin.band, thin.missing
        (None, None, ('audit_currency',))
    """
    s = s.value if isinstance(s, Provenance) else s
    _need(s, ["indicator", "score"], "scored indicator frame")
    if s["indicator"].duplicated().any():
        raise FrameError("the scored frame has an indicator twice")
    d = _day(as_of, "as_of")
    vals, used = _policy(policy)
    names = list(s["indicator"])
    if weights is None:
        w = {n: 1.0 / len(names) for n in names} if names else {}
    else:
        if set(weights) != set(names):
            raise FrameError(f"weights must name exactly the indicators {sorted(names)}")
        w = {n: float(weights[n]) for n in names}
        if any(x < 0 for x in w.values()) or not np.isclose(sum(w.values()), 1.0, atol=1e-9):
            raise FrameError("weights must be non negative and sum to 1")
    ind = s[["indicator", "score"]].copy()
    ind["band"] = [_band(x, vals) for x in ind["score"]]
    ind["weight"] = [w[n] for n in ind["indicator"]]
    have = ind["score"].notna()
    present = float(ind.loc[have, "weight"].sum())
    score = float((ind.loc[have, "score"] * ind.loc[have, "weight"]).sum() / present) if present > 0 and present >= vals["missing_data_min_weight"] - 1e-12 else None
    score = None if score is None else round(score, 2)
    return Scorecard(score, _band(score, vals), ind.reset_index(drop=True), tuple(ind.loc[~have, "indicator"]), round(present, 6), version, d, str(vals["basis"]), str(vals["external_use"]), LABEL,
                     "VERIFY+synthetic", tuple((f.id, f.value, f.status) for f in used))
