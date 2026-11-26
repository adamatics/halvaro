"""Emission factors: the family of a factor row, the factor valid on a date, the difference between two factor sets, the synthetic flag and the counted product share.

Every factor row of the estate is synthetic with a VERIFY note: results are a Provenance with status VERIFY+synthetic, never verified. `valid_to` is inclusive and null means current.
"""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd

from halvaro.core import FrameError

from ._guard import staged, unwrapped
from ._util import Provenance, _day, _days, _need, _provenance
from ._types import DateLike

_FAMILY = ["category", "carrier", "region", "method"]
_COLS = ["efac_key", "category", "carrier", "region", "method", "kgco2e_per_unit", "valid_from", "valid_to", "factor_set", "synthetic", "verify_note"]
_SOURCE = tuple(f"energy-esg.emission_factor.{c}" for c in ("efac_key", "category", "carrier", "region", "method", "kgco2e_per_unit", "valid_from", "valid_to", "factor_set", "synthetic", "verify_note"))
_PRODUCT = "purchased_goods_product_footprint"


@staged(sources=_SOURCE[:5], oracle="py:tests/test_energy_esg.py::test_factors_are_synthetic_and_dated")
def family_key(factors: pd.DataFrame) -> pd.Series:
    """Use this when you need the family of each emission factor row as one text key.

    The family of each factor row as text 'category|carrier|region|method' (a null part is '-'), with the index of the frame. Rows of one family differ by validity and factor set only.

    Args:
        factors: The energy-esg.emission_factor table with the columns category, carrier, region and method.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A Series named family_key with the text key of each row and the index of factors.

    Raises:
        FrameError: factors is not a DataFrame or lacks one of category, carrier, region and method.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import family_key
        >>> ctx = Context(stage="month12", role="analyst")
        >>> F = pd.DataFrame({
        ...     "efac_key": ["EF-900001", "EF-900002"], "category": ["gas", "gas"], "carrier": ["natural_gas", "natural_gas"],
        ...     "region": ["DE", "DE"], "method": [None, None], "kgco2e_per_unit": [0.2, 0.19],
        ...     "valid_from": ["2024-01-01", "2026-01-01"], "valid_to": ["2025-12-31", None], "factor_set": ["FS-A", "FS-B"],
        ...     "synthetic": [True, True], "verify_note": ["VERIFY first", "VERIFY second"]})
        >>> family_key(F, context=ctx).tolist()
        ['gas|natural_gas|DE|-', 'gas|natural_gas|DE|-']
    """
    _need(factors, _FAMILY, "energy-esg.emission_factor")
    parts = factors[_FAMILY].astype(object).where(factors[_FAMILY].notna(), "-")
    return pd.Series(parts["category"].astype(str) + "|" + parts["carrier"].astype(str) + "|" + parts["region"].astype(str) + "|" + parts["method"].astype(str), index=factors.index, name="family_key")


@staged(sources=_SOURCE, oracle="py:tests/test_energy_esg.py::test_every_line_uses_a_valid_factor_or_is_restated")
def factor_on(factors: pd.DataFrame, category: str, region: str, on: DateLike, *, carrier: str | None = None, method: str | None = None) -> Provenance:
    """Use this when you need the one emission factor row of a family that is valid on a date.

    The factor row of a family valid on a date (or the first day of a 'YYYY-MM' period): valid_from <= date <= valid_to, null valid_to open (valid_to is inclusive). `value` is the row as a one row frame. The family is category, region, and carrier and method where the family has them (None matches a null). No row, or two rows, valid on the date raises FrameError: a family has no gap and no overlap. Every factor row is synthetic with a VERIFY note, so the status is VERIFY+synthetic, never verified.

    Args:
        factors: The energy-esg.emission_factor table with the columns efac_key, category, carrier, region, method, kgco2e_per_unit, valid_from, valid_to, factor_set, synthetic and verify_note.
        category: The factor category, for example gas.
        region: The factor region.
        on: The day as a date, a Timestamp or ISO text, or a period 'YYYY-MM' (its first day); numbers and time zones are refused.
        carrier: The carrier of the family, or None for a family without carrier (matches a null).
        method: The method of the family, or None for a family without method (matches a null).
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A Provenance (an Envelope with factor_sets and verify_facts) whose value is the one factor row as a one row frame with all columns of factors.

    Raises:
        FrameError: factors lacks a column, on is a number, not a date or has a time zone, or valid_from or valid_to holds numbers, values that are not dates or a time zone.
        FrameError: no factor of the family is valid on the date, or more than one is (the message lists their efac_key).
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import factor_on
        >>> ctx = Context(stage="month12", role="analyst")
        >>> F = pd.DataFrame({
        ...     "efac_key": ["EF-900001", "EF-900002"], "category": ["gas", "gas"], "carrier": ["natural_gas", "natural_gas"],
        ...     "region": ["DE", "DE"], "method": [None, None], "kgco2e_per_unit": [0.2, 0.19],
        ...     "valid_from": ["2024-01-01", "2026-01-01"], "valid_to": ["2025-12-31", None], "factor_set": ["FS-A", "FS-B"],
        ...     "synthetic": [True, True], "verify_note": ["VERIFY first", "VERIFY second"]})
        >>> r = factor_on(F, "gas", "DE", "2025-06", carrier="natural_gas", context=ctx)
        >>> r.value[["efac_key", "kgco2e_per_unit"]].to_dict("records")
        [{'efac_key': 'EF-900001', 'kgco2e_per_unit': 0.2}]
        >>> r.status
        'VERIFY+synthetic'
    """
    _need(factors, _COLS, "energy-esg.emission_factor")
    d = _day(on, "on")
    f = _days(factors, ["valid_from", "valid_to"], "energy-esg.emission_factor")
    same = (f["category"] == category) & (f["region"] == region)
    same &= f["carrier"].isna() if carrier is None else (f["carrier"] == carrier)
    same &= f["method"].isna() if method is None else (f["method"] == method)
    hit = f[same & (f["valid_from"] <= d) & (f["valid_to"].isna() | (f["valid_to"] >= d))]
    if hit.empty:
        raise FrameError(f"no factor of {category}/{carrier}/{region}/{method} is valid on {d.date()}")
    if len(hit) > 1:
        raise FrameError(f"{len(hit)} factors of {category}/{carrier}/{region}/{method} are valid on {d.date()}: {', '.join(map(str, hit['efac_key']))}")
    row = factors.iloc[np.flatnonzero((same & (f["valid_from"] <= d) & (f["valid_to"].isna() | (f["valid_to"] >= d))).to_numpy())]            # by position: the index of the frame may repeat
    return _provenance(row.reset_index(drop=True), "halvaro.esg.factors.factor_on", row, sources=_SOURCE, as_of=d.date())


def _set_rows(f: pd.DataFrame, sets: Any, what: str) -> pd.DataFrame:
    if not isinstance(sets, (str, list, tuple, set, frozenset, pd.Series)):
        raise FrameError(f"{what} must be a factor set name or a list of names, for example FS-2025 or ['FS-2025', 'FS-2023-25']")
    names = [sets] if isinstance(sets, str) else list(sets)
    if not names or not all(isinstance(n, str) for n in names):
        raise FrameError(f"{what} must be a factor set name or a list of names, for example FS-2025 or ['FS-2025', 'FS-2023-25']")
    rows = f[f["factor_set"].isin(names)].copy()
    unknown = sorted(set(names) - set(f["factor_set"]))
    if unknown:
        raise FrameError(f"{what}: factor set {unknown[0]} is not in the table")
    rows["family"] = unwrapped(family_key)(rows)
    if rows["family"].duplicated().any():
        raise FrameError(f"{what} {names} holds more than one row for the family {rows.loc[rows['family'].duplicated(), 'family'].iloc[0]}")
    return rows


@staged(sources=_SOURCE)
def factor_set_diff(factors: pd.DataFrame, old_set: str | Sequence[str], new_set: str | Sequence[str]) -> Provenance:
    """Use this when you need to compare the emission factors of two factor sets family by family.

    Per family the old value, the new value and the percent change (two decimals) between two factor sets. A set is a name or a list of names (for example ['FS-2031', 'FS-2029-31']); a family may not appear twice in one side. change_percent is null when a side is missing or the old value is 0; side is 'both', 'old_only' or 'new_only'.

    Args:
        factors: The energy-esg.emission_factor table with the columns efac_key, category, carrier, region, method, kgco2e_per_unit, valid_from, valid_to, factor_set, synthetic and verify_note.
        old_set: The old factor set, a name or a list of names.
        new_set: The new factor set, a name or a list of names.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A Provenance whose value is a frame with the columns family, category, carrier, region, method, old_value, new_value, change_percent and side, sorted by family.

    Raises:
        FrameError: factors lacks a column, a set is not a name or a list of names, or a set is not in the table.
        FrameError: one side holds more than one row for the same family.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import factor_set_diff
        >>> ctx = Context(stage="month12", role="analyst")
        >>> F = pd.DataFrame({
        ...     "efac_key": ["EF-900001", "EF-900002"], "category": ["gas", "gas"], "carrier": ["natural_gas", "natural_gas"],
        ...     "region": ["DE", "DE"], "method": [None, None], "kgco2e_per_unit": [0.2, 0.19],
        ...     "valid_from": ["2024-01-01", "2026-01-01"], "valid_to": ["2025-12-31", None], "factor_set": ["FS-A", "FS-B"],
        ...     "synthetic": [True, True], "verify_note": ["VERIFY first", "VERIFY second"]})
        >>> d = factor_set_diff(F, "FS-A", "FS-B", context=ctx)
        >>> d.value[["old_value", "new_value", "change_percent", "side"]].to_dict("records")
        [{'old_value': 0.2, 'new_value': 0.19, 'change_percent': -5.0, 'side': 'both'}]
    """
    _need(factors, _COLS, "energy-esg.emission_factor")
    old, new = _set_rows(factors, old_set, "old_set"), _set_rows(factors, new_set, "new_set")
    m = old[["family", *_FAMILY, "kgco2e_per_unit"]].rename(columns={"kgco2e_per_unit": "old_value"}).merge(
        new[["family", *_FAMILY, "kgco2e_per_unit"]].rename(columns={"kgco2e_per_unit": "new_value"}), on=["family", *_FAMILY], how="outer", indicator=True)
    m["side"] = m["_merge"].map({"both": "both", "left_only": "old_only", "right_only": "new_only"}).astype(str)
    m["old_value"], m["new_value"] = m["old_value"].astype("float64"), m["new_value"].astype("float64")
    pos = m["old_value"] > 0
    m["change_percent"] = np.where(pos & m["new_value"].notna(), np.round((m["new_value"] / m["old_value"].where(pos) - 1) * 100, 2), np.nan)
    out = m[["family", *_FAMILY, "old_value", "new_value", "change_percent", "side"]].sort_values("family").reset_index(drop=True)
    used = pd.concat([old, new])
    return _provenance(out, "halvaro.esg.factors.factor_set_diff", used, sources=_SOURCE)


@staged(sources=(*_SOURCE[:1], "energy-esg.emission_factor.synthetic", "energy-esg.emission_factor.verify_note", "energy-esg.emission_factor.factor_set"), oracle="py:halvaro_gen/world/energy_esg/truth.py::esg_truth")
def flag_synthetic(factors: pd.DataFrame) -> Provenance:
    """Use this when you need to know whether the emission factor rows are synthetic and carry a VERIFY note.

    The synthetic flag and the VERIFY note of the factor rows, as the status of the result: VERIFY+synthetic when every row is synthetic and carries a VERIFY note, never 'ok'. `value` has one row per factor row (efac_key, synthetic, verify_note); a row that is not synthetic or has no VERIFY note is listed in the warnings.

    Args:
        factors: The energy-esg.emission_factor table with the columns efac_key, synthetic, verify_note and factor_set.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        A Provenance whose value is a frame with the columns efac_key, synthetic and verify_note, one row per factor row, and whose status is VERIFY+synthetic when all rows are synthetic with a VERIFY note.

    Raises:
        FrameError: factors is not a DataFrame or lacks one of efac_key, synthetic, verify_note and factor_set.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import flag_synthetic
        >>> ctx = Context(stage="month12", role="analyst")
        >>> F = pd.DataFrame({
        ...     "efac_key": ["EF-900001", "EF-900002"], "category": ["gas", "gas"], "carrier": ["natural_gas", "natural_gas"],
        ...     "region": ["DE", "DE"], "method": [None, None], "kgco2e_per_unit": [0.2, 0.19],
        ...     "valid_from": ["2024-01-01", "2026-01-01"], "valid_to": ["2025-12-31", None], "factor_set": ["FS-A", "FS-B"],
        ...     "synthetic": [True, True], "verify_note": ["VERIFY first", "VERIFY second"]})
        >>> s = flag_synthetic(F, context=ctx)
        >>> s.status
        'VERIFY+synthetic'
        >>> s.value["efac_key"].tolist()
        ['EF-900001', 'EF-900002']
    """
    _need(factors, ["efac_key", "synthetic", "verify_note", "factor_set"], "energy-esg.emission_factor")
    rows = factors[["efac_key", "synthetic", "verify_note", "factor_set"]]
    warnings = []
    flagged = rows["synthetic"].eq(True).fillna(False).astype(bool)
    if not flagged.all():
        warnings.append(f"{int((~flagged).sum())} factor rows are not flagged synthetic")
    noted = rows["verify_note"].map(lambda n: isinstance(n, str) and "VERIFY" in n)
    if not noted.all():
        warnings.append(f"{int((~noted).sum())} factor rows have no VERIFY note")
    return _provenance(rows[["efac_key", "synthetic", "verify_note"]].reset_index(drop=True), "halvaro.esg.factors.flag_synthetic", rows, sources=_SOURCE, warnings=warnings)


@staged(sources=(_SOURCE[0], _SOURCE[1], _SOURCE[5]))
def product_basis_share(factors: pd.DataFrame) -> float:
    """Use this when you need the counted share of the product footprints for purchased goods.

    The counted share of the product footprints: kgco2e_per_unit of the one purchased_goods_product_footprint row of the table. The share is read from the table only, never from the yaml: the table is the truth. It is computed, and it must lie in (0, 1].

    Args:
        factors: The energy-esg.emission_factor table with the columns category and kgco2e_per_unit.
        context: The halvaro.core.Context of the session (stage and role); a source above its stage is refused with StageRefusal.

    Returns:
        The share as a float in (0, 1].

    Raises:
        FrameError: factors lacks category or kgco2e_per_unit, has zero or several purchased_goods_product_footprint rows, or the share is outside (0, 1].
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.esg import product_basis_share
        >>> ctx = Context(stage="month12", role="analyst")
        >>> F = pd.DataFrame({"category": ["gas", "purchased_goods_product_footprint"], "kgco2e_per_unit": [0.2, 0.25]})
        >>> product_basis_share(F, context=ctx)
        0.25
    """
    _need(factors, ["category", "kgco2e_per_unit"], "energy-esg.emission_factor")
    rows = factors[factors["category"] == _PRODUCT]
    if len(rows) != 1:
        raise FrameError(f"energy-esg.emission_factor has {len(rows)} rows of {_PRODUCT}; one is expected")
    v = float(rows["kgco2e_per_unit"].iloc[0])
    if not 0 < v <= 1:
        raise FrameError(f"the counted share {v} is outside (0, 1]")
    return v
