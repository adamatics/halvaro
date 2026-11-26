"""Emission lines: the current basis, the lines as first booked, restated pairs, the lines visible at a booking period and the checks that keep a total from counting a line twice.

Trap T1: restated lines are new rows and the originals stay. A year summed over all lines counts the restated factor change twice. A restated line carries restated_from_period (the booking
period of the restatement, 2026-01 for 2025) and supersedes_line_no, the line_no of its original (same entity, period, scope and category); the original has is_superseded true. `is_superseded` is
state as of now (T3): `as_of_view` ignores it and works from the booking periods.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from halvaro.core import FrameError, violations

from ._guard import staged, unwrapped
from ._util import _LINE_COLS, _LINK_COLS, _basis, _lines, _need, _num, _period_text
from .factors import family_key

_L = ("energy-esg.emission_line.le_key", "energy-esg.emission_line.period", "energy-esg.emission_line.scope", "energy-esg.emission_line.category", "energy-esg.emission_line.line_no",
      "energy-esg.emission_line.kgco2e", "energy-esg.emission_line.is_superseded", "energy-esg.emission_line.restated_from_period", "energy-esg.emission_line.supersedes_line_no")
_KEY = ["le_key", "period", "scope", "category"]
_TOL_KG = 0.002


def _links(flag: pd.DataFrame, *, full: bool, upto: str | None = None) -> None:
    """A restated line (restated_from_period set) must name the original it replaces (supersedes_line_no): without the link no basis can tell what it replaces. With full (the unfiltered table) the
    original must exist in the frame, and a line flagged is_superseded must be replaced by a restated line. upto limits the first check to lines restated up to a period."""
    restated = flag["restated_from_period"].notna() if upto is None else flag["restated_from_period"].notna() & (flag["restated_from_period"] <= upto)
    unlinked = restated & flag["supersedes_line_no"].isna()
    if unlinked.any():
        raise FrameError(f"{int(unlinked.sum())} restated lines have no supersedes_line_no; the original they replace cannot be told, so a total would count the change twice")
    if full:
        idx = pd.MultiIndex.from_arrays([flag["le_key"], flag["period"], flag["scope"], flag["category"], _num(flag["line_no"])])
        new = flag[flag["restated_from_period"].notna()]
        target = pd.MultiIndex.from_arrays([new["le_key"], new["period"], new["scope"], new["category"], _num(new["supersedes_line_no"])])
        lost = ~target.isin(idx)
        if lost.any():
            raise FrameError(f"{int(lost.sum())} restated lines replace a line that is not in the frame (for example line_no {new['supersedes_line_no'].iloc[int(np.argmax(lost))]})")
        orphan = flag["is_superseded"].astype(bool).to_numpy() & ~idx.isin(target)
        if orphan.any():
            raise FrameError(f"{int(orphan.sum())} lines are flagged is_superseded but no restated line replaces them; a total over the current basis would lose them")


@staged(sources=_L, oracle="py:halvaro_gen/world/energy_esg/truth.py::esg_truth")
def current_basis(L: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need the emission lines without the superseded originals, so that a total counts every restatement once.

    The lines without the superseded originals (is_superseded false): restated lines stand, originals that were replaced do not. A total over this frame counts every change once. The frame is checked first: a restated line must name its original and the original must be in the frame, a line flagged is_superseded must be replaced by a restated line, and an original that a restated line replaces must be flagged is_superseded (T3).

    Args:
        L: The energy-esg.emission_line table, unfiltered, with the columns le_key, period, scope, category, line_no, is_superseded, restated_from_period and supersedes_line_no.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        The lines of L with is_superseded false, with all columns of L, in the order of L and a fresh index.

    Raises:
        FrameError: a column is missing, is_superseded has nulls, or the line key (le_key, period, scope, category, line_no) is used twice.
        FrameError: a restated line (restated_from_period set) has no supersedes_line_no, or replaces a line that is not in the frame.
        FrameError: a line is flagged is_superseded but no restated line replaces it, or an original is replaced by a restated line but is not flagged is_superseded.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import current_basis
        >>> ctx = Context(stage="month12", role="analyst")
        >>> L = pd.DataFrame({
        ...     "le_key": ["LE-900001", "LE-900001"], "period": ["2025-03", "2025-03"], "scope": [1, 1], "category": ["gas", "gas"],
        ...     "line_no": [1, 2], "kgco2e": [200.0, 190.0], "quantity": [1000.0, 1000.0], "efac_key": ["EF-900001", "EF-900002"],
        ...     "method": [None, None], "ghg_category": ["1", "1"], "restated_from_period": [None, "2026-01"],
        ...     "supersedes_line_no": [None, 1], "is_superseded": [True, False]})
        >>> current_basis(L, context=ctx)["line_no"].tolist()
        [2]
    """
    flag = _lines(L, base=_LINK_COLS)
    _links(flag, full=True)
    new = flag[flag["restated_from_period"].notna() & flag["supersedes_line_no"].notna()]
    replaced = pd.MultiIndex.from_arrays([new["le_key"], new["period"], new["scope"], new["category"], _num(new["supersedes_line_no"])])
    stale = pd.MultiIndex.from_arrays([flag["le_key"], flag["period"], flag["scope"], flag["category"], _num(flag["line_no"])]).isin(replaced) & ~flag["is_superseded"].astype(bool).to_numpy()
    if stale.any():
        raise FrameError(f"{int(stale.sum())} original lines are replaced by a restated line but not flagged is_superseded; a total over the current basis would count them twice (T3)")
    return _basis(L, "current").reset_index(drop=True)


@staged(sources=_L, oracle="py:halvaro_gen/world/energy_esg/truth.py::esg_truth")
def as_first_booked(L: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need the emission lines as they were first booked, before any restatement.

    The lines without the restated lines (restated_from_period null): the figures as they were first booked, replaced originals included.

    Args:
        L: The energy-esg.emission_line table with the columns le_key, period, scope, category, line_no, is_superseded and restated_from_period.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        The lines of L with restated_from_period null, with all columns of L, in the order of L and a fresh index.

    Raises:
        FrameError: a column is missing, is_superseded has nulls, or the line key (le_key, period, scope, category, line_no) is used twice.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import as_first_booked
        >>> ctx = Context(stage="month12", role="analyst")
        >>> L = pd.DataFrame({
        ...     "le_key": ["LE-900001", "LE-900001"], "period": ["2025-03", "2025-03"], "scope": [1, 1], "category": ["gas", "gas"],
        ...     "line_no": [1, 2], "kgco2e": [200.0, 190.0], "quantity": [1000.0, 1000.0], "efac_key": ["EF-900001", "EF-900002"],
        ...     "method": [None, None], "ghg_category": ["1", "1"], "restated_from_period": [None, "2026-01"],
        ...     "supersedes_line_no": [None, 1], "is_superseded": [True, False]})
        >>> as_first_booked(L, context=ctx)["line_no"].tolist()
        [1]
    """
    return _basis(L, "first_booked").reset_index(drop=True)


@staged(sources=(*_L, "energy-esg.emission_line.quantity", "energy-esg.emission_line.efac_key", "energy-esg.emission_line.method"), oracle="py:tests/test_energy_esg.py::test_restatement_keeps_old_lines")
def restatement_pairs(L: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need each restated emission line next to the original it replaces, with the change in kg.

    Each restated line next to its original, one to one on (le_key, period, scope, category) and supersedes_line_no = line_no. A restated line without its original, an original replaced twice, a different quantity, key or method, or an unchanged factor raises FrameError. delta_kg is kg_restated minus kg_original, rounded to 3 decimals.

    Args:
        L: The energy-esg.emission_line table with the columns le_key, period, scope, category, line_no, kgco2e, quantity, efac_key, method, ghg_category, restated_from_period, supersedes_line_no and is_superseded.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with one row per restated line and the columns le_key, period, scope, category, method, line_no_original, line_no_restated, restated_from_period, quantity_original, quantity_restated, efac_original, efac_restated, kg_original, kg_restated and delta_kg, sorted by le_key, period, scope, category and line_no_original.

    Raises:
        FrameError: a column is missing, is_superseded has nulls, or the line key is used twice.
        FrameError: a restated line has no supersedes_line_no, or no original line.
        FrameError: an original line is replaced by more than one restated line, or a restated line replaces another restated line (chains are not supported).
        FrameError: a restated line or its original has no quantity or no efac_key, differs from its original in quantity (more than 1e-6) or method, or has the same factor as its original.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import restatement_pairs
        >>> ctx = Context(stage="month12", role="analyst")
        >>> L = pd.DataFrame({
        ...     "le_key": ["LE-900001", "LE-900001"], "period": ["2025-03", "2025-03"], "scope": [1, 1], "category": ["gas", "gas"],
        ...     "line_no": [1, 2], "kgco2e": [200.0, 190.0], "quantity": [1000.0, 1000.0], "efac_key": ["EF-900001", "EF-900002"],
        ...     "method": [None, None], "ghg_category": ["1", "1"], "restated_from_period": [None, "2026-01"],
        ...     "supersedes_line_no": [None, 1], "is_superseded": [True, False]})
        >>> pairs = restatement_pairs(L, context=ctx)
        >>> pairs[["line_no_original", "line_no_restated", "delta_kg"]].to_dict("records")
        [{'line_no_original': 1, 'line_no_restated': 2, 'delta_kg': -10.0}]
    """
    L = _lines(L)
    new = L[L["restated_from_period"].notna()]
    if new["supersedes_line_no"].isna().any():
        raise FrameError("a restated line has no supersedes_line_no")
    new = new.assign(_orig_no=_num(new["supersedes_line_no"]))
    m = new.merge(L.assign(_line=_num(L["line_no"])), left_on=[*_KEY, "_orig_no"], right_on=[*_KEY, "_line"], how="left", suffixes=("_restated", "_original"), indicator=True)
    if (m["_merge"] != "both").any():
        raise FrameError(f"{int((m['_merge'] != 'both').sum())} restated lines have no original line")
    if m.duplicated([*_KEY, "_orig_no"]).any():
        raise FrameError("an original line is replaced by more than one restated line")
    if (m["restated_from_period_original"].notna()).any():
        raise FrameError("a restated line replaces another restated line; chains are not supported")
    if m[["quantity_restated", "quantity_original", "efac_key_restated", "efac_key_original"]].isna().any().any():
        raise FrameError("restated lines and their originals need a quantity and an efac_key")
    if ((m["quantity_restated"] - m["quantity_original"]).abs() > 1e-6).any() or (m["method_restated"].fillna("-") != m["method_original"].fillna("-")).any():
        raise FrameError("a restated line differs from its original in quantity or method")
    if (m["efac_key_restated"] == m["efac_key_original"]).any():
        raise FrameError("a restated line has the same factor as its original")
    out = pd.DataFrame({"le_key": m["le_key"], "period": m["period"], "scope": m["scope"], "category": m["category"], "method": m["method_restated"], "line_no_original": m["line_no_original"],
                        "line_no_restated": m["line_no_restated"], "restated_from_period": m["restated_from_period_restated"], "quantity_original": m["quantity_original"],
                        "quantity_restated": m["quantity_restated"], "efac_original": m["efac_key_original"], "efac_restated": m["efac_key_restated"], "kg_original": m["kgco2e_original"],
                        "kg_restated": m["kgco2e_restated"]})
    out["delta_kg"] = (out["kg_restated"] - out["kg_original"]).round(3)
    return out.sort_values([*_KEY, "line_no_original"]).reset_index(drop=True)


@staged(sources=_L, oracle="py:repo_tests/test_oracle_lines_release.py::test_oracle_as_of_view_equals_a_plain_loop_over_the_baseline_lines")
def as_of_view(L: pd.DataFrame, as_of: str) -> pd.DataFrame:
    """Use this when you need the emission lines that were visible at a booking period, whatever is_superseded says today.

    The lines visible at a booking period (text 'YYYY-MM'), from restated_from_period and the replacement links, ignoring is_superseded: lines of periods up to as_of, restated lines booked up to as_of, and originals that no restated line booked up to as_of has replaced. is_superseded is state as of now (T3) and is not used.

    Args:
        L: The energy-esg.emission_line table with the columns le_key, period, scope, category, line_no, is_superseded, restated_from_period and supersedes_line_no.
        as_of: The booking period as text 'YYYY-MM', for example 2025-12.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        The visible lines of L with all columns of L, in the order of L and a fresh index.

    Raises:
        FrameError: as_of is not a period text like 2025-12.
        FrameError: a column is missing, is_superseded has nulls, or the line key is used twice.
        FrameError: a line restated up to as_of has no supersedes_line_no.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import as_of_view
        >>> ctx = Context(stage="month12", role="analyst")
        >>> L = pd.DataFrame({
        ...     "le_key": ["LE-900001", "LE-900001"], "period": ["2025-03", "2025-03"], "scope": [1, 1], "category": ["gas", "gas"],
        ...     "line_no": [1, 2], "kgco2e": [200.0, 190.0], "quantity": [1000.0, 1000.0], "efac_key": ["EF-900001", "EF-900002"],
        ...     "method": [None, None], "ghg_category": ["1", "1"], "restated_from_period": [None, "2026-01"],
        ...     "supersedes_line_no": [None, 1], "is_superseded": [True, False]})
        >>> as_of_view(L, "2025-12", context=ctx)["line_no"].tolist()
        [1]
        >>> as_of_view(L, "2026-01", context=ctx)["line_no"].tolist()
        [2]
    """
    a = _period_text(as_of, "as_of")
    L = _lines(L, base=_LINK_COLS)
    _links(L, full=False, upto=a)
    booked = L["restated_from_period"].isna() | (L["restated_from_period"] <= a)
    new = L[L["restated_from_period"].notna() & (L["restated_from_period"] <= a) & L["supersedes_line_no"].notna()]
    replaced = pd.MultiIndex.from_arrays([new["le_key"], new["period"], new["scope"], new["category"], _num(new["supersedes_line_no"])])
    gone = pd.MultiIndex.from_arrays([L["le_key"], L["period"], L["scope"], L["category"], _num(L["line_no"])]).isin(replaced)
    return L[booked.to_numpy() & ~gone & (L["period"] <= a).to_numpy()].reset_index(drop=True)


@staged(sources=(*_L, "energy-esg.emission_line.quantity", "energy-esg.emission_line.efac_key", "energy-esg.emission_line.method", "energy-esg.emission_factor.efac_key", "energy-esg.emission_factor.category",
                 "energy-esg.emission_factor.carrier", "energy-esg.emission_factor.region", "energy-esg.emission_factor.method"), oracle="py:halvaro_gen/world/energy_esg/truth.py::esg_truth")
def restatement_bridge(L: pd.DataFrame, F: pd.DataFrame, year: int) -> pd.DataFrame:
    """Use this when you need the change from first booked to restated emissions of one year, by scope, category and factor family.

    From first booked to restated for the periods of one year, by scope, category and factor family: kg of the replaced originals, kg of the restated lines, the change and its percent. Only restated pairs count (see restatement_pairs), so a year without a restatement gives an empty frame. delta_percent is null when kg_first_booked is not above 0.

    Args:
        L: The energy-esg.emission_line table with the columns le_key, period, scope, category, line_no, kgco2e, quantity, efac_key, method, ghg_category, restated_from_period, supersedes_line_no and is_superseded.
        F: The energy-esg.emission_factor table with the columns efac_key, category, carrier, region and method (one row per efac_key).
        year: The year of the periods to bridge, a whole number such as 2025.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns scope, category, family, n_lines, kg_first_booked, kg_restated, delta_kg and delta_percent (two decimals), sorted by scope, category and family.

    Raises:
        FrameError: year is not a whole number, or F lacks a column or has more than one row for an efac_key.
        FrameError: the lines fail the checks of restatement_pairs (missing columns, a restated line without original, chains, a changed quantity or method, an unchanged factor).
        FrameError: a factor of the lines is not in F, or a restatement changes the factor family, not only the factor.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import restatement_bridge
        >>> ctx = Context(stage="month12", role="analyst")
        >>> L = pd.DataFrame({
        ...     "le_key": ["LE-900001", "LE-900001"], "period": ["2025-03", "2025-03"], "scope": [1, 1], "category": ["gas", "gas"],
        ...     "line_no": [1, 2], "kgco2e": [200.0, 190.0], "quantity": [1000.0, 1000.0], "efac_key": ["EF-900001", "EF-900002"],
        ...     "method": [None, None], "ghg_category": ["1", "1"], "restated_from_period": [None, "2026-01"],
        ...     "supersedes_line_no": [None, 1], "is_superseded": [True, False]})
        >>> F = pd.DataFrame({
        ...     "efac_key": ["EF-900001", "EF-900002"], "category": ["gas", "gas"], "carrier": ["natural_gas", "natural_gas"],
        ...     "region": ["DE", "DE"], "method": [None, None]})
        >>> bridge = restatement_bridge(L, F, 2025, context=ctx)
        >>> bridge[["family", "n_lines", "kg_first_booked", "kg_restated", "delta_kg", "delta_percent"]].to_dict("records")
        [{'family': 'gas|natural_gas|DE|-', 'n_lines': 1, 'kg_first_booked': 200.0, 'kg_restated': 190.0, 'delta_kg': -10.0, 'delta_percent': -5.0}]
    """
    if not isinstance(year, (int, np.integer)) or isinstance(year, bool):
        raise FrameError(f"year must be a whole number, not {year!r}")
    _need(F, ["efac_key", "category", "carrier", "region", "method"], "energy-esg.emission_factor")
    L = _lines(L)
    pairs = unwrapped(restatement_pairs)(L[L["period"].astype(str).str[:4] == str(int(year))])
    fam = pd.Series(unwrapped(family_key)(F).to_numpy(), index=F["efac_key"].to_numpy())
    if fam.index.duplicated().any():
        raise FrameError("energy-esg.emission_factor has more than one row for an efac_key")
    missing = sorted((set(pairs["efac_original"]) | set(pairs["efac_restated"])) - set(fam.index))
    if missing:
        raise FrameError(f"{len(missing)} factors of the lines are not in energy-esg.emission_factor (for example {missing[0]})")
    pairs = pairs.assign(family=pairs["efac_original"].map(fam))
    if (pairs["efac_restated"].map(fam) != pairs["family"]).any():
        raise FrameError("a restatement changes the factor family, not only the factor")
    g = pairs.groupby(["scope", "category", "family"], as_index=False).agg(n_lines=("delta_kg", "size"), kg_first_booked=("kg_original", "sum"), kg_restated=("kg_restated", "sum"))
    g["delta_kg"] = (g["kg_restated"] - g["kg_first_booked"]).round(3)
    g["delta_percent"] = np.where(g["kg_first_booked"] > 0, np.round(g["delta_kg"] / g["kg_first_booked"].where(g["kg_first_booked"] > 0) * 100, 2), np.nan)
    return g.round({"kg_first_booked": 3, "kg_restated": 3}).sort_values(["scope", "category", "family"]).reset_index(drop=True)


@staged(sources=_L, oracle="py:halvaro_gen/world/energy_esg/truth.py::esg_truth")
def assert_no_double_count(L: pd.DataFrame) -> bool:
    """Use this when you need to confirm that a frame of emission lines holds no original together with the restated line that replaces it, before you total it.

    Raises FrameError when the frame holds both an original line and the restated line that replaces it (a total over it counts the change twice, T1). Returns True otherwise. Frames that are the current basis, the lines as first booked or an as-of view pass; the unfiltered table does not.

    Args:
        L: The energy-esg.emission_line table, or a basis taken from it, with the columns le_key, period, scope, category, line_no, is_superseded, restated_from_period and supersedes_line_no.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        True when no original is in the frame together with the restated line that replaces it.

    Raises:
        FrameError: an original line is in the frame together with the restated line that replaces it (the message names the years).
        FrameError: a column is missing, is_superseded has nulls, or the line key is used twice.
        FrameError: a restated line has no supersedes_line_no.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import assert_no_double_count
        >>> ctx = Context(stage="month12", role="analyst")
        >>> L = pd.DataFrame({
        ...     "le_key": ["LE-900001", "LE-900001"], "period": ["2025-03", "2025-03"], "scope": [1, 1], "category": ["gas", "gas"],
        ...     "line_no": [1, 2], "kgco2e": [200.0, 190.0], "quantity": [1000.0, 1000.0], "efac_key": ["EF-900001", "EF-900002"],
        ...     "method": [None, None], "ghg_category": ["1", "1"], "restated_from_period": [None, "2026-01"],
        ...     "supersedes_line_no": [None, 1], "is_superseded": [True, False]})
        >>> assert_no_double_count(L[L["line_no"] == 2], context=ctx)
        True
    """
    L = _lines(L, base=_LINK_COLS)
    _links(L, full=False)
    new = L[L["restated_from_period"].notna() & L["supersedes_line_no"].notna()]
    replaced = pd.MultiIndex.from_arrays([new["le_key"], new["period"], new["scope"], new["category"], _num(new["supersedes_line_no"])])
    hit = pd.MultiIndex.from_arrays([L["le_key"], L["period"], L["scope"], L["category"], _num(L["line_no"])]).isin(replaced)
    if hit.any():
        years = sorted(set(L.loc[hit, "period"].astype(str).str[:4]))
        raise FrameError(f"{int(hit.sum())} original lines are in the frame together with the restated lines that replace them (years {', '.join(years)}); use current_basis or as_first_booked")
    return True


@staged(sources=(*_L, "energy-esg.emission_line.quantity", "energy-esg.emission_line.efac_key", "energy-esg.emission_line.method", "energy-esg.emission_line.ref_type", "energy-esg.emission_line.ref_key",
                 "energy-esg.emission_factor.efac_key", "energy-esg.emission_factor.kgco2e_per_unit", "energy-esg.emission_factor.valid_from", "energy-esg.emission_factor.valid_to"),
        oracle="py:tests/test_energy_esg.py::test_keys_valid_and_foreign_keys")
def validate_lines(L: pd.DataFrame, F: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need the rule violations of the emission lines, such as a wrong kg value, an unknown or invalid factor or a wrong method.

    Violations (table, key, rule, detail) of the emission lines: duplicate_key, null_value, unknown_factor, value (kgco2e differs from quantity times the factor by more than 0.002 kg), period (not a month like 2025-03), link (a restated line has no supersedes_line_no), category (ghg_category does not belong to the scope: 1, 2 or 3.x), factor_validity (the factor is not valid on the first day of the period, unless the line is restated), restated_factor (a restated line has a factor that was already valid in its period, so nothing was restated), method (scope 2 has location or market, other scopes none) and ref_prefix (the reference type decides the key prefix: MTR, PRJ, SITE, SUP or LE). The key of a violation is 'le_key period scope category line_no'.

    Args:
        L: The energy-esg.emission_line table with the columns le_key, period, scope, category, line_no, kgco2e, quantity, efac_key, method, ghg_category, restated_from_period, supersedes_line_no, is_superseded, ref_type and ref_key.
        F: The energy-esg.emission_factor table with the columns efac_key, kgco2e_per_unit, valid_from and valid_to (one row per efac_key).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A frame with the columns table, key, rule and detail, one row per violation; empty when the lines pass.

    Raises:
        FrameError: L or F lacks a required column, or F has more than one row for an efac_key.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import validate_lines
        >>> ctx = Context(stage="month12", role="analyst")
        >>> L = pd.DataFrame({
        ...     "le_key": ["LE-900001", "LE-900001"], "period": ["2025-03", "2025-03"], "scope": [1, 1], "category": ["gas", "gas"],
        ...     "line_no": [1, 2], "kgco2e": [200.0, 190.0], "quantity": [1000.0, 1000.0], "efac_key": ["EF-900001", "EF-900002"],
        ...     "method": [None, None], "ghg_category": ["1", "1"], "restated_from_period": [None, "2026-01"],
        ...     "supersedes_line_no": [None, 1], "is_superseded": [True, False]})
        >>> F = pd.DataFrame({
        ...     "efac_key": ["EF-900001", "EF-900002"], "category": ["gas", "gas"], "carrier": ["natural_gas", "natural_gas"],
        ...     "region": ["DE", "DE"], "method": [None, None], "kgco2e_per_unit": [0.2, 0.19],
        ...     "valid_from": ["2024-01-01", "2026-01-01"], "valid_to": ["2025-12-31", None], "factor_set": ["FS-A", "FS-B"],
        ...     "synthetic": [True, True], "verify_note": ["VERIFY first", "VERIFY second"]})
        >>> L["ref_type"], L["ref_key"] = "SITE", "SITE-900001"
        >>> validate_lines(L, F, context=ctx).shape[0]
        0
        >>> bad = L.assign(kgco2e=[200.0, 100.0])
        >>> validate_lines(bad, F, context=ctx)[["key", "rule"]].to_dict("records")
        [{'key': 'LE-900001 2025-03 1 gas 2', 'rule': 'value'}]
    """
    _need(L, [*_LINE_COLS, "ghg_category", "ref_type", "ref_key"], "energy-esg.emission_line")
    _need(F, ["efac_key", "kgco2e_per_unit", "valid_from", "valid_to"], "energy-esg.emission_factor")
    if F["efac_key"].duplicated().any():
        raise FrameError("energy-esg.emission_factor has more than one row for an efac_key")
    f = F.set_index("efac_key")
    key = L["le_key"].astype(str) + " " + L["period"].astype(str) + " " + L["scope"].astype(str) + " " + L["category"].astype(str) + " " + L["line_no"].astype(str)
    rows: list[tuple[str, str, str, str]] = []
    add = lambda mask, rule, detail: rows.extend(("energy-esg.emission_line", k, rule, detail) for k in key[mask])
    add(L.duplicated(["le_key", "period", "scope", "category", "line_no"], keep="first"), "duplicate_key", "line key used twice")
    nulls = L[["kgco2e", "quantity", "efac_key"]].isna().any(axis=1)
    add(nulls, "null_value", "kgco2e, quantity or efac_key is null")
    known = L["efac_key"].isin(f.index)
    add(~known & L["efac_key"].notna(), "unknown_factor", "efac_key is not in the factor table")
    ok = known & ~nulls
    rate = L["efac_key"].map(f["kgco2e_per_unit"]).astype(float)
    add(ok & ((L["quantity"] * rate - L["kgco2e"]).abs() > _TOL_KG + 1e-9), "value", "kgco2e differs from quantity times the factor")
    start = pd.to_datetime(L["period"].astype(str) + "-01", errors="coerce")
    add(start.isna(), "period", "period is not a month like 2025-03")
    add(L[["le_key", "category"]].isna().any(axis=1), "null_value", "le_key or category is null")
    add(L["restated_from_period"].notna() & L["supersedes_line_no"].isna(), "link", "a restated line has no supersedes_line_no")
    scope = L["scope"]
    gc = L["ghg_category"].astype(object)
    good = ((scope == 1) & (gc == "1")) | ((scope == 2) & (gc == "2")) | ((scope == 3) & gc.map(lambda v: isinstance(v, str) and v.startswith("3.")))
    add(~good, "category", "ghg_category does not belong to the scope (1, 2, 3.x)")
    vf = pd.to_datetime(L["efac_key"].map(f["valid_from"]), errors="coerce")
    vt = pd.to_datetime(L["efac_key"].map(f["valid_to"]), errors="coerce")
    outside = (start < vf) | (vt.notna() & (start > vt))
    add(ok & L["restated_from_period"].isna() & outside, "factor_validity", "the factor is not valid on the first day of the period and the line is not restated")
    add(ok & L["restated_from_period"].notna() & ~outside & start.notna(), "restated_factor", "a restated line has a factor that was already valid in its period: nothing was restated")
    s2 = L["scope"] == 2
    add((s2 & ~L["method"].isin(["location", "market"])) | (~s2 & L["method"].notna()), "method", "scope 2 lines have location or market, other lines no method")
    prefix = {"MTR": "MTR-", "PRJ": "PRJ-", "SITE": "SITE-", "SUP": "SUP-", "LE": "LE-"}
    bad = L["ref_type"].map(prefix).isna() | ~pd.Series([isinstance(k, str) and isinstance(p, str) and k.startswith(p) for k, p in zip(L["ref_key"], L["ref_type"].map(prefix))], index=L.index)
    add(bad, "ref_prefix", "ref_key does not start with the prefix of ref_type")
    return violations.frame(rows)
