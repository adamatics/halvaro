"""Group consolidation (plan 5.8): the eliminations checked and tied to the group trial balance, intercompany pairs, the group trial balance rebuilt from the entity books, the translation rounding.

The EUR rate is the core fact world.fx_eur_dkk_fixed. Tolerances and the required elimination types are keywords marked PROPOSED (config/finance-reporting.yaml consolidation, fact needed).
"""
from __future__ import annotations

from typing import Any, cast

import numpy as np
import pandas as pd

from halvaro.core import Envelope, FrameError, fact, make_envelope, violations

from ._guard import staged
from ._util import _cents, _need

_FX = "world.fx_eur_dkk_fixed"
_REQUIRED = ("investment", "ic_loan", "ic_trade_revenue")       # PROPOSED: entry types the generator test requires
_CE = ("fiscal_year", "period", "entry_no", "entry_type", "basis", "debit_le_key", "debit_gl_key", "credit_le_key", "credit_gl_key", "amount_dkk", "difference_dkk")


def _round_half_away(v: np.ndarray) -> np.ndarray:
    """Cents, ties away from zero. The product of a balance and a rate carries float noise far above 1e-9 once the amount is large (143684.25 times 7.46 is 1071884.5049999999 in floats, an exact tie of 1071884.505),
    so the tie is decided after rounding the cent value to six decimals, as ledger.py does; balances in cents and rates of up to four decimals never produce a non tie that close."""
    return np.sign(v) * np.floor(np.round(np.abs(v) * 100, 6) + 0.5) / 100


def _rate(rate: Any) -> tuple[float, list[Any]]:
    if rate is None:
        f = fact(_FX)
        return float(f.value), [f]
    if isinstance(rate, bool) or not isinstance(rate, (int, float, np.number)) or not np.isfinite(rate) or rate <= 0:
        raise FrameError("eur_rate must be a positive number")
    return float(rate), []


def _elim_by_gl(ce: pd.DataFrame) -> pd.Series:
    """Net elimination of the movement per period and account from the entries: debit side positive, credit side negative, amounts in DKK. Entries on the opening balance basis (investment and loan
    principal) act on the opening balances, not on a period's movement, and are left out."""
    ce = ce[ce["basis"] != "opening_balance"]
    d = pd.DataFrame({"period": ce["period"], "gl_key": ce["debit_gl_key"], "v": ce["amount_dkk"].astype(float)})
    c = pd.DataFrame({"period": ce["period"], "gl_key": ce["credit_gl_key"], "v": -ce["amount_dkk"].astype(float)})
    return pd.concat([d, c]).groupby(["period", "gl_key"])["v"].sum()


@staged(sources=tuple(f"finance-reporting.consolidation_entry.{c}" for c in _CE) + ("finance-reporting.group_trial_balance.period", "finance-reporting.group_trial_balance.elimination_dkk"),
        oracle="py:tests/test_finance_reporting.py::test_consolidation_entries_balance_and_match")
def eliminations(consolidation_entry: pd.DataFrame, group_trial_balance: pd.DataFrame | None = None, *, tolerance: float = 0.011, period_tolerance: float = 0.5,
                 required_types: tuple[str, ...] = _REQUIRED) -> pd.DataFrame:
    """Use this when you need to check the consolidation entries of the group: that they are positive, balanced, between two different accounts, complete by type, and zero over a period.

    Rule: every violation is listed. non_positive_amount: an amount that is not above zero. entry_unbalanced: a stored difference above tolerance. same_account: an entry that debits and credits the same account of the same entity. entry_type_missing: a type of required_types without an entry (PROPOSED investment, ic_loan, ic_trade_revenue). period_not_zero: with the group trial balance, the eliminations of a period that do not sum to zero within period_tolerance. The entries are not recomputed from the books of the entities.

    Args:
        consolidation_entry: Frame finance-reporting.consolidation_entry with fiscal_year, period, entry_no, entry_type, basis, debit_le_key, debit_gl_key, credit_le_key, credit_gl_key, amount_dkk and difference_dkk, one row per year, period and entry number.
        group_trial_balance: Optional frame with period, gl_key and elimination_dkk; when given, the eliminations of each period are checked to sum to zero.
        tolerance: Largest accepted stored difference of an entry in DKK (default 0.011).
        period_tolerance: Largest accepted sum of the eliminations of a period in DKK (default 0.5).
        required_types: The entry types that must each have an entry (default investment, ic_loan, ic_trade_revenue, PROPOSED).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame of violations with the columns table, key, rule and detail; empty when the entries are clean.

    Raises:
        FrameError: a column is missing, an entry number is repeated within a year and period, or a tolerance is negative or not a number.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import eliminations
        >>> ctx = Context(stage="month12", role="analyst")
        >>> entry = pd.DataFrame([{"fiscal_year": 2026, "period": "2026-03", "entry_no": 1, "entry_type": "investment", "basis": "movement", "debit_le_key": "LE-01", "debit_gl_key": "GL-8000",
        ...                       "credit_le_key": "LE-02", "credit_gl_key": "GL-8100", "amount_dkk": 100.0, "difference_dkk": 0.0}])
        >>> eliminations(entry, context=ctx)[["key", "rule"]].to_dict("records")
        [{'key': 'ic_loan', 'rule': 'entry_type_missing'}, {'key': 'ic_trade_revenue', 'rule': 'entry_type_missing'}]
        >>> eliminations(entry.assign(difference_dkk=5.0), required_types=("investment",), context=ctx)[["key", "rule"]].to_dict("records")
        [{'key': '2026-03 #1', 'rule': 'entry_unbalanced'}]
    """
    _need(consolidation_entry, list(_CE), "finance-reporting.consolidation_entry")
    if consolidation_entry.duplicated(["fiscal_year", "period", "entry_no"]).any():
        raise FrameError("finance-reporting.consolidation_entry has more than one row for a year, period and entry number")
    for name, v in (("tolerance", tolerance), ("period_tolerance", period_tolerance)):
        if isinstance(v, bool) or not isinstance(v, (int, float, np.number)) or not np.isfinite(v) or v < 0:
            raise FrameError(f"{name} must be zero or more")
    ce, rows = consolidation_entry, []
    for r in ce[ce["amount_dkk"] <= 0].itertuples():
        rows.append(("finance-reporting.consolidation_entry", f"{r.period} #{r.entry_no}", "non_positive_amount", f"amount {r.amount_dkk}"))
    for r in ce[ce["difference_dkk"].abs() > tolerance + 1e-9].itertuples():
        rows.append(("finance-reporting.consolidation_entry", f"{r.period} #{r.entry_no}", "entry_unbalanced", f"difference {r.difference_dkk}"))
    for r in ce[(ce["debit_gl_key"] == ce["credit_gl_key"]) & (ce["debit_le_key"] == ce["credit_le_key"])].itertuples():
        rows.append(("finance-reporting.consolidation_entry", f"{r.period} #{r.entry_no}", "same_account", f"{r.debit_le_key} {r.debit_gl_key} on both sides"))
    for t in required_types:
        if t not in set(ce["entry_type"]):
            rows.append(("finance-reporting.consolidation_entry", t, "entry_type_missing", f"no entry of type {t}"))
    if group_trial_balance is not None:
        _need(group_trial_balance, ["period", "gl_key", "elimination_dkk"], "finance-reporting.group_trial_balance")
        for p, x in group_trial_balance.groupby("period"):
            if abs(x["elimination_dkk"].sum()) >= period_tolerance:
                rows.append(("finance-reporting.group_trial_balance", cast(str, p), "period_not_zero", f"eliminations sum to {x['elimination_dkk'].sum():.2f}"))
    return violations.frame(rows)


@staged(sources=("finance-reporting.intercompany_match.ic_ref", "finance-reporting.intercompany_match.amount_le01_dkk", "finance-reporting.intercompany_match.amount_le02_dkk",
                 "finance-reporting.intercompany_match.amount_le02_eur", "finance-reporting.intercompany_match.difference_dkk", "finance-reporting.intercompany_match.status"),
        facts=(_FX,), oracle="py:tests/test_finance_reporting.py::test_consolidation_entries_balance_and_match")
def intercompany_match(match: pd.DataFrame, *, tolerance_dkk: float = 1.0, eur_rate: float | None = None) -> Envelope:
    """Use this when you need the intercompany pairs of the two legal entities recomputed and compared with what is stored.

    Rule: difference_dkk is the amount booked by LE-01 less the amount booked by LE-02 in DKK. status is matched when the difference is within tolerance_dkk (PROPOSED 1.0, the group tolerance of the plan) and difference otherwise. fx_ok is true when the EUR amount of LE-02 at the fixed rate is within 0.011 of its DKK amount. agrees is true when the recomputed status and difference equal the stored ones.

    Args:
        match: Frame finance-reporting.intercompany_match with ic_ref, kind, period, amount_le01_dkk, amount_le02_dkk, amount_le02_eur, difference_dkk and status, one row per ic_ref.
        tolerance_dkk: Largest difference in DKK that still counts as matched (default 1.0, PROPOSED).
        eur_rate: The EUR to DKK rate; without it the fixed rate of the fact world.fx_eur_dkk_fixed is used and listed in the envelope.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        Envelope whose value is a DataFrame with ic_ref, kind, period, amount_le01_dkk, amount_le02_dkk, difference_dkk, status, stored_status, fx_ok and agrees.

    Raises:
        FrameError: a column is missing, an ic_ref is empty or repeated, tolerance_dkk is negative or not a number, or eur_rate is not a positive number.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import intercompany_match
        >>> ctx = Context(stage="month12", role="analyst")
        >>> match = pd.DataFrame({"ic_ref": ["IC-1", "IC-2"], "kind": ["loan", "trade"], "period": ["2026-03"] * 2, "amount_le01_dkk": [1000.0, 500.0],
        ...                       "amount_le02_dkk": [1000.0, 498.0], "amount_le02_eur": [100.0, 49.8], "difference_dkk": [0.0, 2.0], "status": ["matched", "difference"]})
        >>> result = intercompany_match(match, eur_rate=10.0, context=ctx)
        >>> result.value[["ic_ref", "difference_dkk", "status", "fx_ok", "agrees"]].to_dict("records")
        [{'ic_ref': 'IC-1', 'difference_dkk': 0.0, 'status': 'matched', 'fx_ok': True, 'agrees': True}, {'ic_ref': 'IC-2', 'difference_dkk': 2.0, 'status': 'difference', 'fx_ok': True, 'agrees': True}]
    """
    _need(match, ["ic_ref", "kind", "period", "amount_le01_dkk", "amount_le02_dkk", "amount_le02_eur", "difference_dkk", "status"], "finance-reporting.intercompany_match")
    if match["ic_ref"].duplicated().any() or match["ic_ref"].isna().any():
        raise FrameError("finance-reporting.intercompany_match needs one row per ic_ref")
    if isinstance(tolerance_dkk, bool) or not isinstance(tolerance_dkk, (int, float, np.number)) or not np.isfinite(tolerance_dkk) or tolerance_dkk < 0:
        raise FrameError("tolerance_dkk must be zero or more")
    rate, facts = _rate(eur_rate)
    a, b = match["amount_le01_dkk"].astype(float), match["amount_le02_dkk"].astype(float)
    diff = (a - b).round(2)
    out = pd.DataFrame({"ic_ref": match["ic_ref"], "kind": match["kind"], "period": match["period"], "amount_le01_dkk": a, "amount_le02_dkk": b, "difference_dkk": diff,
                        "status": np.where(diff.abs() <= tolerance_dkk + 1e-9, "matched", "difference"), "stored_status": match["status"]})
    out["fx_ok"] = ((cast(Any, _round_half_away(match["amount_le02_eur"].astype(float).to_numpy() * rate)) - b).abs() <= 0.011).to_numpy()
    out["agrees"] = (out["status"] == out["stored_status"]) & ((out["difference_dkk"] - match["difference_dkk"].astype(float)).abs() <= 0.011)
    return make_envelope(out.reset_index(drop=True), "halvaro.finance.consolidation.intercompany_match", facts=facts, sources=("finance-reporting.intercompany_match",))


@staged(sources=("finance.journal_line.le_key", "finance.journal_line.period", "finance.journal_line.gl_key", "finance.journal_line.amount_dkk", "finance.journal_line.source",
                 "finance-reporting.reporting_adjustment.period", "finance-reporting.reporting_adjustment.gl_key", "finance-reporting.reporting_adjustment.debit_dkk",
                 "finance-reporting.reporting_adjustment.credit_dkk"), oracle="py:tests/test_finance_reporting.py::test_group_trial_balance_balances")
def group_trial_balance(journal_line: pd.DataFrame, reporting_adjustment: pd.DataFrame, consolidation_entry: pd.DataFrame, *, opening_sources: tuple[str, ...] = ("opening",)) -> Envelope:
    """Use this when you need the movement of the group per period and account in DKK: the two entities plus the reporting adjustments plus the eliminations.

    Rule: the movement of an entity is the sum of the DKK amounts of its journal lines in the period, as booked (not the change of translated closing balances). Lines of the opening journals (source in opening_sources) are not movement. adjustment_dkk is debit less credit. elimination_dkk is the debit side of the entries positive and the credit side negative; entries on the opening balance basis act on opening balances and are left out. An account whose movement is eliminated to zero is listed with zero. Opening and closing balances and the year end roll are not rebuilt.

    Args:
        journal_line: Frame finance.journal_line with le_key, period, gl_key, amount_dkk and source.
        reporting_adjustment: Frame finance-reporting.reporting_adjustment with period, gl_key, debit_dkk and credit_dkk.
        consolidation_entry: Frame finance-reporting.consolidation_entry with fiscal_year, period, entry_no, entry_type, basis, debit_le_key, debit_gl_key, credit_le_key, credit_gl_key, amount_dkk and difference_dkk.
        opening_sources: The journal sources that are opening balances and not movement (default "opening").
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        Envelope whose value is a DataFrame with period, gl_key, le01_movement_dkk, le02_movement_dkk, adjustment_dkk, elimination_dkk and movement_dkk (their sum), sorted by period and account.

    Raises:
        FrameError: a column is missing, an amount_dkk is null, or the lines name an entity other than LE-01 and LE-02.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import group_trial_balance
        >>> ctx = Context(stage="month12", role="analyst")
        >>> lines = pd.DataFrame({"le_key": ["LE-01", "LE-02"], "period": ["2026-03"] * 2, "gl_key": ["GL-8000"] * 2, "amount_dkk": [100.0, -40.0], "source": ["manual"] * 2})
        >>> adjustment = pd.DataFrame({"period": ["2026-03"], "gl_key": ["GL-8000"], "debit_dkk": [10.0], "credit_dkk": [0.0]})
        >>> entry = pd.DataFrame([{"fiscal_year": 2026, "period": "2026-03", "entry_no": 1, "entry_type": "investment", "basis": "movement", "debit_le_key": "LE-01", "debit_gl_key": "GL-8000",
        ...                       "credit_le_key": "LE-02", "credit_gl_key": "GL-8100", "amount_dkk": 100.0, "difference_dkk": 0.0}])
        >>> group_trial_balance(lines, adjustment, entry, context=ctx).value[["gl_key", "adjustment_dkk", "elimination_dkk", "movement_dkk"]].to_dict("records")
        [{'gl_key': 'GL-8000', 'adjustment_dkk': 10.0, 'elimination_dkk': 100.0, 'movement_dkk': 170.0}, {'gl_key': 'GL-8100', 'adjustment_dkk': 0.0, 'elimination_dkk': -100.0, 'movement_dkk': -100.0}]
    """
    _need(journal_line, ["le_key", "period", "gl_key", "amount_dkk", "source"], "finance.journal_line")
    _need(reporting_adjustment, ["period", "gl_key", "debit_dkk", "credit_dkk"], "finance-reporting.reporting_adjustment")
    _need(consolidation_entry, list(_CE), "finance-reporting.consolidation_entry")
    x = journal_line[~journal_line["source"].astype(str).isin(list(opening_sources))]
    if x["amount_dkk"].isna().any():
        raise FrameError("finance.journal_line has a null amount_dkk")
    tb = pd.DataFrame({"period": x["period"].astype(str).to_numpy(), "gl_key": x["gl_key"].astype(str).to_numpy(), "le": x["le_key"].astype(str).to_numpy(), "v": _cents(x["amount_dkk"]) / 100.0})
    ent = cast(Any, tb.groupby(["period", "gl_key", "le"])["v"].sum()).unstack("le", fill_value=0.0)
    ent = ent.rename(columns={c: f"{c.lower().replace('-', '')}_movement_dkk" for c in ent.columns})
    for c in ("le01_movement_dkk", "le02_movement_dkk"):
        if c not in ent.columns:
            ent[c] = 0.0
    other = [c for c in ent.columns if c not in ("le01_movement_dkk", "le02_movement_dkk")]
    if other:
        raise FrameError(f"entities beyond LE-01 and LE-02 in finance.journal_line: {other}")
    adj = (reporting_adjustment.assign(v=reporting_adjustment["debit_dkk"].astype(float) - reporting_adjustment["credit_dkk"].astype(float))).groupby(["period", "gl_key"])["v"].sum().rename("adjustment_dkk")
    el = _elim_by_gl(consolidation_entry).rename("elimination_dkk")
    out = pd.concat([ent[["le01_movement_dkk", "le02_movement_dkk"]], adj, el], axis=1).fillna(0.0).round(2)
    out["movement_dkk"] = (out["le01_movement_dkk"] + out["le02_movement_dkk"] + out["adjustment_dkk"] + out["elimination_dkk"]).round(2)
    out = out.reset_index().sort_values(["period", "gl_key"]).reset_index(drop=True)
    return make_envelope(out, "halvaro.finance.consolidation.group_trial_balance", facts=[], sources=("finance.journal_line", "finance-reporting.reporting_adjustment", "finance-reporting.consolidation_entry"))


@staged(sources=("finance.trial_balance.le_key", "finance.trial_balance.period", "finance.trial_balance.gl_key", "finance.trial_balance.closing_balance", "finance.trial_balance.currency",
                 "finance.trial_balance.closing_balance_dkk"), facts=(_FX,), oracle="py:repo_tests/test_oracle_consolidation_release.py::test_oracle_translation_check_baseline_per_period_recomputed_with_exact_decimals")
def translation_check(trial_balance: pd.DataFrame, *, month: int = 12, rate_tolerance: float = 0.001, eur_rate: float | None = None) -> Envelope:
    """Use this when you check the rounding of the line by line EUR to DKK translation of a trial balance at each fiscal year end.

    Rule: per period of the chosen month, the stored DKK closing balance of the EUR lines is compared with the closing balance times the fixed rate rounded to the cent (half away from zero). At a fixed rate only cent rounding is left, so the difference is the stored sum less the recomputed sum. A period whose EUR lines (balance above 1 in absolute value) are translated at an implied rate (sum of DKK over sum of EUR, absolute values) that differs from the fixed rate by more than rate_tolerance is an error, because a translation difference would arise.

    Args:
        trial_balance: Frame finance.trial_balance with le_key, period (text like 2026-12), gl_key, closing_balance, currency and closing_balance_dkk.
        month: The month number (1 to 12) that ends the fiscal year. Default 12 (proposed).
        rate_tolerance: Largest accepted gap between the implied rate and the fixed rate. Default 0.001 (proposed).
        eur_rate: The EUR to DKK rate to test against; None takes the fixed rate of the core fact world.fx_eur_dkk_fixed. Optional.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        Envelope whose value is a DataFrame with period, n_lines, sum_dkk, sum_recomputed_dkk, rounding_dkk (stored less recomputed) and max_line_rounding_dkk, one row per period of the month; empty when no EUR line is in that month.

    Raises:
        FrameError: a column is missing, month is not a whole number from 1 to 12, eur_rate is not a positive number, or the EUR lines of a period are translated at a rate that differs from the fixed rate by more than rate_tolerance.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import translation_check
        >>> ctx = Context(stage="month12", role="analyst")
        >>> tb = pd.DataFrame({"le_key": ["LE-02"], "period": ["2026-12"], "gl_key": ["GL-1"], "closing_balance": [100.0], "currency": ["EUR"], "closing_balance_dkk": [750.01]})
        >>> translation_check(tb, eur_rate=7.5, context=ctx).value[["period", "n_lines", "rounding_dkk"]].values.tolist()
        [['2026-12', 1, 0.01]]
        >>> translation_check(tb, month=13, eur_rate=7.5, context=ctx)
        Traceback (most recent call last):
        ...
        halvaro.core.errors.FrameError: month is a whole month number from 1 to 12
    """
    _need(trial_balance, ["le_key", "period", "gl_key", "closing_balance", "currency", "closing_balance_dkk"], "finance.trial_balance")
    if isinstance(month, bool) or not isinstance(month, int) or not 1 <= month <= 12:
        raise FrameError("month is a whole month number from 1 to 12")
    rate, facts = _rate(eur_rate)
    x = trial_balance[(trial_balance["currency"] == "EUR") & (trial_balance["period"].astype(str).str[5:7] == f"{month:02d}")]
    bal = x["closing_balance"].astype(float).to_numpy()
    sd = x["closing_balance_dkk"].astype(float).to_numpy()
    rec = _round_half_away(bal * rate)
    d = pd.DataFrame({"period": x["period"].astype(str).to_numpy(), "sd": sd, "rec": rec, "ad": np.abs(sd - rec)})
    g = d.groupby("period").agg(n_lines=("sd", "size"), sum_dkk=("sd", "sum"), sum_recomputed_dkk=("rec", "sum"), max_line_rounding_dkk=("ad", "max")).reset_index()
    g["rounding_dkk"] = (g["sum_dkk"] - g["sum_recomputed_dkk"]).round(2)
    big = np.abs(bal) > 1.0
    for per, ix in d[big].groupby("period").groups.items():
        pos = d.index.get_indexer(ix)
        implied = float(cast(Any, np.abs(sd[pos]).sum()) / np.abs(bal[pos]).sum())
        if abs(implied - rate) > rate_tolerance:
            raise FrameError(f"the EUR lines of {per} are translated at {implied:.4f}, not the fixed rate {rate}; a translation difference would arise")
    g[["sum_dkk", "sum_recomputed_dkk", "max_line_rounding_dkk"]] = g[["sum_dkk", "sum_recomputed_dkk", "max_line_rounding_dkk"]].round(2)
    return make_envelope(g[["period", "n_lines", "sum_dkk", "sum_recomputed_dkk", "rounding_dkk", "max_line_rounding_dkk"]], "halvaro.finance.consolidation.translation_check", facts=facts, sources=("finance.trial_balance",))
