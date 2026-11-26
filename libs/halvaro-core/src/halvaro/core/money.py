"""Money basics: integer cents, rounding (to_cents rounds a tie to the even cent; rdiv and convert round a tie away from zero) and conversion at fixed rates."""
from __future__ import annotations

from typing import Any, Iterable

import numpy as np
import numpy.typing as npt
import pandas as pd

from . import snapshot
from .errors import BasisError, FrameError, SumGuardError
from .facts import fact
from .registry import function


def _arr(x: Any) -> npt.NDArray[Any]:
    return np.asarray(x)


@function(oracle="py:../libs/halvaro-core/tests/test_oracle_to_cents.py::test_to_cents_oracle_hand_worked_amounts_and_the_round_trip_with_from_cents")
def to_cents(amount: Any) -> Any:
    """Use this when you need an amount as whole cents, so that sums and comparisons are exact.

    Rule: the amount times 100 rounded to a whole number; a tie goes to the even cent (0.125 is 12.5 cents and gives 12). A null, an infinite amount or an amount whose cents do not fit in 64 bits is refused.

    Args:
        amount: One amount, a list or array of amounts, or a Series; the index of a Series is kept.

    Returns:
        The integer cents: a whole number for one amount, an array for an array, a Series for a Series.

    Raises:
        FrameError: an amount is null, infinite, or has cents that do not fit in 64 bits; the message says how many.

    Example:
        >>> from halvaro.core import to_cents
        >>> int(to_cents(1234.56)), int(to_cents(0.125)), int(to_cents(-0.125))
        (123456, 12, -12)
        >>> to_cents(float("nan"))
        Traceback (most recent call last):
        ...
        halvaro.core.errors.FrameError: to_cents got 1 null amount(s); cents are whole numbers and a null has no cents. Drop or fill the nulls first
    """
    raw = amount.to_numpy() if isinstance(amount, pd.Series) else _arr(amount)
    null = np.asarray(pd.isna(raw))
    if null.any():
        raise FrameError(f"to_cents got {int(null.sum())} null amount(s); cents are whole numbers and a null has no cents. Drop or fill the nulls first")
    f = raw.astype(float)
    if not np.isfinite(f).all():
        raise FrameError(f"to_cents got {int((~np.isfinite(f)).sum())} infinite amount(s); an infinite amount has no cents")
    cents = np.rint(f * 100)
    if (np.abs(cents) >= 2.0 ** 63).any():
        raise FrameError(f"to_cents got {int((np.abs(cents) >= 2.0 ** 63).sum())} amount(s) of more than 9.2e16 whose cents do not fit in 64 bits")
    out = cents.astype(np.int64)
    return pd.Series(out, index=amount.index) if isinstance(amount, pd.Series) else out


@function(oracle="py:../libs/halvaro-core/tests/test_oracle_cents.py::test_from_cents_oracle_hand_worked_cents")
def from_cents(cents: Any) -> Any:
    """Use this when you have whole cents and need the amount, with a missing value kept as missing.

    Rule: cents divided by 100. A null (None, NaN, pd.NA) stays NaN and is never turned into a number.

    Args:
        cents: One whole number of cents, a list or array of them, or a Series; the index of a Series is kept.

    Returns:
        The amounts as floats: a number for one value, an array for an array, a Series for a Series.

    Raises:
        This function raises no error of its own; a value that is not a number raises the error of numpy.

    Example:
        >>> from halvaro.core import from_cents
        >>> float(from_cents(123456))
        1234.56
    """
    raw = cents.to_numpy() if isinstance(cents, pd.Series) else _arr(cents)
    null = np.asarray(pd.isna(raw))
    out = (np.where(null, 0, raw) if null.any() else raw).astype(np.int64) / 100.0
    if null.any():
        out = np.where(null, np.nan, out)
    return pd.Series(out, index=cents.index) if isinstance(cents, pd.Series) else out


@function(oracle="py:../libs/halvaro-core/repo_tests/test_oracle_older_money_frames_org.py::test_rdiv_oracle_exact_fractions_round_half_away_from_zero")
def rdiv(a: Any, b: int) -> Any:
    """Use this when you divide whole cents by a whole number and the result must be whole cents too.

    Rule: integer division rounded half away from zero, so 7 divided by 2 is 4 and minus 7 divided by 2 is minus 4. The divisor should be positive; this is not checked, so a zero divisor gives 0 with a numpy warning.

    Args:
        a: The dividend, one whole number or an array of them.
        b: The divisor, a positive whole number.

    Returns:
        The quotient as whole numbers, of the shape of a.

    Raises:
        ValueError: a is a text or cannot be converted to numbers (the error of numpy when it converts the values).

    Example:
        >>> from halvaro.core import rdiv
        >>> int(rdiv(7, 2)), int(rdiv(-7, 2)), int(rdiv(6, 4))
        (4, -4, 2)
    """
    a = _arr(a).astype(np.int64)
    b = np.int64(b)
    if b <= 0:
        raise FrameError(f"rdiv divides by a positive whole number, not {int(b)}")
    return np.sign(a) * ((2 * np.abs(a) + b) // (2 * b))


@function(facts=("world.fx_eur_dkk_fixed", "world.fx_sek_dkk_fixed"), oracle="py:../libs/halvaro-core/repo_tests/test_oracle_older_money_frames_org.py::test_convert_oracle_the_generator_converter_and_exact_fractions_of_the_booking_rates")
def convert(cents: Any, from_currency: str, to_currency: str, *, basis: str) -> Any:
    """Use this when you move whole cents between DKK, EUR and SEK on a named basis.

    Rule: the booking basis uses the fixed booking rates of core; group_pay uses the fixed EUR to DKK rate of the fact world.fx_eur_dkk_fixed and knows DKK and EUR only. The cents are multiplied by the rate of the from currency and divided by the rate of the to currency with rdiv, so the result is rounded half away from zero. There is no default basis.

    Args:
        cents: Whole cents, one value, an array or a Series.
        from_currency: DKK, EUR or SEK.
        to_currency: DKK, EUR or SEK.
        basis: "booking" or "group_pay".

    Returns:
        The converted cents, of the shape of the input.

    Raises:
        BasisError: the basis is not available (the daily basis needs a rate frame), or a currency has no rate on the basis.

    Example:
        >>> from halvaro.core import convert, fact
        >>> rate = fact("world.fx_eur_dkk_fixed").value
        >>> int(convert(10000, "EUR", "DKK", basis="booking")) == round(10000 * rate), int(convert(500, "DKK", "DKK", basis="booking"))
        (True, 500)
        >>> convert(100, "DKK", "EUR", basis="daily")
        Traceback (most recent call last):
        ...
        halvaro.core.errors.BasisError: basis 'daily' is not available; use 'booking' or 'group_pay' (the daily basis needs a rate frame and comes with core 0.2)
    """
    if basis not in ("booking", "group_pay"):
        raise BasisError(f"basis {basis!r} is not available; use 'booking' or 'group_pay' (the daily basis needs a rate frame and comes with core 0.2)")
    rates = dict(snapshot.load()["fixed_rates"])
    if basis == "group_pay":
        rates = {"DKK": 100, "EUR": int(round(fact("world.fx_eur_dkk_fixed").value * 100))}
    c: Any
    for c in (from_currency, to_currency):
        if c not in rates:
            raise BasisError(f"currency {c!r} has no rate on basis {basis!r}; known: {', '.join(sorted(rates))}")
    c = _arr(cents).astype(np.int64)
    out = c if from_currency == to_currency else rdiv(c * rates[from_currency], rates[to_currency])
    return pd.Series(out, index=cents.index) if isinstance(cents, pd.Series) else out


@function(sources=(), oracle="py:../libs/halvaro-core/repo_tests/test_oracle_money_release.py::test_guarded_sum_oracle_baseline_invoices_by_currency_and_by_entity")
def guarded_sum(frame: pd.DataFrame, value: str, *, by: str | Iterable[str] = (), guard: str | Iterable[str] | None = None) -> pd.DataFrame:
    """Use this when you need the sum of an amount or quantity column and must be sure that no two currencies or units are added together.

    Rule: the value column is summed per group of the by columns as the plain sum of the stored numbers, with no rounding and no conversion to cents. Each guard column (default: currency, unit or both, whichever the frame has) may hold at most one distinct non null value inside each group; a group that mixes values is refused. Group on the guard column to get one sum per currency. Null values are skipped and an all null group sums to 0. Groups with a null key are kept.

    Args:
        frame: The rows to sum.
        value: The column to sum.
        by: The column or columns to group by, a name or a list. Optional; without it the result is one row with the sum of all rows.
        guard: The column or columns that must not mix inside a group. Optional; default currency and unit when the frame has them.

    Returns:
        pandas.DataFrame: the by columns followed by the value column, one row per group sorted by the by columns; one row with only the value column when by is empty.

    Raises:
        FrameError: the value column, a by column or a guard column is missing, or the frame has no guard column at all and none was named.
        SumGuardError: a group has more than one distinct value in a guard column.

    Example:
        >>> import pandas as pd
        >>> from halvaro.core import guarded_sum
        >>> frame = pd.DataFrame({"currency": ["DKK", "DKK", "EUR"], "amount": [1.5, 2.25, 4.0]})
        >>> guarded_sum(frame, "amount", by="currency")
          currency  amount
        0      DKK    3.75
        1      EUR    4.00
        >>> guarded_sum(frame, "amount")
        Traceback (most recent call last):
        ...
        halvaro.core.errors.SumGuardError: the rows to sum carry more than one currency (DKK, EUR); group by currency or convert first (core.convert).
    """
    by = [by] if isinstance(by, str) else list(by)
    guards = [guard] if isinstance(guard, str) else list(guard) if guard else [c for c in ("currency", "unit") if c in frame.columns]
    missing = [c for c in [value, *by, *guards] if c not in frame.columns]
    if missing or not guards:
        raise FrameError(f"guarded_sum needs the columns {value!r}, {by} and a currency or unit column; the frame lacks {missing or ['currency or unit']}. Pass guard= to name the column that must not mix.")
    for g in guards:
        if g in by:
            continue
        n = frame.groupby(by, dropna=False)[g].nunique(dropna=True) if by else pd.Series([frame[g].nunique(dropna=True)])
        if (n > 1).any():
            raise SumGuardError(f"the rows to sum carry more than one {g} ({', '.join(sorted(map(str, frame[g].dropna().unique())))}); group by {g} or convert first (core.convert).")
    if not by:
        return pd.DataFrame({value: [frame[value].sum()]})
    out = frame.groupby(by, dropna=False)[value].sum().reset_index()
    return out.sort_values(by, kind="stable").reset_index(drop=True)
