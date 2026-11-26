"""Oracles of the input types of halvaro.core.format (lane P1): Decimal, Fraction, missing values, other types and numbers of many digits. The expected text is built with exact fractions
and written by hand; the library uses Decimal arithmetic."""
import random
from decimal import Decimal
from fractions import Fraction

import numpy as np
import pandas as pd
import pytest

import halvaro.core as core


def _text(value: Fraction, decimals: int) -> str:
    """Round half away from zero with thousands separators, built from an exact fraction; no minus sign for a result of zero."""
    n = int(abs(value) * 10 ** decimals + Fraction(1, 2))
    whole, frac = divmod(n, 10 ** decimals)
    out = f"{whole:,}" + (f".{frac:0{decimals}d}" if decimals else "")
    return ("-" if value < 0 and n != 0 else "") + out


def test_format_number_oracle_decimal_is_used_as_it_is_never_truncated():
    """halvaro.core.format.format_number: a Decimal is formatted with its own digits (Decimal("1.5") was cut to 1.0), by hand and for 2000 random decimals against exact fractions; a NaN Decimal is
    missing and an infinite one is refused."""
    table = [(Decimal("1.5"), 1, "1.5"), (Decimal("1234567.895"), 2, "1,234,567.90"), (Decimal("-2.5"), 0, "-3"), (Decimal("0.0049"), 2, "0.00"), (Decimal("-0.0049"), 2, "0.00"),
             (Decimal("999999.5"), 0, "1,000,000"), (Decimal("1E+3"), 0, "1,000"), (Decimal("12345678901234567890123456789012345.5"), 0, "12,345,678,901,234,567,890,123,456,789,012,346")]
    for x, d, want in table:
        assert core.format_number(x, d) == want, (x, d)
    rng = random.Random(1)
    for _ in range(2000):
        x = Decimal(rng.randint(-10**12, 10**12)).scaleb(-rng.randint(0, 8))
        d = rng.randint(0, 6)
        assert core.format_number(x, d) == _text(Fraction(x), d), (x, d)
    assert core.format_number(Decimal("NaN")) == "n/a"
    for bad in (Decimal("Infinity"), Decimal("-Infinity")):
        with pytest.raises(core.FrameError):
            core.format_number(bad)


def test_format_oracle_fraction_goes_through_numerator_over_denominator():
    """halvaro.core.format.format_number, format_percent and format_money: a Fraction is formatted as its quotient (Fraction(3, 2) was cut to 1), by hand and for 2000 random fractions against exact
    rounding; the percent of a share and a scaled amount follow the same rule."""
    assert core.format_number(Fraction(3, 2)) == "2" and core.format_number(Fraction(-5, 2)) == "-3" and core.format_number(Fraction(1, 3), 4) == "0.3333"
    assert core.format_percent(Fraction(1, 8), 1, ratio=True) == "12.5%" and core.format_percent(Fraction(1, 3), 2) == "0.33%"
    assert core.format_money(Fraction(5, 2), "EUR", decimals=1) == "EUR 2.5" and core.format_money(Fraction(3, 1000), "DKK", "k", 1) == "DKK 0.0k"
    rng = random.Random(2)
    for _ in range(2000):
        x = Fraction(rng.randint(-10**9, 10**9), rng.choice([1, 2, 3, 7, 8, 16, 125, 1000, 999]))
        d = rng.randint(0, 6)
        assert core.format_number(x, d) == _text(x, d), (x, d)
        assert core.format_percent(x, d) == _text(x, d) + "%", (x, d)
        assert core.format_percent(x, d, ratio=True) == _text(x * 100, d) + "%", (x, d)
        assert core.format_money(x, "SEK", "m", d) == "SEK " + _text(x / 10**6, d) + "m", (x, d)


@pytest.mark.parametrize("missing", [None, pd.NA, pd.NaT, float("nan"), np.nan, np.float32("nan"), Decimal("NaN")])
def test_format_oracle_every_kind_of_missing_number_is_n_a_never_an_error_or_zero(missing):
    """halvaro.core.format.format_number, format_percent and format_money: None, pd.NA, pd.NaT, NaN of float, numpy float and Decimal all give n/a (money keeps the currency); a nullable integer column
    formatted value by value no longer fails on its first null."""
    assert core.format_number(missing) == "n/a" and core.format_percent(missing) == "n/a" and core.format_money(missing, "EUR") == "EUR n/a"
    col = pd.Series([1, None, 3], dtype="Int64")
    assert [core.format_number(v) for v in col] == ["1", "n/a", "3"]


@pytest.mark.parametrize("bad", [{"a": 1}, pd.Timestamp("2026-01-01"), b"12", 1 + 2j, object(), np.datetime64("2026-01-01"), pd.Timedelta(days=1), np.timedelta64(1, "D"), [1], (1, 2), True, "5", Decimal("Infinity"), Decimal("-Infinity"), float("inf"), float("-inf")])
def test_format_oracle_a_value_that_is_not_one_number_is_refused_with_frame_error(bad):
    """halvaro.core.format.format_number, format_percent and format_money: a dict, a timestamp, bytes, a complex number, a plain object, a date, a time delta, a list, a tuple, a boolean, text and an infinite
    number raise FrameError (a dict, timestamp and others raised TypeError before)."""
    for call in (lambda: core.format_number(bad), lambda: core.format_percent(bad), lambda: core.format_money(bad, "DKK")):
        with pytest.raises(core.FrameError):
            call()


def test_format_oracle_numbers_of_many_digits_have_a_text_and_no_exception():
    """halvaro.core.format.format_number, format_percent and format_money: floats up to 1e300 and integers of 40 digits are formatted with every digit of their printed form (before: decimal.InvalidOperation above
    28 digits), against exact fractions."""
    rng = random.Random(3)
    for _ in range(1500):
        x = rng.uniform(-1, 1) * 10 ** rng.randint(0, 300)
        d = rng.randint(0, 6)
        assert core.format_number(x, d) == _text(Fraction(repr(x)), d), (x, d)
    big = 10**39 + 12345
    assert core.format_number(big) == f"{big:,}" and core.format_number(-big, 2) == f"-{big:,}.00"
    assert core.format_number(1e30, 3) == "1," + "000," * 9 + "000.000"
    assert core.format_percent(1e25, 1) == _text(Fraction(repr(1e25)), 1) + "%" and core.format_money(1e25, "EUR", "bn", 2) == "EUR 10,000,000,000,000,000.00bn"


def test_format_oracle_a_fraction_of_more_than_28_digits_is_not_cut():
    """halvaro.core.format.format_number, format_percent and format_money: a Fraction with 31 digits before the point, and one that needs 41 digits before the decimals, are formatted digit for digit (the
    expected text is built from integers)."""
    big = Fraction(10**30 + 1)
    assert core.format_number(big) == f"{10**30 + 1:,}" == "1,000,000,000,000,000,000,000,000,000,001"
    third = Fraction(10**40 + 1, 3)
    assert core.format_number(third, 2) == _text(third, 2) and core.format_percent(third, 2) == _text(third, 2) + "%"
    assert core.format_money(third, "EUR", decimals=2) == "EUR " + _text(third, 2) and core.format_money(third, "EUR", "m", 3) == "EUR " + _text(third / 10**6, 3) + "m"


def test_format_oracle_decimals_run_from_zero_to_six_and_scaled_money_defaults_to_one():
    """halvaro.core.format.format_number, format_percent and format_money: decimals 0 and 6 are fine, 7, -1, a boolean, a float and a text raise FrameError naming decimals; money without decimals shows 0
    decimals, and 1 decimal when scaled (k, m, bn), by hand."""
    assert core.format_number(1, 6) == "1.000000" and core.format_percent(1, 0) == "1%" and core.format_money(1, "DKK", decimals=6) == "DKK 1.000000"
    for bad in (7, -1, True, 1.5, "2"):
        for call in (lambda: core.format_number(1, bad), lambda: core.format_percent(1, bad), lambda: core.format_money(1, "DKK", decimals=bad)):
            with pytest.raises(core.FrameError, match="decimals"):
                call()
    assert core.format_money(1234567, "DKK") == "DKK 1,234,567"
    assert core.format_money(1234567, "DKK", "k") == "DKK 1,234.6k" and core.format_money(1234567, "DKK", "m") == "DKK 1.2m" and core.format_money(1234567, "DKK", "bn") == "DKK 0.0bn"
    assert core.format_money(1234567, "DKK", "m", 0) == "DKK 1m" and core.format_money(1234567, "DKK", "m", 3) == "DKK 1.235m"


def test_format_oracle_digits_are_kept_for_decimals_and_fractions_of_any_number_of_digits_that_end():
    """halvaro.core.format.format_number, format_percent and format_money: a Decimal of 86 significant digits formatted as a percent of a ratio, and a Fraction that is a whole number of 101 digits, keep every digit
    (the product and the quotient were rounded twice at 60 digits and cut at 80); the expected text is built from exact fractions."""
    d = Decimal("0.00004" + "9" * 80 + "5")
    assert core.format_percent(d, 2, ratio=True) == _text(Fraction(d) * 100, 2) + "%" == "0.00%"
    assert core.format_percent(Decimal("0.0000" + "4" * 5 + "9" * 80 + "5"), 6, ratio=True) == _text(Fraction(Decimal("0.0000" + "4" * 5 + "9" * 80 + "5")) * 100, 6) + "%"
    big = Fraction(10**100 + 1)
    assert core.format_number(big) == f"{10**100 + 1:,}" and core.format_money(big, "DKK") == f"DKK {10**100 + 1:,}"
    wide = Decimal("1" * 90 + ".5")
    assert core.format_number(wide) == _text(Fraction(wide), 0) == f"{int('1' * 90) + 1:,}"
