"""Ledger: presentation sign, DKK conversion, the trial balance rebuilt from the lines, journal integrity, the retained earnings roll, manual journals and statutory lines.

Signs are debit positive in the source tables. Amounts are in the entity currency; DKK goes through core `convert` (fixed booking rates) or a daily rate frame, never mixed in one sum.
A function that reads an amount refuses a null (the ledger has none); a source column that is missing raises FrameError and names the column.
"""
from __future__ import annotations

from typing import Any, cast

import numpy as np
import pandas as pd

from halvaro.core import BasisError, Envelope, FrameError, convert, fact, make_envelope, violations

from ._guard import staged
from ._util import _cents, _need, _round_half_away

_FY_START = "fin.bookkeeping.fiscal_year_start_month"
_NUMBERING = "fin.bookkeeping.journal_numbering"
_FX_FACTS = ("world.fx_eur_dkk_fixed", "world.fx_sek_dkk_fixed")
_RESIDUAL_CENTS_PER_LINE = 0.5            # tie-out T16: the residual of a journal is at most half a cent per other line, in cents
_KEY = ["le_key", "journal_no"]
_SIGN = {"debit": 1, "credit": -1}


def _fiscal_year(period: pd.Series, start_month: int) -> pd.Series:
    """Fiscal year of 'YYYY-MM' periods: the calendar year when the month is on or after the start month, else the year before."""
    year, month = period.str[:4].astype(int), period.str[5:7].astype(int)
    return year.where(month >= start_month, year - 1)


def _fy_start() -> tuple[int, Any]:
    f = fact(_FY_START)
    return int(f.value), f


@staged(sources=("finance.gl_account.gl_key", "finance.gl_account.normal_balance"), oracle="py:halvaro_gen/world/finance/checks.py::journals_balance")
def to_natural_sign(frame: pd.DataFrame, gl_account: pd.DataFrame, column: str = "amount", gl_column: str = "gl_key") -> pd.Series:
    """Use this when a ledger column is debit positive and you need it in the sign people read: revenue and liabilities positive.

    Rule: the amount of a line on a credit normal account is multiplied by minus one, a line on a debit normal account is kept. A zero stays zero (never minus zero).

    Args:
        frame: Frame with the amount column and the account column.
        gl_account: Frame finance.gl_account with gl_key and normal_balance (debit or credit), one row per account.
        column: Name of the amount column. Default "amount".
        gl_column: Name of the account column. Default "gl_key".
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.Series named like the amount column, on the index of the frame.

    Raises:
        FrameError: a column is missing, gl_account has an account twice or a normal_balance that is neither debit nor credit, or a row names an account that is not in gl_account.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import to_natural_sign
        >>> ctx = Context(stage="month12", role="analyst")
        >>> accounts = pd.DataFrame({"gl_key": ["GL-1", "GL-2"], "normal_balance": ["debit", "credit"]})
        >>> lines = pd.DataFrame({"gl_key": ["GL-1", "GL-2"], "amount": [100.0, -40.0]})
        >>> to_natural_sign(lines, accounts, context=ctx).tolist()
        [100.0, 40.0]
    """
    _need(frame, [column, gl_column], "ledger")
    _need(gl_account, ["gl_key", "normal_balance"], "finance.gl_account")
    if gl_account["gl_key"].duplicated().any():
        raise FrameError("finance.gl_account has duplicate gl_key values")
    sign = gl_account.set_index("gl_key")["normal_balance"].astype(object).map(_SIGN)
    if sign.isna().any():
        raise FrameError(f"finance.gl_account has accounts whose normal_balance is neither debit nor credit (for example {sign.index[sign.isna()][0]})")
    s = frame[gl_column].astype(object).map(sign)
    if s.isna().any():
        raise FrameError(f"{int(s.isna().sum())} rows name an account that is not in finance.gl_account (for example {frame.loc[s.isna(), gl_column].iloc[0]})")
    return (frame[column] * s + 0.0).rename(column)               # + 0.0: a zero on a credit account is 0.0, not -0.0


@staged(sources=("finance.fx_rate.currency", "finance.fx_rate.rate", "finance.fx_rate.booking_rate", "finance.fx_rate.rate_date"), facts=("world.fx_eur_dkk_fixed", "world.fx_sek_dkk_fixed"),
        oracle="py:halvaro_gen/world/finance/core.py::conv")
def dkk_amount(amount: pd.Series, currency: pd.Series, *, basis: str, fx_rate: pd.DataFrame | None = None, on: pd.Series | None = None, group: bool = False) -> pd.Series:
    """Use this when you need amounts in DKK to the cent: on the booking basis with the fixed rates of core, or on the daily basis with the latest rate on or before each date.

    Rule: rounding is half away from zero on the cent. The daily basis needs one date per amount and a rate frame without duplicate (currency, rate_date), and is refused for group statements. A currency without a rate is an error.

    Args:
        amount: The amounts.
        currency: The currency of each amount, same length, no nulls.
        basis: "booking" or "daily".
        fx_rate: Frame finance.fx_rate; on the booking basis it must agree with core for the currencies used. Optional.
        on: The date of each amount; required on the daily basis.
        group: True for group statements, which use the booking basis only.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.Series of the amounts in DKK, on the index of amount.

    Raises:
        BasisError: the basis is neither booking nor daily, or the daily basis is asked for a group statement.
        FrameError: amount and currency differ in length or have nulls, a rate frame lacks a column or disagrees with core, a currency has no rate, or the daily basis lacks its dates or rates.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import dkk_amount
        >>> ctx = Context(stage="month12", role="analyst")
        >>> from halvaro.core import fact
        >>> rate = fact("world.fx_eur_dkk_fixed").value
        >>> dkk_amount(pd.Series([10.0, 10.0]), pd.Series(["DKK", "EUR"]), basis="booking", context=ctx).tolist() == [10.0, round(10 * rate, 2)]
        True
        >>> dkk_amount(pd.Series([1.0]), pd.Series(["DKK"]), basis="spot", context=ctx)
        Traceback (most recent call last):
        ...
        halvaro.core.errors.BasisError: basis 'spot' is not available; use 'booking' or 'daily'
    """
    if basis not in ("booking", "daily"):
        raise BasisError(f"basis {basis!r} is not available; use 'booking' or 'daily'")
    if basis == "daily" and group:
        raise BasisError("group statements use the fixed booking rates; the daily basis is for realised FX at settlement only")
    if len(amount) != len(currency):
        raise FrameError("amount and currency must have the same length")
    if amount.isna().any() or currency.isna().any():
        raise FrameError("amount and currency must not contain nulls")
    cents = pd.Series(_cents(amount), index=amount.index)
    out = pd.Series(0.0, index=amount.index)
    if basis == "booking":
        if fx_rate is not None:
            _need(fx_rate, ["currency", "booking_rate"], "finance.fx_rate")
            rates: Any
            for cur, rates in fx_rate[fx_rate["currency"].isin(set(currency))].groupby("currency")["booking_rate"]:
                core = convert(pd.Series([100]), str(cur), "DKK", basis="booking").iloc[0] / 100
                if rates.nunique() != 1 or abs(rates.iloc[0] - core) > 1e-9:
                    raise FrameError(f"finance.fx_rate booking_rate of {cur} ({sorted(rates.unique())}) differs from the fixed booking rate of core ({core})")
        for cur in currency.unique():
            m = (currency == cur).to_numpy()
            out[m] = convert(cents[m], str(cur), "DKK", basis="booking").to_numpy() / 100
        return out
    if fx_rate is None or on is None:
        raise FrameError("basis 'daily' needs fx_rate (currency, rate_date, rate, quote_currency) and the dates `on`")
    _need(fx_rate, ["currency", "rate_date", "rate", "quote_currency"], "finance.fx_rate")
    if (fx_rate["quote_currency"] != "DKK").any():
        raise FrameError("finance.fx_rate quotes a currency other than DKK")
    if len(on) != len(amount):
        raise FrameError("`on` must have one date per amount")
    if pd.isna(on).any():
        raise FrameError(f"`on` has {int(pd.isna(on).sum())} null dates; the daily basis needs a date for every amount")
    if fx_rate.duplicated(["currency", "rate_date"]).any():
        raise FrameError("finance.fx_rate has more than one rate for a currency and date")
    rates = fx_rate.assign(rate_date=pd.to_datetime(fx_rate["rate_date"]).astype("datetime64[ns]")).sort_values("rate_date")
    left = pd.DataFrame({"currency": currency.to_numpy(), "d": pd.to_datetime(on).astype("datetime64[ns]").to_numpy(), "_i": np.arange(len(amount))}).sort_values("d")
    m = pd.merge_asof(left, rates[["currency", "rate_date", "rate"]], left_on="d", right_on="rate_date", by="currency", direction="backward").sort_values("_i")
    rate = np.where(currency.to_numpy() == "DKK", 1.0, m["rate"].to_numpy())
    if np.isnan(rate).any():
        raise FrameError(f"{int(np.isnan(rate).sum())} amounts have no daily rate on or before their date (for example currency {currency.to_numpy()[np.isnan(rate)][0]})")
    return pd.Series(_round_half_away(np.round(cents.to_numpy() * rate, 6)) / 100, index=amount.index)          # round(…, 6) removes float noise before an exact half cent


@staged(sources=("finance.journal_header.le_key", "finance.journal_header.journal_no", "finance.journal_header.source", "finance.journal_header.posting_date", "finance.journal_header.description",
                 "finance.journal_line.le_key", "finance.journal_line.journal_no", "finance.journal_line.line_no", "finance.journal_line.gl_key", "finance.journal_line.prj_key",
                 "finance.journal_line.amount", "finance.journal_line.amount_dkk", "finance.journal_line.currency"),
        oracle="py:halvaro_gen/world/finance/facts.py::build_truth")
def manual_journals(journal_header: pd.DataFrame, journal_line: pd.DataFrame, *, gl_key: str | None = None, prj_key: str | None = None) -> pd.DataFrame:
    """Use this when you need the lines of the journals that were posted by hand, optionally only those on one account or one project.

    Rule: the journals whose header source is manual; their lines with the date and description of the header.

    Args:
        journal_header: Frame finance.journal_header with le_key, journal_no, source, posting_date and description.
        journal_line: Frame finance.journal_line with le_key, journal_no, line_no, gl_key, prj_key, amount, amount_dkk and currency.
        gl_key: Keep only the lines on this account. Optional.
        prj_key: Keep only the lines on this project. Optional.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame with le_key, journal_no, line_no, posting_date, description, gl_key, prj_key, currency, amount and amount_dkk of each line.

    Raises:
        FrameError: a column is missing or a manual journal is listed twice in the header frame.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import manual_journals
        >>> ctx = Context(stage="month12", role="analyst")
        >>> header = pd.DataFrame({"le_key": ["LE-01"] * 2, "journal_no": [1, 2], "source": ["manual", "auto"], "posting_date": ["2026-03-01"] * 2, "description": ["x", "y"]})
        >>> lines = pd.DataFrame({"le_key": ["LE-01"] * 4, "journal_no": [1, 1, 2, 2], "line_no": [1, 2, 1, 2], "gl_key": ["GL-1", "GL-2"] * 2, "prj_key": [None] * 4,
        ...                       "amount": [10.0, -10.0, 5.0, -5.0], "amount_dkk": [10.0, -10.0, 5.0, -5.0], "currency": ["DKK"] * 4})
        >>> manual_journals(header, lines, context=ctx)[["journal_no", "gl_key", "amount"]].values.tolist()
        [[1, 'GL-1', 10.0], [1, 'GL-2', -10.0]]
    """
    _need(journal_header, ["le_key", "journal_no", "source", "posting_date", "description"], "finance.journal_header")
    _need(journal_line, ["le_key", "journal_no", "line_no", "gl_key", "prj_key", "amount", "amount_dkk", "currency"], "finance.journal_line")
    manual = journal_header.loc[journal_header["source"] == "manual", ["le_key", "journal_no", "posting_date", "description"]]
    if manual.duplicated(_KEY).any():
        raise FrameError("finance.journal_header has a manual journal listed twice")
    ln = journal_line
    if gl_key is not None:
        ln = ln[ln["gl_key"] == gl_key]
    if prj_key is not None:
        ln = ln[ln["prj_key"] == prj_key]
    m = ln[["le_key", "journal_no", "line_no", "gl_key", "prj_key", "currency", "amount", "amount_dkk"]].merge(manual, on=_KEY, how="inner", validate="many_to_one")
    cols = ["le_key", "journal_no", "line_no", "posting_date", "description", "gl_key", "prj_key", "currency", "amount", "amount_dkk"]
    return m[cols].sort_values(["le_key", "journal_no", "line_no"]).reset_index(drop=True)


@staged(sources=("finance.journal_line.le_key", "finance.journal_line.gl_key", "finance.journal_line.amount", "finance.journal_line.amount_dkk", "finance.journal_line.currency",
                 "finance.journal_line.period", "finance.journal_line.source", "finance.opening_balance_item.le_key", "finance.opening_balance_item.gl_key", "finance.opening_balance_item.amount",
                 "finance.opening_balance_item.amount_dkk", "finance.gl_account.gl_key", "finance.gl_account.statement"),
        facts=(_FY_START,), oracle="py:tests/test_finance.py::test_trial_balance_zero_per_entity_and_period")
def rebuild_trial_balance(journal_line: pd.DataFrame, opening_balance_item: pd.DataFrame, gl_account: pd.DataFrame, *, carry_results: bool = True,
                          retained_earnings_gl: str = "GL-3300") -> Envelope:
    """Use this when you need the trial balance per entity, period and account rebuilt from the journal lines and the opening items.

    Rule: amounts are summed in cents. The opening journals are not movements. Balance sheet accounts run from the opening items and income statement accounts restart at each fiscal year start (there are no closing journals). With carry_results the results of earlier fiscal years sit in the retained earnings account, as in the stored table; with carry_results False they are left out (the input of roll_retained_earnings). A row exists for a non-zero opening or closing balance (also in DKK) or a non-zero movement.

    Args:
        journal_line: Frame finance.journal_line with le_key, gl_key, amount, amount_dkk, currency, period (text like 2026-01) and source.
        opening_balance_item: Frame finance.opening_balance_item with le_key, gl_key, amount and amount_dkk, balance sheet accounts only.
        gl_account: Frame finance.gl_account with gl_key and statement (IS or BS), one row per account.
        carry_results: True puts the results of earlier fiscal years in the retained earnings account. Default True.
        retained_earnings_gl: The retained earnings account, which must be a balance sheet account. Default "GL-3300" (proposed, the account of the plan).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        Envelope whose value is a DataFrame in the shape of finance.trial_balance: le_key, period, gl_key, opening_balance, debit, credit, closing_balance, currency and closing_balance_dkk.

    Raises:
        FrameError: a column is missing, journal_line is empty or has a line without le_key, gl_key or period, a period is not text like 2026-01, gl_account repeats an account or has a statement other than IS or BS, the retained earnings account is not a balance sheet account, an opening item is on a result account or belongs to an entity without lines, an account is not in gl_account, or an entity has more than one currency.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import rebuild_trial_balance
        >>> ctx = Context(stage="month12", role="analyst")
        >>> lines = pd.DataFrame({"le_key": ["LE-01"] * 2, "gl_key": ["GL-1000", "GL-5100"], "amount": [100.0, -100.0], "amount_dkk": [100.0, -100.0], "currency": ["DKK"] * 2,
        ...                       "period": ["2026-01"] * 2, "source": ["manual"] * 2})
        >>> opening = pd.DataFrame({"le_key": [], "gl_key": [], "amount": [], "amount_dkk": []})
        >>> accounts = pd.DataFrame({"gl_key": ["GL-1000", "GL-3300", "GL-5100"], "statement": ["BS", "BS", "IS"]})
        >>> rebuild_trial_balance(lines, opening, accounts, context=ctx).value[["gl_key", "closing_balance"]].values.tolist()
        [['GL-1000', 100.0], ['GL-5100', -100.0]]
    """
    _need(journal_line, ["le_key", "gl_key", "amount", "amount_dkk", "currency", "period", "source"], "finance.journal_line")
    _need(opening_balance_item, ["le_key", "gl_key", "amount", "amount_dkk"], "finance.opening_balance_item")
    _need(gl_account, ["gl_key", "statement"], "finance.gl_account")
    if journal_line.empty:
        raise FrameError("finance.journal_line is empty: there is no ledger to rebuild")
    if journal_line[["le_key", "gl_key", "period"]].isna().any().any() or opening_balance_item[["le_key", "gl_key"]].isna().any().any():
        raise FrameError("finance.journal_line and finance.opening_balance_item need an le_key and a gl_key in every row, and the lines a period (a line without them would be dropped)")
    per = journal_line["period"].astype(str)
    if not per.str.fullmatch(r"\d{4}-(0[1-9]|1[0-2])").all():
        raise FrameError(f"finance.journal_line.period must be text like 2025-02, not {per[~per.str.fullmatch(r'\d{4}-(0[1-9]|1[0-2])')].iloc[0]!r}")
    if gl_account["gl_key"].duplicated().any():
        raise FrameError("finance.gl_account has more than one row for a gl_key")
    if not gl_account["statement"].isin(["IS", "BS"]).all():
        raise FrameError("finance.gl_account.statement must be IS or BS in every row")
    start, f = _fy_start()
    statement = gl_account.set_index("gl_key")["statement"]
    if statement.get(retained_earnings_gl) != "BS":
        raise FrameError(f"{retained_earnings_gl} is not a balance sheet account of finance.gl_account")
    result_items = opening_balance_item[opening_balance_item["gl_key"].map(statement).eq("IS")]
    if len(result_items):
        raise FrameError(f"{len(result_items)} opening items are on result accounts (for example {result_items['gl_key'].iloc[0]}); opening balances are balance sheet items")
    lonely = set(opening_balance_item["le_key"]) - set(journal_line["le_key"])
    if lonely:
        raise FrameError(f"entities {sorted(lonely)} have opening items but no journal lines")
    lines = journal_line[journal_line["source"] != "opening"]
    unknown = (set(lines["gl_key"]) | set(opening_balance_item["gl_key"])) - set(statement.index)
    if unknown:
        raise FrameError(f"{len(unknown)} accounts are not in finance.gl_account (for example {sorted(unknown)[0]})")
    cur = journal_line.groupby("le_key")["currency"].nunique()
    if (cur > 1).any():
        raise FrameError(f"journal lines of {', '.join(cur.index[cur > 1])} carry more than one currency; the ledger is in the entity currency")
    currency = journal_line.groupby("le_key")["currency"].first()
    c = pd.DataFrame({"le_key": lines["le_key"].to_numpy(), "gl_key": lines["gl_key"].to_numpy(), "period": lines["period"].to_numpy(), "a": _cents(lines["amount"]), "d": _cents(lines["amount_dkk"])})
    c["debit"], c["credit"] = np.where(c["a"] > 0, c["a"], 0), np.where(c["a"] < 0, -c["a"], 0)
    mv = c.groupby(["le_key", "gl_key", "period"], as_index=False).agg(net=("a", "sum"), net_dkk=("d", "sum"), debit=("debit", "sum"), credit=("credit", "sum"))
    ob = pd.DataFrame({"le_key": opening_balance_item["le_key"].to_numpy(), "gl_key": opening_balance_item["gl_key"].to_numpy(), "o": _cents(opening_balance_item["amount"]),
                       "o_dkk": _cents(opening_balance_item["amount_dkk"])}).groupby(["le_key", "gl_key"], as_index=False).sum()
    periods = journal_line.groupby("le_key")["period"].agg(["min", "max"])
    frames = []
    for le, (p0, p1) in cast(Any, periods).iterrows():
        rng = pd.period_range(p0, p1, freq="M").strftime("%Y-%m")
        pairs = pd.concat([mv.loc[mv["le_key"] == le, ["gl_key"]], ob.loc[ob["le_key"] == le, ["gl_key"]], pd.DataFrame({"gl_key": [retained_earnings_gl]})]).drop_duplicates()
        g = pairs.merge(pd.DataFrame({"period": rng}), how="cross").assign(le_key=le)
        g = g.merge(mv[mv["le_key"] == le], on=["le_key", "gl_key", "period"], how="left").merge(ob[ob["le_key"] == le], on=["le_key", "gl_key"], how="left")
        for col in ("net", "net_dkk", "debit", "credit", "o", "o_dkk"):
            g[col] = g[col].fillna(0).astype(np.int64)
        fy = _fiscal_year(pd.Series(rng), start)
        res = g[g["gl_key"].map(statement).eq("IS")].groupby("period")[["net", "net_dkk"]].sum().reindex(rng, fill_value=0)
        before = res.cumsum().shift(1, fill_value=0)                 # results of all periods before each period
        first = before.groupby(fy.to_numpy()).transform("first")      # ... before the start of its fiscal year
        g = g.merge(pd.DataFrame({"period": rng, "carry": first["net"].to_numpy(), "carry_dkk": first["net_dkk"].to_numpy()}), on="period", how="left")
        frames.append(g)
    g = pd.concat(frames, ignore_index=True).sort_values(["le_key", "gl_key", "period"])
    g["fy"] = _fiscal_year(g["period"], start)
    is_pl = g["gl_key"].map(statement).eq("IS")
    key = [g["le_key"], g["gl_key"], np.where(is_pl, g["fy"], 0)]            # income statement accounts restart each fiscal year, balance sheet accounts never
    g["cum"], g["cum_dkk"] = g.groupby(key)["net"].cumsum(), g.groupby(key)["net_dkk"].cumsum()
    base, base_dkk = np.where(is_pl, 0, g["o"]), np.where(is_pl, 0, g["o_dkk"])
    on_re = (g["gl_key"] == retained_earnings_gl).to_numpy() & carry_results
    g["closing"] = g["cum"] + base + np.where(on_re, g["carry"], 0)
    g["closing_dkk"] = g["cum_dkk"] + base_dkk + np.where(on_re, g["carry_dkk"], 0)
    g["opening"], g["opening_dkk"] = g["closing"] - g["net"], g["closing_dkk"] - g["net_dkk"]
    live = (g["opening"] != 0) | (g["debit"] != 0) | (g["credit"] != 0) | (g["closing"] != 0) | (g["closing_dkk"] != 0) | (g["opening_dkk"] != 0)
    keep = g[live]
    out = pd.DataFrame({"le_key": keep["le_key"].to_numpy(), "period": keep["period"].to_numpy(), "gl_key": keep["gl_key"].to_numpy(), "opening_balance": keep["opening"].to_numpy() / 100,
                        "debit": keep["debit"].to_numpy() / 100, "credit": keep["credit"].to_numpy() / 100, "closing_balance": keep["closing"].to_numpy() / 100,
                        "currency": keep["le_key"].map(currency).to_numpy(), "closing_balance_dkk": keep["closing_dkk"].to_numpy() / 100})
    out = out.sort_values(["le_key", "period", "gl_key"]).reset_index(drop=True)
    return make_envelope(out, "halvaro.finance.ledger.rebuild_trial_balance", facts=(f,), sources=("finance.journal_line", "finance.opening_balance_item", "finance.gl_account"))


@staged(sources=("finance.journal_header.le_key", "finance.journal_header.journal_no", "finance.journal_header.line_count", "finance.journal_line.le_key", "finance.journal_line.journal_no",
                 "finance.journal_line.line_no", "finance.journal_line.amount", "finance.journal_line.amount_dkk", "finance.journal_line.currency"),
        facts=(_NUMBERING, *_FX_FACTS), oracle="py:halvaro_gen/world/finance/checks.py::journals_balance")
def journal_integrity(journal_header: pd.DataFrame, journal_line: pd.DataFrame) -> Envelope:
    """Use this when you check the journals of the ledger: every journal has its lines, balances to the cent and is numbered without gaps.

    Rule: the checks are orphan_lines, header_without_lines, line_count, duplicate_header, duplicate_line, unbalanced_local and unbalanced_dkk (to the cent), numbering_gap (gapless per entity, as the numbering fact says), unknown_currency and dkk_conversion (the DKK amount of a line is the rounded fixed rate conversion, except one residual line per journal).

    Args:
        journal_header: Frame finance.journal_header with le_key, journal_no and line_count.
        journal_line: Frame finance.journal_line with le_key, journal_no, line_no, amount, amount_dkk and currency.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        Envelope whose value is a DataFrame of violations with the columns table, key, rule and detail; empty when the ledger is clean.

    Raises:
        FrameError: a column is missing, a journal has no le_key or journal_no, or the numbering fact names a rule other than gapless_per_entity.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import journal_integrity
        >>> ctx = Context(stage="month12", role="analyst")
        >>> header = pd.DataFrame({"le_key": ["LE-01"], "journal_no": [1], "line_count": [3]})
        >>> lines = pd.DataFrame({"le_key": ["LE-01"] * 2, "journal_no": [1, 1], "line_no": [1, 2], "amount": [10.0, -10.0], "amount_dkk": [10.0, -10.0], "currency": ["DKK"] * 2})
        >>> journal_integrity(header, lines, context=ctx).value["rule"].tolist()
        ['line_count']
    """
    _need(journal_header, ["le_key", "journal_no", "line_count"], "finance.journal_header")
    _need(journal_line, ["le_key", "journal_no", "line_no", "amount", "amount_dkk", "currency"], "finance.journal_line")
    f = fact(_NUMBERING)
    if str(f.value) != "gapless_per_entity":
        raise FrameError(f"the fact {_NUMBERING} says {f.value!r}; only gapless_per_entity is checked")
    facts = (f, *[fact(i) for i in _FX_FACTS])
    rows = []
    dup_h = journal_header.duplicated(_KEY, keep="first")
    rows += [("finance.journal_header", f"{a} {b}", "duplicate_header", "journal listed twice") for a, b in journal_header.loc[dup_h, _KEY].itertuples(index=False)]
    h = journal_header.loc[~dup_h, ["le_key", "journal_no", "line_count"]]
    ln = pd.DataFrame({"le_key": journal_line["le_key"].to_numpy(), "journal_no": journal_line["journal_no"].to_numpy(), "line_no": journal_line["line_no"].to_numpy(),
                       "c": _cents(journal_line["amount"]), "cd": _cents(journal_line["amount_dkk"]), "cur": journal_line["currency"].to_numpy()})
    dup = ln.duplicated(["le_key", "journal_no", "line_no"], keep="first")
    rows += [("finance.journal_line", f"{a} {b} line {c}", "duplicate_line", "line number used twice") for a, b, c in ln.loc[dup, ["le_key", "journal_no", "line_no"]].itertuples(index=False)]
    g = ln.groupby(_KEY).agg(n=("c", "size"), sc=("c", "sum"), sd=("cd", "sum"))
    j = h.merge(g.reset_index(), on=_KEY, how="outer", indicator=True).set_index(_KEY)
    rows += [("finance.journal_line", f"{a} {b}", "orphan_lines", f"{int(r.n)} lines without a header") for (a, b), r in cast(Any, j[j["_merge"] == "right_only"]).iterrows()]
    rows += [("finance.journal_header", f"{a} {b}", "header_without_lines", "no lines") for a, b in j.index[j["_merge"] == "left_only"]]
    both = j[j["_merge"] == "both"]
    bad = both[both["line_count"].isna() | (both["line_count"] != both["n"])]
    rows += [("finance.journal_header", f"{a} {b}", "line_count", f"header says {r.line_count}, {int(r.n)} lines") for (a, b), r in cast(Any, bad).iterrows()]
    for rule, col, label in (("unbalanced_local", "sc", "entity currency"), ("unbalanced_dkk", "sd", "DKK")):
        off = j[j[col].fillna(0) != 0]
        rows += [("finance.journal_line", f"{a} {b}", rule, f"sums to {r[col] / 100:.2f} in {label}") for (a, b), r in cast(Any, off).iterrows()]
    numbers = pd.concat([h[["le_key", "journal_no"]], g.reset_index()[["le_key", "journal_no"]]]).drop_duplicates()
    if numbers["journal_no"].isna().any() or numbers["le_key"].isna().any():
        raise FrameError("finance.journal_header and finance.journal_line need an le_key and a journal_no in every row")
    for le, x in numbers.groupby("le_key"):
        nos = np.sort(x["journal_no"].to_numpy(dtype=np.int64))
        lead = max(int(nos[0]) - 1, 0)                                          # a numbering that starts at 0 or 1 has no leading gap
        missing = lead + int((np.diff(nos) - 1).sum())
        if missing:
            first = int(1 if lead else nos[:-1][np.diff(nos) > 1][0] + 1)
            rows.append(("finance.journal_header", f"{le}", "numbering_gap", f"{missing} numbers missing, first {first}"))
    # the DKK conversion rule of T16
    expected = np.zeros(len(ln), dtype=np.int64)
    known = np.ones(len(ln), dtype=bool)
    for cur in ln["cur"].unique():
        m = (ln["cur"] == cur).to_numpy()
        try:
            expected[m] = convert(ln.loc[m, "c"], str(cur), "DKK", basis="booking").to_numpy()
        except BasisError:
            known[m] = False
    if not known.all():
        bad_cur = ln.loc[~known, ["le_key", "journal_no", "cur"]].drop_duplicates(_KEY)
        rows += [("finance.journal_line", f"{a} {b}", "unknown_currency", f"currency {c!r} has no fixed booking rate") for a, b, c in bad_cur.itertuples(index=False)]
    ln = ln[known].assign(diff=ln["cd"].to_numpy()[known] - expected[known])
    ln["off"], ln["ac"], ln["ad"], ln["dkk"] = ln["diff"] != 0, ln["c"].abs(), ln["diff"].abs(), ln["cur"] == "DKK"
    ln["maxabs"] = ln.groupby(_KEY)["ac"].transform("max")
    per = ln.groupby(_KEY).agg(n=("c", "size"), n_off=("off", "sum"), worst=("ad", "max"), dkk=("dkk", "all"))
    for (a, b) in per.index[per["n_off"] > 1]:
        rows.append(("finance.journal_line", f"{a} {b}", "dkk_conversion", "more than one line off the rounded fixed rate conversion"))
    for (a, b) in per.index[(per["n_off"] > 0) & per["dkk"]]:
        rows.append(("finance.journal_line", f"{a} {b}", "dkk_conversion", "a DKK journal has a line off its amount"))
    for (a, b) in per.index[per["worst"] > _RESIDUAL_CENTS_PER_LINE * (per["n"] - 1) + 1e-9]:
        rows.append(("finance.journal_line", f"{a} {b}", "dkk_conversion", "the residual exceeds half a cent per other line"))
    for a, b in ln.loc[ln["off"] & (ln["ac"] < ln["maxabs"]), _KEY].drop_duplicates().itertuples(index=False):
        rows.append(("finance.journal_line", f"{a} {b}", "dkk_conversion", "the residual is not on the largest line"))
    return make_envelope(violations.frame(rows), "halvaro.finance.ledger.journal_integrity", facts=facts, sources=("finance.journal_header", "finance.journal_line"))


@staged(sources=("finance.trial_balance.le_key", "finance.trial_balance.period", "finance.trial_balance.gl_key", "finance.trial_balance.opening_balance", "finance.trial_balance.closing_balance",
                 "finance.trial_balance.closing_balance_dkk", "finance.gl_account.gl_key", "finance.gl_account.statement"), facts=(_FY_START,),
        oracle="py:halvaro_gen/world/finance/views.py::trial_balance")
def roll_retained_earnings(trial_balance: pd.DataFrame, gl_account: pd.DataFrame, *, retained_earnings_gl: str = "GL-3300") -> Envelope:
    """Use this when a trial balance was built without carrying results and you need the results of completed fiscal years moved into the retained earnings account.

    Rule: the input is the output of rebuild_trial_balance with carry_results False. The result of a fiscal year is the sum of the closing balances of the income statement accounts at its last period, and it is added to the retained earnings account from the next fiscal year on. Only the retained earnings rows differ, and that account gets a row in every period that lacks one. The table must start at the first period of the ledger. A stored finance.trial_balance already carries the roll, so a table whose retained earnings opening balance jumps at a fiscal year start is refused instead of being rolled twice.

    Args:
        trial_balance: Frame with le_key, period (text like 2026-12), gl_key, opening_balance, closing_balance and closing_balance_dkk.
        gl_account: Frame finance.gl_account with gl_key and statement (IS or BS).
        retained_earnings_gl: The retained earnings account, which must be a balance sheet account. Default "GL-3300" (proposed, the account of the plan).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        Envelope whose value is the input plus rolled_opening_balance, rolled_closing_balance and rolled_closing_balance_dkk, sorted by entity, period and account.

    Raises:
        FrameError: a column is missing, the retained earnings account is not a balance sheet account of gl_account, or the retained earnings opening balance jumps at a fiscal year start (the table already carries the results).
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import roll_retained_earnings
        >>> ctx = Context(stage="month12", role="analyst")
        >>> tb = pd.DataFrame({"le_key": ["LE-01"] * 2, "period": ["2026-12", "2027-01"], "gl_key": ["GL-5100", "GL-1000"], "opening_balance": [-50.0, 0.0],
        ...                    "closing_balance": [-100.0, 0.0], "closing_balance_dkk": [-100.0, 0.0]})
        >>> accounts = pd.DataFrame({"gl_key": ["GL-1000", "GL-3300", "GL-5100"], "statement": ["BS", "BS", "IS"]})
        >>> out = roll_retained_earnings(tb, accounts, context=ctx).value
        >>> out[out["gl_key"] == "GL-3300"][["period", "rolled_closing_balance"]].values.tolist()
        [['2026-12', 0.0], ['2027-01', -100.0]]
    """
    _need(trial_balance, ["le_key", "period", "gl_key", "opening_balance", "closing_balance", "closing_balance_dkk"], "finance.trial_balance")
    _need(gl_account, ["gl_key", "statement"], "finance.gl_account")
    start, f = _fy_start()
    st = gl_account.set_index("gl_key")["statement"]
    if st.get(retained_earnings_gl) != "BS":
        raise FrameError(f"{retained_earnings_gl} is not a balance sheet account of finance.gl_account")
    t = trial_balance.copy()
    t["fy"] = _fiscal_year(t["period"], start)
    re_rows = t[t["gl_key"] == retained_earnings_gl].sort_values(["le_key", "period"])
    prev = re_rows.groupby("le_key")["closing_balance"].shift()
    first_of_year = re_rows["period"].str[5:7].astype(int) == start
    jump = first_of_year & prev.notna() & ((re_rows["opening_balance"] - prev).abs() > 0.005)
    if jump.any():
        raise FrameError(f"the trial balance already carries the results into {retained_earnings_gl} (its opening balance jumps at {int(jump.sum())} fiscal year starts, for example {re_rows.loc[jump, 'le_key'].iloc[0]} "
                         f"{re_rows.loc[jump, 'period'].iloc[0]}); pass a table built with carry_results=False")
    t_pl = t[t["gl_key"].map(st).eq("IS")]
    first = pd.PeriodIndex(t_pl["fy"].astype(str) + f"-{start:02d}", freq="M")
    final = t_pl[t_pl["period"].to_numpy() == (cast(Any, first) + 11).strftime("%Y-%m").to_numpy()]               # the closing row of each result account at the last period of its fiscal year
    result = final.groupby(["le_key", "fy"], as_index=False).agg(r=("closing_balance", "sum"), r_dkk=("closing_balance_dkk", "sum"))
    periods = t[["le_key", "period", "fy"]].drop_duplicates()
    have = set(zip(re_rows["le_key"], re_rows["period"]))
    add = periods[[(a, b) not in have for a, b in zip(periods["le_key"], periods["period"])]]
    ext = t
    if len(add):
        new = pd.DataFrame({"le_key": add["le_key"].to_numpy(), "period": add["period"].to_numpy(), "gl_key": retained_earnings_gl, "fy": add["fy"].to_numpy()})
        for col in t.columns:
            if col not in new.columns:
                new[col] = t.groupby("le_key")[col].first().reindex(new["le_key"]).to_numpy() if col == "currency" else 0.0
        ext = pd.concat([t, new[t.columns]], ignore_index=True)
    carry = periods.merge(result, on="le_key", how="left", suffixes=("", "_res"))
    carry = carry[carry["fy_res"] < carry["fy"]].groupby(["le_key", "period"], as_index=False)[["r", "r_dkk"]].sum()
    ext = ext.merge(carry, on=["le_key", "period"], how="left").fillna({"r": 0.0, "r_dkk": 0.0})
    on_re = (ext["gl_key"] == retained_earnings_gl).to_numpy()
    ext["rolled_opening_balance"] = (ext["opening_balance"] + np.where(on_re, ext["r"], 0.0)).round(2)
    ext["rolled_closing_balance"] = (ext["closing_balance"] + np.where(on_re, ext["r"], 0.0)).round(2)
    ext["rolled_closing_balance_dkk"] = (ext["closing_balance_dkk"] + np.where(on_re, ext["r_dkk"], 0.0)).round(2)
    out = ext.drop(columns=["r", "r_dkk", "fy"]).sort_values(["le_key", "period", "gl_key"]).reset_index(drop=True)
    return make_envelope(out, "halvaro.finance.ledger.roll_retained_earnings", facts=(f,), sources=("finance.trial_balance", "finance.gl_account"))


@staged(sources=("finance.gl_account.gl_key", "finance.gl_account.dk_statutory_map", "finance.gl_account.de_statutory_map", "finance.statutory_map_line.map_code", "finance.statutory_map_line.line_code"),
        oracle="py:tests/test_finance.py::test_gl_account_has_statutory_maps")
def statutory_line_of(gl_account: pd.DataFrame, statutory_map_line: pd.DataFrame) -> pd.DataFrame:
    """Use this when you need the statutory statement line that each ledger account belongs to, for Denmark and for Germany.

    Rule: the map code of the account (dk_statutory_map, de_statutory_map) is looked up in the statutory map lines; the line of an account must belong to the country of its map.

    Args:
        gl_account: Frame finance.gl_account with gl_key, dk_statutory_map and de_statutory_map, one row per account.
        statutory_map_line: Frame finance.statutory_map_line with map_code, country, statement, line_order, line_code, label and normal_side, one row per map code.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        pandas.DataFrame with gl_key, country, map_code, statement, line_order, line_code, label and normal_side: one row per account and country.

    Raises:
        FrameError: a column is missing, a key is duplicated, an account has no map, a map code is not in the map lines, or a map belongs to the other country.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import statutory_line_of
        >>> ctx = Context(stage="month12", role="analyst")
        >>> accounts = pd.DataFrame({"gl_key": ["GL-1"], "dk_statutory_map": ["DK-A"], "de_statutory_map": ["DE-A"]})
        >>> lines = pd.DataFrame({"map_code": ["DK-A", "DE-A"], "country": ["DK", "DE"], "statement": ["IS", "IS"], "line_order": [1, 1], "line_code": ["REV", "REV"],
        ...                       "label": ["Revenue", "Umsatz"], "normal_side": ["credit", "credit"]})
        >>> statutory_line_of(accounts, lines, context=ctx)[["gl_key", "country", "line_code", "label"]].sort_values("country").values.tolist()
        [['GL-1', 'DE', 'REV', 'Umsatz'], ['GL-1', 'DK', 'REV', 'Revenue']]
    """
    _need(gl_account, ["gl_key", "dk_statutory_map", "de_statutory_map"], "finance.gl_account")
    _need(statutory_map_line, ["map_code", "country", "statement", "line_order", "line_code", "label", "normal_side"], "finance.statutory_map_line")
    if gl_account["gl_key"].duplicated().any():
        raise FrameError("finance.gl_account has duplicate gl_key values")
    if statutory_map_line["map_code"].duplicated().any():
        raise FrameError("finance.statutory_map_line has duplicate map_code values")
    parts = []
    for country, col in (("DK", "dk_statutory_map"), ("DE", "de_statutory_map")):
        p = gl_account[["gl_key", col]].rename(columns={col: "map_code"}).assign(country=country)
        if p["map_code"].isna().any():
            raise FrameError(f"{int(p['map_code'].isna().sum())} accounts have no {col} (for example {p.loc[p['map_code'].isna(), 'gl_key'].iloc[0]})")
        parts.append(p)
    p = pd.concat(parts, ignore_index=True)
    lines = statutory_map_line.rename(columns={"country": "map_country"})
    m = p.merge(lines, on="map_code", how="left", validate="many_to_one")
    if m["line_code"].isna().any():
        raise FrameError(f"{int(m['line_code'].isna().sum())} statutory maps are not in finance.statutory_map_line (for example {m.loc[m['line_code'].isna(), 'map_code'].iloc[0]})")
    if (m["map_country"] != m["country"]).any():
        raise FrameError("an account maps to a statutory line of the other country")
    cols = ["gl_key", "country", "map_code", "statement", "line_order", "line_code", "label", "normal_side"]
    return m[cols].sort_values(["gl_key", "country"]).reset_index(drop=True)
