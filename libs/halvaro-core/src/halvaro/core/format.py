"""Text formats for tables and charts (plan 5.10, section 7): English locale, thousands separator, rounding half away from zero (the ledger rule), no scientific notation, currency code first, never one figure
for two currencies. A missing number is the text 'n/a', never 0 and never an empty cell."""
from __future__ import annotations

import decimal
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from typing import Any

import numpy as np
import pandas as pd

from .errors import FrameError
from .registry import function

CURRENCIES = ("DKK", "EUR", "SEK")
_SCALE = {None: (Decimal(1), ""), "k": (Decimal(10) ** 3, "k"), "m": (Decimal(10) ** 6, "m"), "bn": (Decimal(10) ** 9, "bn")}
NA = "n/a"


def _scalar(x: Any, what: str) -> Decimal | None:
    """One number as a Decimal; None, NaN, pd.NA, pd.NaT and a NaN Decimal are missing (None); anything that is not one finite number raises FrameError."""
    if x is None or x is pd.NA or x is pd.NaT:
        return None
    if isinstance(x, (bool, np.bool_, str, bytes, np.timedelta64)) or np.ndim(x) != 0:
        raise FrameError(f"{what} takes one number, not {type(x).__name__}; format each value (a figure never mixes two currencies)")
    if isinstance(x, Decimal):
        if x.is_nan():
            return None
        if x.is_infinite():
            raise FrameError(f"{what} got an infinite number")
        return x
    if isinstance(x, Fraction):
        with decimal.localcontext() as ctx:
            ctx.prec = max(80, len(str(abs(x.numerator))) + 30)                  # every digit of a whole number; a quotient that does not end is taken at 80 digits or more
            return Decimal(x.numerator) / Decimal(x.denominator)
    if isinstance(x, (float, np.floating)):
        if np.isnan(x):
            return None
        if not np.isfinite(x):
            raise FrameError(f"{what} got an infinite number")
        return Decimal(repr(float(x)))
    if isinstance(x, (int, np.integer)):
        return Decimal(int(x))
    raise FrameError(f"{what} takes one number (int, float, Decimal or Fraction), not {type(x).__name__}; format each value")


def _decimals(decimals: Any, what: str) -> int:
    if isinstance(decimals, bool) or not isinstance(decimals, (int, np.integer)) or not 0 <= decimals <= 6:
        raise FrameError(f"{what}: decimals must be a whole number from 0 to 6")
    return int(decimals)


def _wide(d: Decimal, decimals: int) -> Any:
    """A decimal context with room for every digit of `d` (as many as it has, with 20 to spare), of the rounded text and of the product by 100 or the quotient by a power of ten (the default of 28 digits raised InvalidOperation for large numbers and rounded long integers)."""
    ctx = decimal.Context(prec=max(60, len(d.as_tuple().digits) + max(d.adjusted(), 0) + decimals + 20))
    return decimal.localcontext(ctx)


def _text(d: Decimal, decimals: int) -> str:
    with _wide(d, decimals):
        q = d.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)          # ROUND_HALF_UP rounds half away from zero
        s = f"{abs(q):,.{decimals}f}"
    return ("-" if q < 0 else "") + s


@function(sources=(), oracle="py:../libs/halvaro-core/tests/test_oracle_format.py::test_format_number_oracle_exact_fractions_for_random_floats_and_decimals")
def format_number(x: Any, decimals: int = 0) -> str:
    """Use this when you write a number into a text, a table or a figure label.

    Rule: thousands separator comma, decimal point, rounding half away from zero, a minus sign and no scientific notation. None and NaN give n/a.

    Args:
        x: One number; None and NaN are allowed.
        decimals: The number of decimals, a whole number from 0 to 6. Default 0.

    Returns:
        str: the text, for example 1,235 for 1234.5 with no decimals.

    Raises:
        FrameError: x is not one number (a list or a text), or decimals is not a whole number from 0 to 6.

    Example:
        >>> from halvaro.core import format_number
        >>> format_number(1234.5, 1), format_number(-1234567.891), format_number(None)
        ('1,234.5', '-1,234,568', 'n/a')
    """
    d, n = _scalar(x, "format_number"), _decimals(decimals, "format_number")
    return NA if d is None else _text(d, n)


@function(sources=(), oracle="py:../libs/halvaro-core/tests/test_oracle_format.py::test_format_percent_oracle_exact_fractions_and_hand_worked_table")
def format_percent(x: Any, decimals: int = 1, *, ratio: bool = False) -> str:
    """Use this when you write a percentage into a text, a table or a figure label.

    Rule: the number with the sign %. x is already in percent (12.345 gives 12.3%); with ratio=True x is a share (0.12345 gives 12.3%). Rounding half away from zero. None and NaN give n/a.

    Args:
        x: One number; None and NaN are allowed.
        decimals: The number of decimals, a whole number from 0 to 6. Default 1.
        ratio: True when x is a share of one and not a percent. Default False.

    Returns:
        str: the text with the percent sign.

    Raises:
        FrameError: x is not one number, or decimals is not a whole number from 0 to 6.

    Example:
        >>> from halvaro.core import format_percent
        >>> format_percent(12.345), format_percent(0.256, ratio=True), format_percent(None)
        ('12.3%', '25.6%', 'n/a')
    """
    d, n = _scalar(x, "format_percent"), _decimals(decimals, "format_percent")
    if d is None:
        return NA
    with _wide(d, n):
        shown = d * 100 if ratio else d
    return _text(shown, n) + "%"


@function(sources=(), oracle="py:../libs/halvaro-core/tests/test_oracle_format.py::test_format_money_oracle_currency_first_scales_and_exact_fractions")
def format_money(amount: Any, currency: str, scale: str | None = None, decimals: int | None = None) -> str:
    """Use this when you write one amount of one currency into a text, a table or a figure label.

    Rule: the currency code, a space and the amount rounded half away from zero; with scale k, m or bn the amount is divided by a thousand, a million or a billion and the letter is appended. Decimals default to 0, or 1 when scaled. A sum over two currencies is refused upstream (see guarded_sum).

    Args:
        amount: One number; None and NaN give n/a.
        currency: DKK, EUR or SEK.
        scale: None, "k", "m" or "bn".
        decimals: The number of decimals, a whole number from 0 to 6. Default 0, or 1 with a scale.

    Returns:
        str: the text, for example DKK 1,235.

    Raises:
        FrameError: the currency is not DKK, EUR or SEK, the scale is not allowed, or amount is not one number.

    Example:
        >>> from halvaro.core import format_money
        >>> format_money(1234.5, "DKK"), format_money(1234567.0, "EUR", "m")
        ('DKK 1,235', 'EUR 1.2m')
        >>> format_money(1.0, "XXX")
        Traceback (most recent call last):
        ...
        halvaro.core.errors.FrameError: currency 'XXX' is not one of DKK, EUR, SEK
    """
    if currency not in CURRENCIES:
        raise FrameError(f"currency {currency!r} is not one of {', '.join(CURRENCIES)}")
    if scale not in _SCALE:
        raise FrameError("scale must be None, 'k', 'm' or 'bn'")
    d = _scalar(amount, "format_money")
    n = _decimals(1 if scale and decimals is None else 0 if decimals is None else decimals, "format_money")
    if d is None:
        return f"{currency} {NA}"
    div, suffix = _SCALE[scale]
    with _wide(d, n):
        shown = d / div
    return f"{currency} {_text(shown, n)}{suffix}"
