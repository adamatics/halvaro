"""Holiday ledger and carry-over. Legal values come from core facts and carry their status; policy values are keyword parameters."""
from __future__ import annotations

import calendar
import datetime as dt
import re
import warnings
from typing import Any, Sequence, cast

import pandas as pd

from halvaro.core import FrameError, combine_status, fact
from halvaro.core.registry import function

from .holiday_results import AccrualRows, CarryOverProjectionRows, CarryOverRows, HighCarryOverRows, HolidayBalance, LeaveLedgerRows, LedgerRows
from .org import PolicyDefault, policy_number

_ACCR = "legal.{c}.holiday.accrual_days_per_month"
_CAP = "legal.{c}.holiday.carryover.default_max_days"
_AGR = "legal.DK.holiday.carryover.agreement_max_days"
_START_M, _START_D = "legal.{c}.holiday.holiday_year_start.month", "legal.{c}.holiday.holiday_year_start.day"
_FORMAT = "legal.{c}.holiday.label_format"
_ANNUAL = "legal.{c}.holiday.annual_days"
_DEADLINE_M, _DEADLINE_D = "legal.DE.holiday.carryover.deadline_month_day.month", "legal.DE.holiday.carryover.deadline_month_day.day"
_ENT = ("hr.holiday_entitlement.emp_key", "hr.holiday_entitlement.holiday_year", "hr.holiday_entitlement.carried_in_days",
        "hr.holiday_entitlement.carry_over_agreement", "hr.holiday_entitlement.opening_balance")
_ACC = ("hr.holiday_accrual.emp_key", "hr.holiday_accrual.holiday_year", "hr.holiday_accrual.period", "hr.holiday_accrual.accrued_days",
        "hr.holiday_accrual.taken_days")
_LABELS = tuple(_FORMAT.format(c=c) for c in ("DK", "DE"))
_START_FACTS = tuple(_START_M.format(c=c) for c in ("DK", "DE")) + tuple(_START_D.format(c=c) for c in ("DK", "DE"))
_CAPS = (_CAP.format(c="DK"), _CAP.format(c="DE"), _AGR)
_WINDOW = "world.window_start"


def _need(frame: pd.DataFrame, columns: Sequence[str], what: str) -> None:
    missing = [c for c in columns if c not in frame.columns]
    if missing:
        raise FrameError(f"{what} frame lacks column(s) {', '.join(missing)}")


def _country_of_label(label: str) -> str:
    """The country whose label_format fact (DK {y}/{y2}, DE {y}) matches the label; any other text raises FrameError."""
    for c in ("DK", "DE"):
        rx = str(fact(_FORMAT.format(c=c)).value).replace("{y}", r"\d{4}").replace("{y2}", r"\d{2}")
        if re.fullmatch(rx, str(label)):
            return c
    raise FrameError(f"holiday year {label!r} matches no label format (DK 2026/27, DE 2026)")


def _legal_status(*ids: str) -> str:
    return combine_status(fact(i).status for i in ids)


@function(facts=("legal.DK.holiday.holiday_year_start.month", "legal.DE.holiday.holiday_year_start.month", "legal.DK.holiday.label_format",
                 "legal.DE.holiday.label_format"), oracle="py:halvaro_gen/world/holiday.py::label_for")
def holiday_year_label(country: str, as_of: dt.date) -> str:
    """Use this when you need the label of the holiday year that contains a date, for DK or DE.

    The start month of the holiday year and the label format of the country are read from the legal facts at call time, so a changed fact changes the label. A date before the start month
    belongs to the holiday year that began in the previous calendar year.

    Rule: the label is the start year of the holiday year written in the label_format fact of the country (DK start year, slash, last two digits of the end year; DE the year).

    Args:
        country: "DK" or "DE".
        as_of: Any date.

    Returns:
        The label as text, for example "2026/27" (DK) or "2026" (DE).

    Raises:
        FrameError: country is not "DK" or "DE".

    Example:
        >>> import datetime as dt
        >>> from halvaro.hr import holiday_year_bounds, holiday_year_label
        >>> first_day, last_day = holiday_year_bounds("2026/27")
        >>> holiday_year_label("DK", first_day), holiday_year_label("DK", last_day)
        ('2026/27', '2026/27')
        >>> holiday_year_label("DK", first_day - dt.timedelta(days=1))
        '2025/26'
    """
    if country not in ("DK", "DE"):
        raise FrameError(f"country {country!r} is not DK or DE")
    month = fact(_START_M.format(c=country)).value
    y = as_of.year if as_of.month >= month else as_of.year - 1
    return str(fact(_FORMAT.format(c=country)).value.format(y=y, y2=f"{(y + 1) % 100:02d}"))


@function(facts=_START_FACTS + _LABELS, oracle="py:halvaro_gen/world/leave.py::hy_bounds")
def holiday_year_bounds(label: str) -> tuple[dt.date, dt.date]:
    """Use this when you have the label of a holiday year and need its first and last day.

    The country is read from the label format (DK "2026/27", DE "2026"). The first day is the start month and day of the holiday year of that country (legal facts) in the start year of the
    label. The last day is the day before the next holiday year starts.

    Args:
        label: Holiday year label, for example "2026/27" or "2026".

    Returns:
        (first_day, last_day) as dates, both inclusive.

    Raises:
        FrameError: the label matches no label format.

    Example:
        >>> from halvaro.hr import holiday_year_bounds
        >>> first_day, last_day = holiday_year_bounds("2026/27")
        >>> first_day.year, last_day.year
        (2026, 2027)
        >>> (last_day - first_day).days >= 364
        True
    """
    c = _country_of_label(label)
    start = dt.date(int(str(label)[:4]), fact(_START_M.format(c=c)).value, fact(_START_D.format(c=c)).value)
    end = dt.date(start.year + 1, start.month, start.day) - dt.timedelta(days=1)
    return start, end


@function(sources=_ENT + _ACC + ("hr.holiday_entitlement.entitlement_days",), facts=(_ANNUAL.format(c="DK"), _ANNUAL.format(c="DE"), _ACCR.format(c="DK"), _ACCR.format(c="DE")) + _LABELS,
          oracle="py:halvaro_gen/world/holiday.py::holiday_balance")
def holiday_balance(ent: pd.DataFrame, acc: pd.DataFrame, emp_key: str, holiday_year: str, as_of: dt.date) -> HolidayBalance:
    """Use this when you need the holiday balance of one person in one holiday year at the end of a month.

    Rule: balance_days = carried_in_days + accrued_days_ytd - taken_days_ytd. The sums run over the ledger periods of the person and holiday year up to the month of as_of, and as_of is
    read as the end of its month. entitlement_days is the full-year entitlement: it is reported and never used as accrued. A person with no entitlement row and no accrual rows gets a zero
    record (has_entitlement_row is False). legal_status is the combined status of the legal facts behind the country of the label.

    Args:
        ent: Entitlement frame (hr.holiday_entitlement) with emp_key, holiday_year, entitlement_days, carried_in_days, carry_over_agreement.
        acc: Accrual frame (hr.holiday_accrual) with emp_key, holiday_year, period (YYYY-MM), accrued_days, taken_days.
        emp_key: Key of the person (EMP-).
        holiday_year: Holiday year label, for example "2026/27".
        as_of: A date. Its month is the last month counted.

    Returns:
        HolidayBalance, a frozen model whose fields carry a description and a unit (HolidayBalance.columns()): emp_key, holiday_year, as_of (ISO text), entitlement_days, carried_in_days,
        carry_over_agreement, accrued_days_ytd, taken_days_ytd, balance_days (all in days, rounded to 2 decimals), has_entitlement_row and legal_status. result.to_dict() gives the fields as a dict.

    Raises:
        FrameError: a frame lacks a required column, the person has more than one entitlement row for the year, the person has accrual rows but no entitlement row, or the label matches no
            label format.
        UserWarning: (a warning, not an error) as_of is after the last ledger period, so the balance is frozen at that month.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.core import fact
        >>> from halvaro.hr import holiday_balance
        >>> rate = fact("legal.DK.holiday.accrual_days_per_month").value
        >>> ent = pd.DataFrame({"emp_key": ["EMP-1"], "holiday_year": ["2026/27"], "entitlement_days": [fact("legal.DK.holiday.annual_days").value],
        ...                     "carried_in_days": [3.0], "carry_over_agreement": [False]})
        >>> acc = pd.DataFrame({"emp_key": ["EMP-1", "EMP-1"], "holiday_year": ["2026/27", "2026/27"], "period": ["2026-09", "2026-10"],
        ...                     "accrued_days": [rate, rate], "taken_days": [0.0, 1.0]})
        >>> b = holiday_balance(ent, acc, "EMP-1", "2026/27", dt.date(2026, 10, 15))
        >>> b.balance_days == round(3.0 + 2 * rate - 1.0, 2)
        True
    """
    _need(ent, ["emp_key", "holiday_year", "entitlement_days", "carried_in_days", "carry_over_agreement"], "hr.holiday_entitlement")
    _need(acc, ["emp_key", "holiday_year", "period", "accrued_days", "taken_days"], "hr.holiday_accrual")
    c = _country_of_label(holiday_year)
    status = _legal_status(_ANNUAL.format(c=c), _ACCR.format(c=c))
    e = ent[(ent["emp_key"] == emp_key) & (ent["holiday_year"] == holiday_year)]
    if len(e) > 1:
        raise FrameError(f"{emp_key} has {len(e)} entitlement rows for {holiday_year}; expected 1")
    own = acc[(acc["emp_key"] == emp_key) & (acc["holiday_year"] == holiday_year)]
    if not len(e) and len(own):
        raise FrameError(f"{emp_key} has accrual rows for {holiday_year} but no entitlement row (see the missing_entitlement flag of holiday_ledger)")
    period = f"{as_of.year}-{as_of.month:02d}"
    if len(acc) and period > str(acc["period"].max()):
        warnings.warn(f"as_of {as_of} is after the last ledger period {acc['period'].max()}: the balance is frozen at that month", UserWarning, stacklevel=2)
    a = own[own["period"] <= period]
    accrued, taken = round(float(a["accrued_days"].sum()), 2), round(float(a["taken_days"].sum()), 2)
    row = e.iloc[0] if len(e) else None
    carried = float(row["carried_in_days"]) if row is not None else 0.0
    return HolidayBalance(emp_key=emp_key, holiday_year=holiday_year, as_of=as_of.isoformat(), entitlement_days=float(row["entitlement_days"]) if row is not None else 0.0,
                          carried_in_days=carried, carry_over_agreement=bool(row["carry_over_agreement"]) if row is not None else False,
                          accrued_days_ytd=accrued, taken_days_ytd=taken, balance_days=round(carried + accrued - taken, 2),
                          has_entitlement_row=row is not None, legal_status=status)


@function(sources=_ENT + _ACC, facts=_LABELS, oracle="py:tests/test_leave.py::test_ledger_never_negative_and_matches_leave_records")
def holiday_ledger(ent: pd.DataFrame, acc: pd.DataFrame) -> LedgerRows:
    """Use this when you need the month by month holiday balance of every person and holiday year, with flags for a negative balance, a missing entitlement row and an opening balance.

    Rule: balance = carried_in_days + running sum of (accrued_days - taken_days) in period order, per person and holiday year, rounded to 2 decimals. A ledger row without an entitlement row
    counts carried_in_days as 0 and is flagged missing_entitlement. negative is True when balance is below zero (bound of 1e-6 days).

    Args:
        ent: Entitlement frame (hr.holiday_entitlement) with emp_key, holiday_year, carried_in_days, opening_balance.
        acc: Accrual frame (hr.holiday_accrual) with emp_key, holiday_year, period (YYYY-MM), accrued_days, taken_days.

    Returns:
        LedgerRows: an immutable sequence of LedgerRow, one per accrual row, sorted by emp_key, holiday_year, period. Fields of a row: emp_key (key), holiday_year (label), period (YYYY-MM),
        accrued_days (days), taken_days (days), balance (days), opening_balance (flag: carried_in_days is the start value of the data window), missing_entitlement (flag), negative (flag),
        legal_status (status of the facts). Every field carries a description and a unit (LedgerRow.columns()). result.to_frame() gives the DataFrame with these columns.

    Raises:
        FrameError: a frame lacks a required column, or the entitlement frame has several rows for one person and holiday year.

    Example:
        >>> import pandas as pd
        >>> from halvaro.hr import holiday_ledger
        >>> ent = pd.DataFrame({"emp_key": ["EMP-1"], "holiday_year": ["2026/27"], "carried_in_days": [1.0], "opening_balance": [False]})
        >>> acc = pd.DataFrame({"emp_key": ["EMP-1", "EMP-1"], "holiday_year": ["2026/27", "2026/27"], "period": ["2026-09", "2026-10"],
        ...                     "accrued_days": [2.0, 2.0], "taken_days": [0.0, 6.0]})
        >>> ledger = holiday_ledger(ent, acc)
        >>> [row.balance for row in ledger], [row.negative for row in ledger]
        ([3.0, -1.0], [False, True])
        >>> ledger.to_frame().balance.tolist()
        [3.0, -1.0]
    """
    _need(ent, ["emp_key", "holiday_year", "carried_in_days", "opening_balance"], "hr.holiday_entitlement")
    _need(acc, ["emp_key", "holiday_year", "period", "accrued_days", "taken_days"], "hr.holiday_accrual")
    if ent.duplicated(["emp_key", "holiday_year"]).any():
        raise FrameError("hr.holiday_entitlement has several rows for one person and holiday year; expected 1")
    a = acc.merge(ent[["emp_key", "holiday_year", "carried_in_days", "opening_balance"]], on=["emp_key", "holiday_year"], how="left", validate="many_to_one")
    a = a.sort_values(["emp_key", "holiday_year", "period"]).reset_index(drop=True)
    a["missing_entitlement"] = a["carried_in_days"].isna()
    a["opening_balance"] = a["opening_balance"].fillna(False).astype(bool)
    net = (a["accrued_days"] - a["taken_days"]).groupby([a["emp_key"], a["holiday_year"]]).cumsum()
    a["balance"] = (a["carried_in_days"].fillna(0.0) + net).round(2)
    a["negative"] = a["balance"] < -1e-6
    a["legal_status"] = _legal_status(*_LABELS)
    return LedgerRows.from_frame(a[["emp_key", "holiday_year", "period", "accrued_days", "taken_days", "balance", "opening_balance", "missing_entitlement", "negative", "legal_status"]])


@function(sources=_ENT, facts=_CAPS + _LABELS + (_DEADLINE_M, _DEADLINE_D), oracle="py:tests/test_leave.py::test_carry_in_caps")
def carry_over_position(ent: pd.DataFrame) -> CarryOverRows:
    """Use this when you need to compare the days carried into each holiday year with the cap that applies to the person, and see the headroom that is left.

    Rule: basis is "agreement" for a DK row whose carry_over_agreement flag is set, otherwise "default" (DE rows have the default only). cap is the cap fact of that basis. headroom = cap -
    carried_in_days, so a carry-in above its cap shows as negative headroom. at_cap is True when headroom is zero. An opening row (opening_balance True) is the start value of the data window:
    it has no cap and no headroom, and at_cap is False. For DE rows deadline is the date given by the deadline facts in the year of the label; DK rows have no deadline.

    Args:
        ent: Entitlement frame (hr.holiday_entitlement) with emp_key, holiday_year, carried_in_days, carry_over_agreement, opening_balance.

    Returns:
        CarryOverRows: an immutable sequence of CarryOverRow, one per entitlement row. Fields of a row: emp_key, holiday_year, carried_in_days (days), carry_over_agreement (flag),
        opening_balance (flag), country (DK or DE), basis ("default" or "agreement"), cap (days, None on an opening row), headroom (days, None on an opening row), at_cap (flag),
        deadline (date, DE only, else None), legal_status (status of the facts). Every field carries a description and a unit (CarryOverRow.columns()). result.to_frame() gives the DataFrame.

    Raises:
        FrameError: the frame lacks a required column, or a holiday year label matches no label format.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import fact
        >>> from halvaro.hr import carry_over_position
        >>> cap = fact("legal.DK.holiday.carryover.default_max_days").value
        >>> ent = pd.DataFrame({"emp_key": ["EMP-1", "EMP-2"], "holiday_year": ["2026/27", "2026/27"], "carried_in_days": [cap, cap + 1],
        ...                     "carry_over_agreement": [False, False], "opening_balance": [False, False]})
        >>> position = carry_over_position(ent)
        >>> [row.headroom for row in position], [row.at_cap for row in position]
        ([0.0, -1.0], [True, False])
    """
    _need(ent, ["emp_key", "holiday_year", "carried_in_days", "carry_over_agreement", "opening_balance"], "hr.holiday_entitlement")
    out = ent[["emp_key", "holiday_year", "carried_in_days", "carry_over_agreement", "opening_balance"]].copy()
    out["country"] = out["holiday_year"].map(_country_of_label)
    cap = {"DK": float(fact(_CAP.format(c="DK")).value), "DE": float(fact(_CAP.format(c="DE")).value)}
    agr = float(fact(_AGR).value)
    out["basis"] = ["agreement" if (c == "DK" and a) else "default" for c, a in zip(out["country"], out["carry_over_agreement"])]
    out["cap"] = [agr if b == "agreement" else cap[c] for b, c in zip(out["basis"], out["country"])]
    opening = out["opening_balance"].astype(bool)
    out.loc[opening, "cap"] = float("nan")
    out["headroom"] = out["cap"] - out["carried_in_days"]
    out["at_cap"] = (out["headroom"].abs() < 1e-9) & ~opening
    m, d = fact(_DEADLINE_M).value, fact(_DEADLINE_D).value
    out["deadline"] = [dt.date(int(h[:4]), m, min(d, calendar.monthrange(int(h[:4]), m)[1])) if c == "DE" else None for h, c in zip(out["holiday_year"], out["country"])]
    out["legal_status"] = _legal_status(*_CAPS, *_LABELS, _DEADLINE_M, _DEADLINE_D)
    return CarryOverRows.from_frame(out.reset_index(drop=True))


@function(sources=_ENT + _ACC, facts=_CAPS + _LABELS, oracle="py:halvaro_gen/world/leave.py::Builder")
def carry_over_projection(ledger: LedgerRows | pd.DataFrame, ent: pd.DataFrame, *, tolerance: float = 0.05) -> CarryOverProjectionRows:
    """Use this when you need the carry-in that the next holiday year should start with, and whether the carry-in stored for it agrees.

    Rule: projected_carry_in = min(max(year_end_balance, 0), cap). year_end_balance is the balance of the last ledger period of the person and holiday year (the frame of holiday_ledger).
    cap is the cap of the closing year: the agreement cap for a DK person whose carry_over_agreement flag is set in that year, otherwise the default cap; a closing year without an entitlement
    row has the default. stored_carry_in is carried_in_days of the next holiday year (null when that year has no row). difference = projected_carry_in - stored_carry_in. matches is True when
    the difference is within `tolerance` days (null without a stored value). The tolerance of 0.05 days is a proposed policy value.

    Args:
        ledger: The result of holiday_ledger (LedgerRows), or a frame with emp_key, holiday_year, period, balance (for example its to_frame()).
        ent: Entitlement frame (hr.holiday_entitlement) with emp_key, holiday_year, carried_in_days, carry_over_agreement.
        tolerance: Largest difference in days that still counts as a match. A number of zero or more, not a bool.

    Returns:
        CarryOverProjectionRows: an immutable sequence of CarryOverProjectionRow, one per person and closing holiday year, sorted by emp_key and holiday_year. Fields of a row: emp_key,
        holiday_year, year_end_balance (days), country, next_holiday_year, basis, cap (days), projected_carry_in (days), stored_carry_in (days, None without a next year), difference (days, None
        without a stored value), matches (flag, None without a stored value), legal_status (status of the facts). Every field carries a description and a unit
        (CarryOverProjectionRow.columns()). result.to_frame() gives the DataFrame.

    Raises:
        FrameError: a frame lacks a required column, the entitlement frame has several rows for one person and holiday year, tolerance is not a number of zero or more, or a holiday year
            label matches no label format.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import fact
        >>> from halvaro.hr import carry_over_projection, holiday_ledger
        >>> cap = fact("legal.DK.holiday.carryover.default_max_days").value
        >>> ent = pd.DataFrame({"emp_key": ["EMP-1", "EMP-1"], "holiday_year": ["2026/27", "2027/28"], "carried_in_days": [0.0, cap],
        ...                     "carry_over_agreement": [False, False], "opening_balance": [False, False]})
        >>> acc = pd.DataFrame({"emp_key": ["EMP-1"], "holiday_year": ["2026/27"], "period": ["2027-08"], "accrued_days": [cap + 3.0], "taken_days": [0.0]})
        >>> projection = carry_over_projection(holiday_ledger(ent, acc), ent)
        >>> projection[0].projected_carry_in == cap, projection[0].matches
        (True, True)
    """
    if isinstance(ledger, LedgerRows):
        ledger = ledger.to_frame()
    _need(ledger, ["emp_key", "holiday_year", "period", "balance"], "holiday_ledger frame")
    _need(ent, ["emp_key", "holiday_year", "carried_in_days", "carry_over_agreement"], "hr.holiday_entitlement")
    if isinstance(tolerance, bool) or not isinstance(tolerance, (int, float)) or tolerance < 0:
        raise FrameError("tolerance must be a number of days, zero or more")
    if ent.duplicated(["emp_key", "holiday_year"]).any():
        raise FrameError("hr.holiday_entitlement has several rows for one person and holiday year; expected 1")
    last = ledger.sort_values(["emp_key", "holiday_year", "period"]).drop_duplicates(["emp_key", "holiday_year"], keep="last")[["emp_key", "holiday_year", "balance"]]
    out = last.rename(columns={"balance": "year_end_balance"}).copy()
    out["country"] = out["holiday_year"].map(_country_of_label)

    def nxt(label: str, country: str) -> str:
        y = int(str(label)[:4]) + 1
        return str(fact(_FORMAT.format(c=country)).value).format(y=y, y2=f"{(y + 1) % 100:02d}")

    out["next_holiday_year"] = [nxt(h, c) for h, c in zip(out["holiday_year"], out["country"])]
    flag = ent.set_index(["emp_key", "holiday_year"])["carry_over_agreement"]
    agreement = [bool(flag.get((e, h), False)) and c == "DK" for e, h, c in zip(out["emp_key"], out["holiday_year"], out["country"])]
    cap = {"DK": float(fact(_CAP.format(c="DK")).value), "DE": float(fact(_CAP.format(c="DE")).value)}
    agr = float(fact(_AGR).value)
    out["basis"] = ["agreement" if a else "default" for a in agreement]
    out["cap"] = [agr if a else cap[c] for a, c in zip(agreement, out["country"])]
    out["projected_carry_in"] = [round(min(max(float(b), 0.0), c), 2) for b, c in zip(out["year_end_balance"], out["cap"])]
    stored = ent.set_index(["emp_key", "holiday_year"])["carried_in_days"]
    out["stored_carry_in"] = [float(stored.get((e, h), float("nan"))) for e, h in zip(out["emp_key"], out["next_holiday_year"])]
    out["difference"] = (out["projected_carry_in"] - out["stored_carry_in"]).round(2)
    out["matches"] = pd.array([pd.NA if pd.isna(d) else bool(abs(d) <= tolerance + 1e-9) for d in out["difference"]], dtype="boolean")
    out["legal_status"] = _legal_status(*_CAPS, *_LABELS)
    return CarryOverProjectionRows.from_frame(out.sort_values(["emp_key", "holiday_year"]).reset_index(drop=True))


@function(sources=("hr.employee.emp_key", "hr.employee.hire_date", "hr.employee.leave_date", "hr.leave_record.emp_key", "hr.leave_record.leave_type", "hr.leave_record.start",
                   "hr.leave_record.end") + _ACC, facts=(_ACCR.format(c="DK"), _ACCR.format(c="DE"), _WINDOW) + _LABELS + _START_FACTS,
          oracle="py:halvaro_gen/world/leave.py::Builder._month_accrual")
def accrual_expected(employee: pd.DataFrame, leave_record: pd.DataFrame, acc: pd.DataFrame, now: dt.date, *, tolerance: float = 0.01,
                     non_accruing_types: tuple[str, ...] = ("extended_leave",)) -> AccrualRows:
    """Use this when you need the holiday accrual a person should have per month, to compare with the ledger and find months that are missing or differ.

    Rule: expected_days = monthly rate of the country of the holiday year (legal fact) x employed days of the month / days of the month, rounded to 2 decimals. Employed days run from the hire
    date to the leave date or `now`, whichever comes first, minus the days inside leave records of `non_accruing_types`. The result is not scaled by fte. Months that should exist (from the
    start of the holiday year, the hire date or the window start, to the end of the holiday year, the leave date or `now`) and are missing in `acc` come back as rows with accrued_days null
    and missing_month True. `tolerance` and `non_accruing_types` are proposed policy values. Simplification: only extended_leave is non-accruing by default; the ledger of the data accrues
    during parental leave too, so pass non_accruing_types=("extended_leave", "parental") to test the rule that it does not (known-defects.md D11).

    Args:
        employee: Frame hr.employee with emp_key, hire_date, leave_date (null while employed).
        leave_record: Frame hr.leave_record with emp_key, leave_type, start, end.
        acc: Accrual frame (hr.holiday_accrual) with emp_key, holiday_year, period (YYYY-MM), accrued_days.
        now: Last day that counts as employed (the data date).
        tolerance: Largest difference in days between stored and expected accrual that counts as within tolerance.
        non_accruing_types: leave_type values whose days do not accrue.

    Returns:
        AccrualRows: an immutable sequence of AccrualRow sorted by emp_key, holiday_year, period. Fields of a row: emp_key, holiday_year, period (YYYY-MM), accrued_days (days, None on a missing
        month), expected_days (days), missing_month (flag), difference (days, accrued minus expected, None on a missing month), within_tolerance (flag), legal_status (status of the facts).
        Every field carries a description and a unit (AccrualRow.columns()). result.to_frame() gives the DataFrame.

    Raises:
        FrameError: a frame lacks a required column, a person of `acc` is not in `employee`, or a holiday year label matches no label format.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.core import fact
        >>> from halvaro.hr import accrual_expected
        >>> rate = fact("legal.DK.holiday.accrual_days_per_month").value
        >>> employee = pd.DataFrame({"emp_key": ["EMP-1"], "hire_date": [dt.date(2020, 1, 1)], "leave_date": [None]})
        >>> leave_record = pd.DataFrame({"emp_key": [], "leave_type": [], "start": [], "end": []})
        >>> acc = pd.DataFrame({"emp_key": ["EMP-1"], "holiday_year": ["2026/27"], "period": ["2026-10"], "accrued_days": [rate]})
        >>> out = accrual_expected(employee, leave_record, acc, dt.date(2026, 10, 31))
        >>> [r.period for r in out], [r.missing_month for r in out], [r.within_tolerance for r in out]
        (['2026-09', '2026-10'], [True, False], [False, True])
        >>> all(r.expected_days == round(rate, 2) for r in out)
        True
    """
    _need(employee, ["emp_key", "hire_date", "leave_date"], "hr.employee")
    _need(leave_record, ["emp_key", "leave_type", "start", "end"], "hr.leave_record")
    _need(acc, ["emp_key", "holiday_year", "period", "accrued_days"], "hr.holiday_accrual")
    unknown = sorted(set(acc["emp_key"]) - set(employee["emp_key"]))
    if unknown:
        raise FrameError(f"{len(unknown)} people of the accrual frame are not in hr.employee (for example {unknown[0]})")
    emp = employee.set_index("emp_key")[["hire_date", "leave_date"]]
    unpaid: dict[Any, list[tuple[pd.Timestamp, pd.Timestamp]]] = {}
    for r in cast(Any, leave_record[leave_record["leave_type"].isin(list(non_accruing_types))].itertuples()):
        unpaid.setdefault(r.emp_key, []).append((pd.Timestamp(r.start), pd.Timestamp(r.end)))
    rate = {c: float(fact(_ACCR.format(c=c)).value) for c in ("DK", "DE")}
    nowt, w0 = pd.Timestamp(now), pd.Timestamp(fact(_WINDOW).value)

    def expected_days(emp_key: str, label: str, period: str) -> float:
        y, m = int(period[:4]), int(period[5:7])
        ms = pd.Timestamp(y, m, 1)
        me = ms + pd.offsets.MonthEnd(0)
        hire = pd.Timestamp(cast(Any, emp.at[emp_key, "hire_date"]))
        leave: Any = emp.at[emp_key, "leave_date"]
        lo, hi = max(ms, hire), min(me, pd.Timestamp(leave) if pd.notna(leave) else pd.Timestamp.max, nowt)
        days = max(0, (hi - lo).days + 1)
        for s, e in unpaid.get(emp_key, []):
            a, b = max(lo, s), min(hi, e)
            if b >= a:
                days -= (b - a).days + 1
        return round(rate[_country_of_label(label)] * max(0, days) / ((me - ms).days + 1), 2)

    out = acc[["emp_key", "holiday_year", "period", "accrued_days"]].copy()
    out["expected_days"] = [expected_days(r.emp_key, r.holiday_year, r.period) for r in cast(Any, out.itertuples())]
    out["missing_month"] = False
    stored = set(map(tuple, out[["emp_key", "holiday_year", "period"]].to_numpy()))
    extra = []
    for k, label in out[["emp_key", "holiday_year"]].drop_duplicates().itertuples(index=False):
        y0, y1 = holiday_year_bounds(label)
        leave_k: Any = emp.at[k, "leave_date"]
        a0 = max(pd.Timestamp(y0), pd.Timestamp(cast(Any, emp.at[k, "hire_date"])), w0)
        a1 = min(pd.Timestamp(y1), pd.Timestamp(leave_k) if pd.notna(leave_k) else pd.Timestamp.max, nowt)
        for p in pd.period_range(a0, a1, freq="M").strftime("%Y-%m") if a1 >= a0 else []:
            if (k, label, p) not in stored:
                extra.append({"emp_key": k, "holiday_year": label, "period": p, "accrued_days": float("nan"), "expected_days": expected_days(k, label, p), "missing_month": True})
    if extra:
        out = pd.concat([out, pd.DataFrame(extra)], ignore_index=True)
    out["difference"] = (out["accrued_days"] - out["expected_days"]).round(4)
    out["within_tolerance"] = (out["difference"].abs() <= tolerance + 1e-9) & ~out["missing_month"]
    out["legal_status"] = _legal_status(*(_ACCR.format(c=c) for c in ("DK", "DE")), *_LABELS)
    return AccrualRows.from_frame(out.sort_values(["emp_key", "holiday_year", "period"]).reset_index(drop=True))


@function(sources=("hr.leave_record.emp_key", "hr.leave_record.leave_type", "hr.leave_record.days", "hr.leave_record.end") + _ACC, facts=_START_FACTS + _LABELS,
          oracle="py:tests/test_leave.py::test_ledger_never_negative_and_matches_leave_records")
def leave_vs_ledger(leave_record: pd.DataFrame, acc: pd.DataFrame, now: dt.date, *, total_tolerance_days: float = 25.0) -> LeaveLedgerRows:
    """Use this when you need to check that the holiday leave records agree with the days taken in the ledger, per person and holiday year.

    Rule: holiday leave records (leave_type "holiday") that ended on or before `now` are placed in the holiday year of their end date, using the country of the person (read from the label of
    the person in `acc`), and summed per person and holiday year as leave_days. taken_days is the sum of taken_days in `acc`. difference = taken_days - leave_days. total_difference_days is the
    sum of all differences (the same value on every row) and within_total_tolerance is True when its size is at most `total_tolerance_days`. A record that straddles `now` is left out whole,
    while the ledger counts its days up to `now`. `total_tolerance_days` is a proposed policy value.

    Args:
        leave_record: Frame hr.leave_record with emp_key, leave_type, days, end.
        acc: Accrual frame (hr.holiday_accrual) with emp_key, holiday_year, taken_days.
        now: Last day that counts (the data date).
        total_tolerance_days: Largest size of the total difference, in days, that counts as within tolerance.

    Returns:
        LeaveLedgerRows: an immutable sequence of LeaveLedgerRow sorted by emp_key, holiday_year. Fields of a row: emp_key, holiday_year (None for a leave record of a person without ledger rows),
        leave_days (days), taken_days (days), difference (days), total_difference_days (days), within_total_tolerance (flag), legal_status (status of the facts). Every field carries a
        description and a unit (LeaveLedgerRow.columns()). result.to_frame() gives the DataFrame.

    Raises:
        FrameError: a frame lacks a required column, or a holiday year label in `acc` matches no label format.

    Example:
        >>> import datetime as dt
        >>> import pandas as pd
        >>> from halvaro.hr import leave_vs_ledger
        >>> leave_record = pd.DataFrame({"emp_key": ["EMP-1"], "leave_type": ["holiday"], "days": [3], "end": [dt.date(2026, 10, 9)]})
        >>> acc = pd.DataFrame({"emp_key": ["EMP-1", "EMP-1"], "holiday_year": ["2026/27", "2026/27"], "period": ["2026-09", "2026-10"], "taken_days": [1.0, 2.0]})
        >>> out = leave_vs_ledger(leave_record, acc, dt.date(2026, 11, 30))
        >>> [r.holiday_year for r in out], [r.difference for r in out], [r.within_total_tolerance for r in out]
        (['2026/27'], [0.0], [True])
    """
    _need(leave_record, ["emp_key", "leave_type", "days", "end"], "hr.leave_record")
    _need(acc, ["emp_key", "holiday_year", "taken_days"], "hr.holiday_accrual")
    country = acc.drop_duplicates("emp_key").set_index("emp_key")["holiday_year"].map(_country_of_label)
    h = leave_record[(leave_record["leave_type"] == "holiday") & (pd.to_datetime(leave_record["end"]) <= pd.Timestamp(now))].copy()
    h["country"] = h["emp_key"].map(country)
    h["holiday_year"] = [holiday_year_label(c, pd.Timestamp(e).date()) if isinstance(c, str) else None for c, e in zip(h["country"], h["end"])]
    leave = h.groupby(["emp_key", "holiday_year"], dropna=False)["days"].sum().rename("leave_days").reset_index()
    taken = acc.groupby(["emp_key", "holiday_year"])["taken_days"].sum().reset_index()
    out = leave.merge(taken, on=["emp_key", "holiday_year"], how="outer").fillna({"leave_days": 0.0, "taken_days": 0.0})
    out["difference"] = (out["taken_days"] - out["leave_days"]).round(2)
    total = float(out["difference"].sum())
    out["total_difference_days"] = total
    out["within_total_tolerance"] = abs(total) <= total_tolerance_days
    out["legal_status"] = _legal_status(*_START_FACTS, *_LABELS)
    return LeaveLedgerRows.from_frame(out.sort_values(["emp_key", "holiday_year"], na_position="last").reset_index(drop=True))


@function(sources=_ENT, facts=(*_LABELS, "policy.holiday.high_carry_over_days"))
def high_carry_over(ent: pd.DataFrame, holiday_year: str = "2026/27", country: str = "DK", threshold: float | PolicyDefault = PolicyDefault("policy.holiday.high_carry_over_days")) -> HighCarryOverRows:
    """Use this when you need the people who carry more holiday days into a holiday year than a threshold, so that a person can look at each of them.

    Rule: rows of the holiday year whose carried_in_days is strictly above the threshold, opening rows left out. The default threshold is the fact policy.holiday.high_carry_over_days (status
    proposed). When the default is used the result carries policy_status with the status of that fact (by fact id); a number given by the caller is used as it is and policy_status is empty. The flag is a hint for a look at one
    person, not a limit, and it is meant for the country given (default DK).

    Args:
        ent: Entitlement frame (hr.holiday_entitlement) with emp_key, holiday_year, carried_in_days, carry_over_agreement, opening_balance.
        holiday_year: Holiday year label to look at.
        country: "DK" or "DE". The label must be a label of this country.
        threshold: Days. Carried-in days above this value are listed. Default: the policy fact.

    Returns:
        HighCarryOverRows: an immutable sequence of HighCarryOverRow sorted by emp_key. Fields of a row: emp_key, holiday_year, carried_in_days (days), carry_over_agreement (flag),
        legal_status (status of the facts). Every field carries a description and a unit (HighCarryOverRow.columns()). result.to_frame() gives the DataFrame; result.policy_status is the
        status of the policy fact behind a default threshold.

    Raises:
        FrameError: the frame lacks a required column, or holiday_year is not a label of the given country.

    Example:
        >>> import pandas as pd
        >>> from halvaro.hr import high_carry_over
        >>> ent = pd.DataFrame({"emp_key": ["EMP-1", "EMP-2"], "holiday_year": ["2026/27", "2026/27"], "carried_in_days": [9.0, 2.0],
        ...                     "carry_over_agreement": [True, False], "opening_balance": [False, False]})
        >>> [row.emp_key for row in high_carry_over(ent, threshold=3.0)]
        ['EMP-1']
        >>> from halvaro.core import fact
        >>> dict(high_carry_over(ent).policy_status) == {'policy.holiday.high_carry_over_days': fact('policy.holiday.high_carry_over_days').status}
        True
    """
    _need(ent, ["emp_key", "holiday_year", "carried_in_days", "carry_over_agreement", "opening_balance"], "hr.holiday_entitlement")
    if _country_of_label(holiday_year) != country:
        raise FrameError(f"holiday year {holiday_year!r} is not a {country} label")
    used: dict[str, str] = {}
    threshold = policy_number(threshold, used)
    r = ent[(ent["holiday_year"] == holiday_year) & ~ent["opening_balance"].astype(bool) & (ent["carried_in_days"] > threshold)]
    out = r[["emp_key", "holiday_year", "carried_in_days", "carry_over_agreement"]].sort_values("emp_key").reset_index(drop=True)
    out["legal_status"] = _legal_status(*_LABELS)
    return HighCarryOverRows.from_frame(out, policy_status=used)
