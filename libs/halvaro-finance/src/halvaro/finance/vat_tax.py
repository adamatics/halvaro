"""VAT and tax (plan 5.7): VAT boxes from the coded ledger lines, the rate and account checks, settlement against the payment, the filing calendar, the tax provision recomputed from its inputs and the e-invoicing shares.

Rates, due days, tax rates and cut-over dates are core facts (VERIFY, carried in the envelope status). The box layout of the return is a generator placeholder (frep.vat.boxes, VERIFY): the accounts and codes of each box are a keyword.
"""
from __future__ import annotations

import datetime as dt
from typing import Any, Callable, Hashable, Sequence, cast

import numpy as np
import pandas as pd

from halvaro.core import Envelope, FrameError, add_working_days, fact, make_envelope, violations

from ._guard import staged
from ._util import _cents, _day, _need

_OUT_GL, _IN_GL = ("GL-4710", "GL-4720"), ("GL-2510", "GL-2520")
# PROPOSED box layout of the placeholder return (config/finance-reporting-parameters.provisional.yaml vat.boxes): name -> (accounts, vat codes)
_BOXES = {"output_domestic": (_OUT_GL, ("DK25", "DE19")), "output_acquisition_eu": (_OUT_GL, ("RC-EU",)), "output_acquisition_non_eu": (_OUT_GL, ("RC-NONEU",)),
          "input_domestic": (_IN_GL, ("DK25", "DE19")), "input_acquisition_eu": (_IN_GL, ("RC-EU",)), "input_acquisition_non_eu": (_IN_GL, ("RC-NONEU",)), "input_import": (_IN_GL, ())}
_COUNTRY = {"LE-01": "DK", "LE-02": "DE"}                    # PROPOSED: country of the legal entity (hr.legal_entity.country)
_REGION = {"LE-01": "DK", "LE-02": "DE-HH"}                  # PROPOSED: holiday region of the filing office (core calendar)
_CODE_COUNTRY = {"DK25": "DK", "DE19": "DE"}
_VAT_ACCOUNTS = ("GL-2510", "GL-2520", "GL-2530", "GL-4710", "GL-4720", "GL-4740")
_BOX_FACTS = tuple(f"frep.vat.boxes.{n}.label" for n in _BOXES)
_STRUCTURED = ("xrechnung", "zugferd", "peppol_bis")        # PROPOSED: every format except pdf


def _tol_cents(tolerance: float) -> int:
    """A tolerance in currency units as whole cents, cut down (0.015 allows one cent, not two; round() would go to even)."""
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float, np.number)) or not np.isfinite(tolerance) or tolerance < 0:
        raise FrameError("tolerance must be a number of zero or more")
    return int(np.floor(float(tolerance) * 100 + 1e-9))


_CAP = 50                                                                                       # violations listed per rule; a further row says how many were left out


def _capped(rows: list[Any], rule: str, table: str, idx: Sequence[Hashable], make: Callable[[Any], Any]) -> None:
    for i in idx[:_CAP]:
        rows.append(make(i))
    if len(idx) > _CAP:
        rows.append((table, "(more)", rule + "_not_listed", f"{len(idx) - _CAP} further lines with this rule are not listed"))


def _period_pairs(frame: pd.DataFrame) -> pd.Series:
    per = frame["period"].astype(str)
    if not per.str.fullmatch(r"\d{4}-(0[1-9]|1[0-2])").all() or frame[["le_key", "period"]].isna().any().any():
        raise FrameError("finance.journal_line needs an le_key and a period like 2025-02 on every row")
    return per


@staged(sources=("finance.journal_line.le_key", "finance.journal_line.gl_key", "finance.journal_line.period", "finance.journal_line.amount", "finance.journal_line.vat_code",
                 "finance.journal_line.vat_base", "finance.journal_line.currency"), facts=_BOX_FACTS, oracle="py:tests/test_finance_reporting.py::test_vat_returns_equal_vat_coded_lines")
def vat_return_from_ledger(journal_line: pd.DataFrame, *, boxes: dict[str, Any] = _BOXES) -> Envelope:
    """Use this when you need the VAT return of each entity and month rebuilt from the VAT coded ledger lines.

    Rule: output boxes read the credit side of the output accounts (GL-4710, GL-4720) and input boxes the debit side of the input accounts (GL-2510, GL-2520), each box by its VAT codes. The taxable base
    of a box is the sum of vat_base of its lines. vat_payable = total_output_vat less total_input_vat. Every month from the first to the last period of the entity is listed, a month without lines
    has zeros. The box layout is a generator placeholder (fact frep.vat.boxes, status VERIFY) and its status is carried in the envelope.

    Args:
        journal_line: Frame finance.journal_line with le_key, gl_key, period (text like 2025-02), amount (debit positive), vat_code, vat_base and currency.
        boxes: Optional box layout: box name to (accounts, VAT codes). The default is the placeholder layout; the names of the boxes must stay the default names.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        Envelope whose value is a DataFrame with le_key, period, currency, output_vat_domestic, output_vat_acquisition_eu, output_vat_acquisition_non_eu, input_vat_domestic, input_vat_acquisition_eu, input_vat_acquisition_non_eu,
        input_vat_import, total_output_vat, total_input_vat, vat_payable (all in the currency of the entity), taxable_base_domestic_sales, taxable_base_acquisitions_eu,
        taxable_base_acquisitions_non_eu and taxable_base_domestic_purchases. The envelope carries the status of the box facts (VERIFY).
        Typed form: VatReturnRow.from_frame(envelope.value), one frozen model per row.

    Raises:
        FrameError: a column is missing, a period is not text like 2025-02, an entity has lines in more than one currency, or the box names differ from the default names.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import vat_return_from_ledger
        >>> ctx = Context(stage="month3", role="analyst")
        >>> lines = pd.DataFrame([("LE-01", "GL-4710", "2025-01", -250.0, "DK25", 1000.0, "DKK"), ("LE-01", "GL-2510", "2025-01", 100.0, "DK25", 400.0, "DKK")],
        ...                      columns=["le_key", "gl_key", "period", "amount", "vat_code", "vat_base", "currency"])
        >>> env = vat_return_from_ledger(lines, context=ctx)
        >>> env.value.loc[0, ["total_output_vat", "total_input_vat", "vat_payable"]].tolist() == [250.0, 100.0, 150.0]
        True
        >>> env.status
        'VERIFY'
    """
    _need(journal_line, ["le_key", "gl_key", "period", "amount", "vat_code", "vat_base", "currency"], "finance.journal_line")
    journal_line = journal_line.reset_index(drop=True)
    per = _period_pairs(journal_line)
    if set(boxes) != set(_BOXES):
        raise FrameError(f"boxes names {sorted(_BOXES)}")
    facts = [fact(f"frep.vat.boxes.{n}.label") for n in _BOXES]
    cur = journal_line.groupby("le_key", observed=True)["currency"].agg(lambda s: sorted(set(s.astype(str))))
    if (cur.str.len() > 1).any():
        raise FrameError("an entity has lines in more than one currency; the return is in the entity currency")
    v = journal_line[journal_line["vat_code"].notna()]
    c = pd.DataFrame({"le_key": v["le_key"].astype(str).to_numpy(), "period": per[v.index].to_numpy(), "gl": v["gl_key"].astype(str).to_numpy(), "code": v["vat_code"].astype(str).to_numpy(),
                      "a": _cents(v["amount"]), "b": _cents(v["vat_base"].fillna(0.0))})
    rows = []
    for le in sorted(journal_line["le_key"].astype(str).unique()):
        ps = per[journal_line["le_key"].astype(str) == le]
        months = pd.period_range(ps.min(), ps.max(), freq="M").strftime("%Y-%m")
        cl = c[c["le_key"] == le]
        for m in months:
            g = cl[cl["period"] == m]
            vals, bases = {}, {}
            for name, (gls, codes) in boxes.items():
                sel = g[g["gl"].isin(gls) & g["code"].isin(codes)]
                vals[name] = (-1 if name.startswith("output_") else 1) * int(sel["a"].sum())
                bases[name] = int(sel["b"].sum())
            out_t = vals["output_domestic"] + vals["output_acquisition_eu"] + vals["output_acquisition_non_eu"]
            in_t = vals["input_domestic"] + vals["input_acquisition_eu"] + vals["input_acquisition_non_eu"] + vals["input_import"]
            rows.append({"le_key": le, "period": m, "currency": cur[le][0], **{f"{'output' if k.startswith('output_') else 'input'}_vat_{k.split('_', 1)[1]}": v_ / 100 for k, v_ in vals.items()},
                         "total_output_vat": out_t / 100, "total_input_vat": in_t / 100, "vat_payable": (out_t - in_t) / 100, "taxable_base_domestic_sales": bases["output_domestic"] / 100,
                         "taxable_base_acquisitions_eu": bases["output_acquisition_eu"] / 100, "taxable_base_acquisitions_non_eu": bases["output_acquisition_non_eu"] / 100,
                         "taxable_base_domestic_purchases": bases["input_domestic"] / 100})
    return make_envelope(pd.DataFrame(rows), "halvaro.finance.vat_tax.vat_return_from_ledger", facts=facts, sources=("finance.journal_line",),
                         warnings=("the box layout is a generator placeholder, not the official form of either country",))


@staged(sources=("finance.journal_line.le_key", "finance.journal_line.gl_key", "finance.journal_line.period", "finance.journal_line.amount", "finance.journal_line.vat_code",
                 "finance.journal_line.vat_base", "finance.journal_line.source"), facts=("fin.vat.DK.standard_rate", "fin.vat.DE.standard_rate"),
        oracle="py:halvaro_gen/world/finance/checks.py::vat_lines_equal_vat_accounts")
def vat_code_check(journal_line: pd.DataFrame, *, min_base: float = 1000.0, ratio_tolerance: float = 0.001, tolerance: float = 0.005, settlement_sources: tuple[str, ...] = ("treasury", "opening"),
                   vat_accounts: tuple[str, ...] = _VAT_ACCOUNTS) -> Envelope:
    """Use this when you need to check that the VAT codes of the ledger lines carry the right rate, sit on the right accounts and agree with the postings on the VAT accounts.

    Rule: a domestic code (DK25, DE19) carries the standard rate of its country on its base: |vat amount / vat_base - rate| must be within ratio_tolerance for lines with a base of at least min_base
    (rule rate_mismatch). The rate is the fact fin.vat.<country>.standard_rate (status VERIFY). A code on a line outside the VAT accounts and the revenue and cost accounts is code_on_wrong_account.
    A code that belongs to no box is code_in_no_box, a domestic code of the other country is code_of_other_country, a domestic code on a VAT account without a base is missing_vat_base. Per
    entity and month the postings of documents on the VAT accounts must equal the coded lines within `tolerance` (vat_account_differs_from_coded_lines); sources in settlement_sources are left
    out because the return journals that clear the accounts carry no code.

    Args:
        journal_line: Frame finance.journal_line with le_key, gl_key, period, amount, vat_code, vat_base and source.
        min_base: Smallest vat_base that is rate checked, in currency units (default 1000.0, PROPOSED).
        ratio_tolerance: Largest accepted difference between the observed and the standard rate, a share (default 0.001, PROPOSED).
        tolerance: Largest accepted difference of postings and coded lines, in currency units (default 0.005).
        settlement_sources: Journal sources of the return journals that are left out of the account check (default treasury and opening).
        vat_accounts: The VAT accounts (default the output and input accounts of the box layout).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        Envelope whose value is a DataFrame of violations with the columns table (finance.journal_line), key, rule and detail (what was observed), empty when the coding is clean. The key is
        text of words separated by one space: `<le_key> <period> <gl_key>` for the rules on a line (rate_mismatch, code_in_no_box, code_on_wrong_account, code_of_other_country,
        missing_vat_base) and `<le_key> <period>` for vat_account_differs_from_coded_lines, so the period of a violation is the second word of its key. The envelope carries the VERIFY status of
        the rate facts. Typed form: ViolationRow.from_frame(envelope.value), one frozen model per row.

    Raises:
        FrameError: a column is missing, a tolerance is negative or not a number, or a period is not text like 2025-02.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import vat_code_check
        >>> ctx = Context(stage="month3", role="analyst")
        >>> cols = ["le_key", "gl_key", "period", "amount", "vat_code", "vat_base", "source"]
        >>> clean = pd.DataFrame([("LE-01", "GL-4710", "2025-01", -250.0, "DK25", 1000.0, "ar")], columns=cols)
        >>> vat_code_check(clean, context=ctx).value.empty
        True
        >>> off = pd.DataFrame([("LE-01", "GL-4710", "2025-01", -240.0, "DK25", 1000.0, "ar")], columns=cols)
        >>> vat_code_check(off, context=ctx).value["rule"].tolist()
        ['rate_mismatch']
        >>> vat_code_check(off, context=ctx).value["key"].tolist()
        ['LE-01 2025-01 GL-4710']
    """
    _need(journal_line, ["le_key", "gl_key", "period", "amount", "vat_code", "vat_base", "source"], "finance.journal_line")
    journal_line = journal_line.reset_index(drop=True)
    per = _period_pairs(journal_line)
    facts = {c: fact(f"fin.vat.{c}.standard_rate") for c in ("DK", "DE")}
    gl = journal_line["gl_key"].astype(str)
    coded = journal_line["vat_code"].notna()
    on_vat = gl.isin(vat_accounts)
    code = journal_line["vat_code"].astype(object)
    rows: list[tuple[str, str, str, str]] = []
    for cd, ctry in _CODE_COUNTRY.items():
        m = coded & (code == cd) & on_vat & (journal_line["vat_base"].abs() >= min_base)
        if m.any():
            ratio = journal_line.loc[m, "amount"].abs() / journal_line.loc[m, "vat_base"].abs()
            bad = ratio[(ratio - float(facts[ctry].value)).abs() > ratio_tolerance]
            _capped(rows, "rate_mismatch", "finance.journal_line", list(bad.index), lambda i: ("finance.journal_line", f"{journal_line.at[i, 'le_key']} {per[i]} {gl[i]}", "rate_mismatch", f"{cd}: {bad[i]:.4f} of the base, the rate is {float(facts[ctry].value):.4f}"))
    known = set(_CODE_COUNTRY) | {c for _, cs in _BOXES.values() for c in cs}
    nobox = coded & on_vat & ~code.astype(str).isin(known)
    _capped(rows, "code_in_no_box", "finance.journal_line", list(journal_line.index[nobox]), lambda i: ("finance.journal_line", f"{journal_line.at[i, 'le_key']} {per[i]} {gl[i]}", "code_in_no_box", f"VAT code {code[i]} on a VAT account belongs to no box of the return"))
    off = coded & ~on_vat & ~gl.str.startswith(("GL-5", "GL-6", "GL-7", "GL-8", "GL-9"))
    _capped(rows, "code_on_wrong_account", "finance.journal_line", list(journal_line.index[off]), lambda i: ("finance.journal_line", f"{journal_line.at[i, 'le_key']} {per[i]} {gl[i]}", "code_on_wrong_account", f"VAT code {code[i]} on an account that is neither a VAT account nor revenue or cost"))
    # a domestic code on the wrong country's entity, and a domestic code without a base
    ctry_of_le = journal_line["le_key"].astype(str).map(_COUNTRY)
    wrong = coded & code.isin(list(_CODE_COUNTRY)) & ctry_of_le.notna() & (code.map(_CODE_COUNTRY) != ctry_of_le)
    _capped(rows, "code_of_other_country", "finance.journal_line", list(journal_line.index[wrong]), lambda i: ("finance.journal_line", f"{journal_line.at[i, 'le_key']} {per[i]} {gl[i]}", "code_of_other_country", f"VAT code {code[i]} belongs to {_CODE_COUNTRY[code[i]]}, the entity is in {ctry_of_le[i]}"))
    nobase = coded & code.isin(list(_CODE_COUNTRY)) & on_vat & journal_line["vat_base"].isna()
    _capped(rows, "missing_vat_base", "finance.journal_line", list(journal_line.index[nobase]), lambda i: ("finance.journal_line", f"{journal_line.at[i, 'le_key']} {per[i]} {gl[i]}", "missing_vat_base", f"VAT code {code[i]} on a VAT account without a vat_base"))
    doc = on_vat & ~journal_line["source"].astype(str).isin(settlement_sources)
    a = pd.DataFrame({"le_key": journal_line["le_key"].astype(str), "period": per, "doc": np.where(doc, _cents(journal_line["amount"]), 0), "cod": np.where(coded & on_vat, _cents(journal_line["amount"]), 0)})
    g = a.groupby(["le_key", "period"])[["doc", "cod"]].sum()
    for key, r in g[(g["doc"] - g["cod"]).abs() > _tol_cents(tolerance)].iterrows():
        le, p = cast("tuple[str, str]", key)
        rows.append(("finance.journal_line", f"{le} {p}", "vat_account_differs_from_coded_lines", f"postings on the VAT accounts {r['doc'] / 100:.2f}, coded lines {r['cod'] / 100:.2f}"))
    return make_envelope(violations.frame(rows), "halvaro.finance.vat_tax.vat_code_check", facts=list(facts.values()), sources=("finance.journal_line",))


@staged(sources=("finance-reporting.vat_return.le_key", "finance-reporting.vat_return.period", "finance-reporting.vat_return.vat_payable", "finance-reporting.vat_return.settlement_difference",
                 "finance.payment.le_key", "finance.payment.payment_date", "finance.payment.direction", "finance.payment.amount", "finance.payment.description"),
        facts=("fin.vat.DK.payment_day_of_next_month", "fin.vat.DE.payment_day_of_next_month"), oracle="py:tests/test_finance_reporting.py::test_vat_return_settlement_and_status")
def vat_settlement(vat_return: pd.DataFrame, payment: pd.DataFrame, *, description: str | tuple[str, ...] = ("VAT payment", "VAT refund"), tolerance: float = 0.011) -> Envelope:
    """Use this when you need to compare the VAT payable of each return with the VAT payment of the following month.

    Rule: the signed payment is the amount of the payments whose description is one of `description` (outgoing positive, incoming negative, so a refund is an incoming payment). The settlement
    difference = vat_payable less the signed payment of the month after the period. The recomputed difference is compared with the stored one within `tolerance`. The payment day is compared with
    the fact fin.vat.<country>.payment_day_of_next_month (status VERIFY): a payment on that day or on the next working day of the entity's holiday region agrees. A month with no payment has a null
    payment and a null difference.

    Args:
        vat_return: Frame finance-reporting.vat_return with le_key, period (text like 2025-02), vat_payable and settlement_difference.
        payment: Frame finance.payment with le_key, payment_date, direction (outgoing or incoming), amount and description.
        description: One payment description or a tuple of them that count as VAT payments (default "VAT payment" and "VAT refund", PROPOSED).
        tolerance: Largest accepted difference between the recomputed and the stored settlement difference, in currency units (default 0.011).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        Envelope whose value is a DataFrame with le_key, period, vat_payable, payment_month, paid_signed, paid_date, settlement_difference, stored_difference (currency units), agrees and
        day_agrees (yes or no, missing when there is no payment). The envelope carries the VERIFY status of the payment day facts.
        Typed form: VatSettlementRow.from_frame(envelope.value), one frozen model per row.

    Raises:
        FrameError: a column is missing, a period is not text like 2025-02, an entity has no country, a VAT payment has no date or a direction other than outgoing or incoming, or an entity
            has more than one VAT payment in a month.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import vat_settlement
        >>> ctx = Context(stage="month12", role="analyst")
        >>> ret = pd.DataFrame({"le_key": ["LE-01"], "period": ["2025-01"], "vat_payable": [150.0], "settlement_difference": [0.0]})
        >>> pay = pd.DataFrame({"le_key": ["LE-01"], "payment_date": ["2025-02-25"], "direction": ["outgoing"], "amount": [150.0], "description": ["VAT payment"]})
        >>> r = vat_settlement(ret, pay, context=ctx).value
        >>> r.loc[0, ["payment_month", "paid_signed", "settlement_difference", "agrees"]].tolist() == ['2025-02', 150.0, 0.0, True]
        True
    """
    _need(vat_return, ["le_key", "period", "vat_payable", "settlement_difference"], "finance-reporting.vat_return")
    _need(payment, ["le_key", "payment_date", "direction", "amount", "description"], "finance.payment")
    vat_return = vat_return.assign(period=vat_return["period"].astype(str))
    if vat_return["period"].isna().any() or not vat_return["period"].str.fullmatch(r"\d{4}-(0[1-9]|1[0-2])").all():
        raise FrameError("finance-reporting.vat_return.period must be text like 2025-02 on every row")
    if not set(vat_return["le_key"]) <= set(_COUNTRY):
        raise FrameError(f"no country for the entity {sorted(set(vat_return['le_key']) - set(_COUNTRY))[0]}")
    p = payment[payment["description"].isin([description] if isinstance(description, str) else list(description))]
    if p["payment_date"].isna().any():
        raise FrameError("a VAT payment has no payment date")
    if p["direction"].isin(["outgoing", "incoming"]).all() is False or not p["direction"].isin(["outgoing", "incoming"]).all():
        raise FrameError("payment direction must be outgoing or incoming")
    pd_ = pd.to_datetime(p["payment_date"])
    pay = pd.DataFrame({"le_key": p["le_key"].astype(str).to_numpy(), "month": pd_.dt.strftime("%Y-%m").to_numpy(), "day": pd_.dt.date.to_numpy(),
                        "signed": np.where(p["direction"] == "outgoing", p["amount"], -p["amount"]).astype(float)})
    if pay.duplicated(["le_key", "month"]).any():
        raise FrameError("more than one VAT payment for an entity and month")
    pay = pay.set_index(["le_key", "month"])
    facts, rows = {c: fact(f"fin.vat.{c}.payment_day_of_next_month") for c in ("DK", "DE")}, []
    for r in vat_return.to_dict("records"):
        y, m = int(r['period'][:4]), int(r['period'][5:7])
        nxt = f"{y + (m == 12)}-{1 if m == 12 else m + 1:02d}"
        q = pay.loc[(r['le_key'], nxt)] if (r['le_key'], nxt) in pay.index else None
        diff = None if q is None else round(float(r['vat_payable']) - float(q["signed"]), 2)
        ctry = _COUNTRY.get(r['le_key'])
        day_ok: Any = pd.NA
        if q is not None and ctry:
            due = add_working_days(dt.date(y + (m == 12), 1 if m == 12 else m + 1, int(facts[ctry].value)), 1, _REGION[r['le_key']])
            day_ok = bool(q["day"] == due)
        stored = r['settlement_difference']
        rows.append({"le_key": r['le_key'], "period": r['period'], "vat_payable": float(r['vat_payable']), "payment_month": nxt, "paid_signed": None if q is None else float(q["signed"]), "paid_date": None if q is None else q["day"],
                     "settlement_difference": diff, "stored_difference": None if pd.isna(stored) else float(stored),
                     "agrees": pd.NA if diff is None else (bool(pd.isna(stored)) is False and abs(diff - float(stored)) <= tolerance), "day_agrees": day_ok})
    return make_envelope(pd.DataFrame(rows), "halvaro.finance.vat_tax.vat_settlement", facts=list(facts.values()), sources=("finance-reporting.vat_return", "finance.payment"))


@staged(sources=("finance-reporting.vat_return.le_key", "finance-reporting.vat_return.period", "finance-reporting.vat_return.filing_due_date"),
        facts=("frep.vat.DK.filing_due_day_of_next_month", "frep.vat.DE.filing_due_day_of_next_month"), oracle="py:tests/test_finance_reporting.py::test_vat_return_settlement_and_status")
def vat_filing_calendar(vat_return: pd.DataFrame) -> Envelope:
    """Use this when you need the filing due date of each VAT return and want to compare it with the stored date.

    Rule: the due date is the day of the month given by the fact frep.vat.<country>.filing_due_day_of_next_month (status VERIFY) in the month after the period, moved to the next working day of the
    filing office. The office is the holiday region of the entity (LE-01 Denmark, LE-02 Hamburg; PROPOSED).

    Args:
        vat_return: Frame finance-reporting.vat_return with le_key, period (text like 2025-02) and filing_due_date.
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        Envelope whose value is a DataFrame with le_key, period, due_date, stored_due_date (both dates) and agrees (yes or no). The envelope carries the VERIFY status of the day facts.
        Typed form: FilingDateRow.from_frame(envelope.value), one frozen model per row.

    Raises:
        FrameError: a column is missing or an entity has no country.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import vat_filing_calendar
        >>> ctx = Context(stage="month12", role="analyst")
        >>> ret = pd.DataFrame({"le_key": ["LE-01"], "period": ["2025-01"], "filing_due_date": [None]})
        >>> r = vat_filing_calendar(ret, context=ctx).value
        >>> (r.loc[0, "due_date"].year, r.loc[0, "due_date"].month, bool(r.loc[0, "agrees"]))
        (2025, 2, False)
    """
    _need(vat_return, ["le_key", "period", "filing_due_date"], "finance-reporting.vat_return")
    facts, rows = {c: fact(f"frep.vat.{c}.filing_due_day_of_next_month") for c in ("DK", "DE")}, []
    for r in vat_return.to_dict("records"):
        ctry = _COUNTRY.get(r['le_key'])
        if ctry is None:
            raise FrameError(f"no country for the entity {r['le_key']}")
        y, m = int(r['period'][:4]), int(r['period'][5:7])
        due = add_working_days(dt.date(y + (m == 12), 1 if m == 12 else m + 1, int(facts[ctry].value)), 1, _REGION[r['le_key']])
        stored = None if pd.isna(r['filing_due_date']) else pd.Timestamp(r['filing_due_date']).date()
        rows.append({"le_key": r['le_key'], "period": r['period'], "due_date": due, "stored_due_date": stored, "agrees": stored == due})
    return make_envelope(pd.DataFrame(rows), "halvaro.finance.vat_tax.vat_filing_calendar", facts=list(facts.values()), sources=("finance-reporting.vat_return",))


_TAX_COLS = ["le_key", "fiscal_year", "tax_rate", "profit_before_tax", "non_deductible_expenses", "exempt_income", "temporary_difference_movement", "taxable_income_before_losses", "tax_loss_utilised",
             "tax_loss_added", "tax_loss_carried_forward", "taxable_income", "current_tax", "deferred_tax_movement", "total_tax_expense"]


@staged(sources=tuple(f"finance-reporting.tax_provision.{c}" for c in _TAX_COLS if c != "le_key") + ("finance-reporting.tax_provision.le_key",),
        facts=("frep.corporate_tax.DK.rate", "frep.corporate_tax.DE.rate", "frep.corporate_tax.tax_losses.utilisation_cap_share_of_taxable_income"),
        oracle="py:tests/test_finance_reporting.py::test_tax_in_statements_equals_provision")
def tax_provision(provision: pd.DataFrame, *, tolerance: float = 0.011) -> Envelope:
    """Use this when you need the corporate tax provision of each entity and fiscal year recomputed from its inputs and compared with the stored rows.

    Rule, per entity in fiscal year order: taxable income before losses = profit before tax + non deductible expenses - exempt income - temporary difference movement. A negative result is added
    to the loss carried forward; a positive one is reduced by the loss utilised, at most the share of the fact frep.corporate_tax.tax_losses.utilisation_cap_share_of_taxable_income of the income
    and at most the loss carried in. taxable income = income before losses - loss utilised. current tax = rate x taxable income. total tax expense = current tax + the stored deferred movement.
    The rate of the row is compared with the fact frep.corporate_tax.<country>.rate (status VERIFY). The deferred movement is taken as stored: its inputs are not in the row. The function
    refuses when the fact fin.corporate_tax.posted_in_ledger is true, because the provision would then be counted twice.

    Args:
        provision: Frame finance-reporting.tax_provision with the inputs and the stored results, one row per entity and fiscal year.
        tolerance: Largest accepted difference between a recomputed and a stored figure, in currency units (default 0.011).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        Envelope whose value is a DataFrame with le_key, fiscal_year, tax_rate (a share), profit_before_tax, taxable_income_before_losses, tax_loss_utilised, tax_loss_added,
        tax_loss_carried_forward, taxable_income, current_tax, deferred_tax_movement, total_tax_expense (currency units), rate_is_the_fact and agrees (yes or no).
        Typed form: TaxProvisionRow.from_frame(envelope.value), one frozen model per row.

    Raises:
        FrameError: a column is missing, a row has no entity or fiscal year, an entity and year appear twice, an input is null, or fin.corporate_tax.posted_in_ledger is true.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context, fact
        >>> from halvaro.finance import tax_provision
        >>> from halvaro.finance.vat_tax import _TAX_COLS
        >>> ctx = Context(stage="month12", role="analyst")
        >>> rate = fact("frep.corporate_tax.DK.rate").value
        >>> row = dict.fromkeys(_TAX_COLS, 0.0)
        >>> row.update(le_key="LE-01", fiscal_year=2025, tax_rate=rate, profit_before_tax=1000.0, taxable_income_before_losses=1000.0, taxable_income=1000.0,
        ...            current_tax=round(1000.0 * rate, 2), total_tax_expense=round(1000.0 * rate, 2))
        >>> r = tax_provision(pd.DataFrame([row]), context=ctx).value
        >>> r.loc[0, ["taxable_income", "current_tax", "rate_is_the_fact", "agrees"]].tolist() == [1000.0, round(1000.0 * rate, 2), True, True]
        True
    """
    _need(provision, _TAX_COLS, "finance-reporting.tax_provision")
    if provision["le_key"].isna().any() or provision["fiscal_year"].isna().any():
        raise FrameError("finance-reporting.tax_provision has a row without le_key or fiscal_year")
    if provision.duplicated(["le_key", "fiscal_year"]).any():
        raise FrameError("finance-reporting.tax_provision has more than one row for an entity and fiscal year")
    if provision[["profit_before_tax", "non_deductible_expenses", "exempt_income", "temporary_difference_movement", "tax_rate", "deferred_tax_movement"]].isna().any().any():
        raise FrameError("finance-reporting.tax_provision has null inputs")
    cap_f = fact("frep.corporate_tax.tax_losses.utilisation_cap_share_of_taxable_income")
    posted_f = fact("fin.corporate_tax.posted_in_ledger")
    if posted_f.value is True:
        raise FrameError("fin.corporate_tax.posted_in_ledger is true: the provision is already in the ledger and would be counted twice")
    rate_f = {c: fact(f"frep.corporate_tax.{c}.rate") for c in ("DK", "DE")}
    rows = []
    for le, g in provision.sort_values(["le_key", "fiscal_year"]).groupby("le_key"):
        carried = 0.0
        for r in g.to_dict("records"):
            before = r['profit_before_tax'] + r['non_deductible_expenses'] - r['exempt_income'] - r['temporary_difference_movement']
            added = max(-before, 0.0)
            used = min(carried, float(cap_f.value) * max(before, 0.0))
            carried = carried - used + added
            taxable = max(before, 0.0) - used
            cur = taxable * float(r['tax_rate'])
            tot = cur + r['deferred_tax_movement']
            ctry = _COUNTRY.get(str(le))
            rate_ok = ctry is not None and abs(float(r['tax_rate']) - float(rate_f[ctry].value)) < 1e-9
            tol = tolerance + 1e-9
            ok = (abs(before - r['taxable_income_before_losses']) <= tol and abs(used - r['tax_loss_utilised']) <= tol and abs(added - r['tax_loss_added']) <= tol and abs(carried - r['tax_loss_carried_forward']) <= tol
                  and abs(taxable - r['taxable_income']) <= tol and abs(cur - r['current_tax']) <= tol and abs(tot - r['total_tax_expense']) <= tol)
            rows.append({"le_key": le, "fiscal_year": r['fiscal_year'], "tax_rate": float(r['tax_rate']), "profit_before_tax": float(r['profit_before_tax']), "taxable_income_before_losses": round(before, 2),
                         "tax_loss_utilised": round(used, 2), "tax_loss_added": round(added, 2), "tax_loss_carried_forward": round(carried, 2), "taxable_income": round(taxable, 2),
                         "current_tax": round(cur, 2), "deferred_tax_movement": float(r['deferred_tax_movement']), "total_tax_expense": round(tot, 2), "rate_is_the_fact": rate_ok, "agrees": bool(ok and rate_ok)})
    return make_envelope(pd.DataFrame(rows), "halvaro.finance.vat_tax.tax_provision", facts=[cap_f, posted_f, *rate_f.values()], sources=("finance-reporting.tax_provision",))


@staged(sources=("finance.customer_invoice.le_key", "finance.customer_invoice.invoice_date", "finance.customer_invoice.invoice_format", "finance.customer_invoice.counterpart_le_key",
                 "finance.customer_invoice.invoice_type"),
        oracle="py:tests/test_vat_tax.py::test_einvoice_share_and_gap")
def einvoice_format_share(customer_invoice: pd.DataFrame, *, le_key: str = "LE-02", structured: tuple[str, ...] = _STRUCTURED, invoice_types: tuple[str, ...] | None = None) -> pd.DataFrame:
    """Use this when you need the share of structured e-invoices among the third party invoices of one entity, by month.

    Rule: share = invoices whose format is structured / all invoices of the month, four decimals. Structured formats are every format except pdf (default xrechnung, zugferd and peppol_bis,
    PROPOSED). Intercompany invoices (counterpart_le_key set) are left out. By default every document counts, credit notes included; invoice_types restricts the rows to those types when the
    frame has invoice_type, for example ("invoice",) leaves credit notes out.

    Args:
        customer_invoice: Frame finance.customer_invoice with le_key, invoice_date, invoice_format and counterpart_le_key (and invoice_type to filter).
        le_key: Entity to count (default LE-02, the German company).
        structured: Tuple of the invoice formats that count as structured.
        invoice_types: Tuple of invoice types to count, or None for every type (default None).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        DataFrame with period (text like 2025-02), n_invoices and n_structured (counts) and share (between 0 and 1, four decimals), one row per month with invoices.
        Typed form: EinvoiceShareRow.from_frame(the frame), one frozen model per row.

    Raises:
        FrameError: a column is missing, an invoice has no date or no format, or structured or invoice_types is a single text instead of a tuple.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import einvoice_format_share
        >>> ctx = Context(stage="month3", role="analyst")
        >>> inv = pd.DataFrame({"le_key": "LE-02", "invoice_date": ["2025-03-03", "2025-03-10", "2025-03-20"], "invoice_format": ["pdf", "xrechnung", "xrechnung"],
        ...                     "counterpart_le_key": [None, None, None]})
        >>> einvoice_format_share(inv, context=ctx).loc[0, ["period", "n_invoices", "n_structured", "share"]].tolist() == ['2025-03', 3, 2, 0.6667]
        True
    """
    _need(customer_invoice, ["le_key", "invoice_date", "invoice_format", "counterpart_le_key"], "finance.customer_invoice")
    if isinstance(structured, (str, bytes)) or isinstance(invoice_types, (str, bytes)):
        raise FrameError("structured and invoice_types must be tuples, not a single text")
    if customer_invoice["invoice_date"].isna().any():
        raise FrameError("finance.customer_invoice has an invoice without a date")
    x = customer_invoice[(customer_invoice["le_key"] == le_key) & customer_invoice["counterpart_le_key"].isna()]
    if invoice_types is not None and "invoice_type" in x.columns:
        x = x[x["invoice_type"].isin(list(invoice_types))]
    if x["invoice_format"].isna().any():
        raise FrameError("invoices without an invoice_format")
    per = pd.to_datetime(x["invoice_date"]).dt.strftime("%Y-%m")
    s = pd.DataFrame({"period": per.to_numpy(), "st": x["invoice_format"].isin(list(structured)).to_numpy()})
    g = s.groupby("period").agg(n_invoices=("st", "size"), n_structured=("st", "sum")).reset_index()
    g["share"] = (g["n_structured"] / g["n_invoices"]).round(4)
    return g.astype({"n_structured": int})


@staged(sources=("finance.customer_invoice.le_key", "finance.customer_invoice.cus_key", "finance.customer_invoice.invoice_date", "finance.customer_invoice.invoice_format",
                 "finance.customer_invoice.counterpart_le_key"), facts=("fin.e_invoicing.DE.mandatory_issue_from", "fin.e_invoicing.DE.pdf_allowed_until"),
        oracle="py:repo_tests/test_oracle_vat_tax_release.py::test_oracle_einvoice_gap_baseline_invoices_filtered_with_plain_loops")
def einvoice_gap(customer_invoice: pd.DataFrame, as_of: dt.date, *, le_key: str = "LE-02", months: int = 6) -> Envelope:
    """Use this when you need the customers of one entity that still receive pdf invoices shortly before structured invoices become mandatory.

    Rule: the invoices of the entity dated after as_of less `months` months (a rolling window: the same day `months` months earlier, the day clipped to the length of that month) up to and including as_of,
    without intercompany invoices. A customer is listed when at least one of those invoices is a pdf. last_invoice_date and last_format are those of the customer's latest invoice in the window; invoices of the
    same day are ordered by inv_key when the frame has that column, else by position.
    days_to_mandatory = the fact fin.e_invoicing.DE.mandatory_issue_from less as_of, in days (negative after the date). The fact fin.e_invoicing.DE.pdf_allowed_until is read and carried in the
    envelope with its status; it does not bound the window or the list. Both facts have status VERIFY and the status is carried in the envelope.

    Args:
        customer_invoice: Frame finance.customer_invoice with le_key, cus_key, invoice_date, invoice_format and counterpart_le_key.
        as_of: The date the window ends on (a date).
        le_key: Entity to look at (default LE-02, the German company).
        months: Length of the window in whole months, one or more (default 6, PROPOSED).
        context: A halvaro.core.Context (stage and role of the session), required.

    Returns:
        Envelope whose value is a DataFrame with cus_key, n_pdf and n_invoices (counts), last_invoice_date, last_format and days_to_mandatory (days), the customers with most pdf invoices first.
        Typed form: EinvoiceGapRow.from_frame(envelope.value), one frozen model per row.

    Raises:
        FrameError: a column is missing or months is not a whole number of one or more.
        StageRefusal: a source of the function is above the stage of the context.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.core import Context
        >>> from halvaro.finance import einvoice_gap
        >>> ctx = Context(stage="month3", role="analyst")
        >>> inv = pd.DataFrame({"le_key": "LE-02", "cus_key": ["CUS-1", "CUS-2"], "invoice_date": ["2025-03-03", "2025-03-04"], "invoice_format": ["pdf", "xrechnung"],
        ...                     "counterpart_le_key": [None, None]})
        >>> r = einvoice_gap(inv, dt.date(2025, 3, 31), context=ctx).value
        >>> r["cus_key"].tolist()
        ['CUS-1']
    """
    _need(customer_invoice, ["le_key", "cus_key", "invoice_date", "invoice_format", "counterpart_le_key"], "finance.customer_invoice")
    if isinstance(months, bool) or not isinstance(months, int) or months < 1:
        raise FrameError("months must be a whole number, one or more")
    d = _day(as_of)
    mand, allowed = fact("fin.e_invoicing.DE.mandatory_issue_from"), fact("fin.e_invoicing.DE.pdf_allowed_until")
    due = pd.Timestamp(mand.value)
    x = customer_invoice[(customer_invoice["le_key"] == le_key) & customer_invoice["counterpart_le_key"].isna()].copy()
    x["d"] = pd.to_datetime(x["invoice_date"])
    x = x[(x["d"] <= d) & (x["d"] > d - pd.DateOffset(months=months))]
    rows = []
    for cus, g in x.groupby("cus_key"):
        last = g.sort_values(["d", "inv_key"] if "inv_key" in g.columns else ["d"], kind="stable").iloc[-1]
        n_pdf = int((g["invoice_format"] == "pdf").sum())
        if n_pdf:
            rows.append({"cus_key": cus, "n_pdf": n_pdf, "n_invoices": len(g), "last_invoice_date": last["d"].date(), "last_format": last["invoice_format"], "days_to_mandatory": int((due - d).days)})
    out = pd.DataFrame(rows, columns=["cus_key", "n_pdf", "n_invoices", "last_invoice_date", "last_format", "days_to_mandatory"]).sort_values(["n_pdf", "cus_key"], ascending=[False, True]).reset_index(drop=True)
    return make_envelope(out, "halvaro.finance.vat_tax.einvoice_gap", facts=[mand, allowed], sources=("finance.customer_invoice",))
