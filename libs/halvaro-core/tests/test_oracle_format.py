"""Property oracles of halvaro.core.format (lane L1): format_number, format_percent and format_money. The expected text is built with exact fractions (the printed decimal of a float is the
value that is rounded, half away from zero) and written out by hand; the library uses Decimal quantize."""
import random
from fractions import Fraction

import numpy as np
import pandas as pd
import pytest

import halvaro.core as core


def _text(value: Fraction, decimals: int) -> str:
    """The format of the module, built from a fraction: round half away from zero, thousands separator, no minus sign for a result of zero."""
    scaled = abs(value) * 10 ** decimals
    n = int(scaled + Fraction(1, 2))                                         # floor of x + 1/2 for x >= 0 is half away from zero
    whole, frac = divmod(n, 10 ** decimals)
    out = f"{whole:,}" + (f".{frac:0{decimals}d}" if decimals else "")
    return ("-" if value < 0 and n != 0 else "") + out


def _random_floats(seed: int, n: int) -> list:
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        kind = rng.choice(["cents", "wide", "tiny", "half", "int"])
        out.append({"cents": round(rng.uniform(-1e7, 1e7), 2), "wide": rng.uniform(-1e12, 1e12), "tiny": rng.uniform(-1, 1) * 10 ** rng.randint(-8, 0),
                    "half": rng.randint(-100000, 100000) / 2, "int": float(rng.randint(-10**9, 10**9))}[kind])
    return out


def test_format_number_oracle_exact_fractions_for_random_floats_and_decimals():
    """halvaro.core.format.format_number: for 1000 random floats and every number of decimals from 0 to 6 the text equals the one built from the exact decimal value of the float's printed form."""
    for x in _random_floats(1, 1000):
        for d in range(7):
            assert core.format_number(x, d) == _text(Fraction(repr(x)), d), (x, d)
    for x in (0.5, 1.5, 2.5, -0.5, -1.5, -2.5, 0.125, 0.135, 1e-7):
        assert core.format_number(x, 0) == _text(Fraction(repr(x)), 0)


def test_format_number_oracle_hand_worked_table():
    """halvaro.core.format.format_number: half goes away from zero, no minus sign for a rounded zero, big numbers have separators and no exponent, and None and NaN are n/a, never 0."""
    table = [(1234567.5, 0, "1,234,568"), (0.5, 0, "1"), (1.5, 0, "2"), (2.5, 0, "3"), (-0.5, 0, "-1"), (-2.5, 0, "-3"), (0.4, 0, "0"), (-0.4, 0, "0"), (12.345, 2, "12.35"),
             (-12.345, 2, "-12.35"), (1e21, 0, "1,000,000,000,000,000,000,000"), (1e-7, 6, "0.000000"), (999999.995, 2, "1,000,000.00"), (0, 0, "0"), (7, 2, "7.00"),
             (np.int64(-1234), 0, "-1,234"), (np.float64(1234.5), 0, "1,235"), (None, 0, "n/a"), (float("nan"), 3, "n/a"), (np.nan, 0, "n/a")]
    for x, d, want in table:
        assert core.format_number(x, d) == want, (x, d)
    for x in (1e21, 123456789012345678, -1e20, 1e-9):
        assert "e" not in core.format_number(x, 3).lower()


def test_format_number_oracle_parse_back_symmetry_and_order():
    """halvaro.core.format.format_number: the text read back as an exact fraction is within half a unit of the last decimal of the number, the text of -x is the text of x with the minus sign
    moved (a rounded zero has none), and a larger number never gives a smaller value."""
    xs = sorted(_random_floats(2, 1500))
    for d in (0, 2, 4):
        back = [Fraction(core.format_number(x, d).replace(",", "")) for x in xs]
        assert all(abs(b - Fraction(repr(x))) <= Fraction(1, 2) * Fraction(1, 10 ** d) for b, x in zip(back, xs)), d
        assert back == sorted(back), "ordered input stays ordered"
        for x in xs[::25]:
            t, m = core.format_number(x, d), core.format_number(-x, d)
            if Fraction(t.replace(",", "")) == 0:
                assert t.lstrip("-") == m.lstrip("-") and "-" not in t and "-" not in m, (x, d)
            else:
                assert m == (t[1:] if t.startswith("-") else "-" + t), (x, d)


@pytest.mark.parametrize("bad", ["5", True, [1, 2], np.array([1, 2]), pd.Series([1.0]), float("inf"), float("-inf"), (1,)])
def test_format_oracle_a_value_that_is_not_one_finite_number_is_refused(bad):
    """halvaro.core.format.format_number, format_percent and format_money: text, booleans, lists, arrays, series and infinite numbers raise FrameError; a column is formatted value by value."""
    for call in (lambda: core.format_number(bad), lambda: core.format_percent(bad), lambda: core.format_money(bad, "DKK")):
        with pytest.raises(core.FrameError):
            call()


@pytest.mark.parametrize("decimals", [-1, 7, 1.5, True, "1"])
def test_format_oracle_decimals_outside_zero_to_six_are_refused(decimals):
    """halvaro.core.format.format_number, format_percent and format_money: decimals must be a whole number from 0 to 6; None is the default only for format_money."""
    for call in (lambda: core.format_number(1.0, decimals), lambda: core.format_percent(1.0, decimals), lambda: core.format_money(1.0, "EUR", decimals=decimals)):
        with pytest.raises(core.FrameError):
            call()
    with pytest.raises(core.FrameError):
        core.format_number(1.0, None)
    assert core.format_money(1.0, "EUR", decimals=None) == "EUR 1", "None means the default number of decimals for money"


def test_format_percent_oracle_exact_fractions_and_hand_worked_table():
    """halvaro.core.format.format_percent: the percent is the number itself, or the share times 100 with ratio=True, rounded half away from zero with a % sign; the table is by hand and the
    random cases use exact fractions."""
    table = [(12.345, 1, False, "12.3%"), (12.35, 1, False, "12.4%"), (0.12345, 1, True, "12.3%"), (0.125, 0, True, "13%"), (-0.125, 0, True, "-13%"), (100, 0, False, "100%"),
             (1, 2, True, "100.00%"), (0, 1, False, "0.0%"), (-0.04, 0, False, "0%"), (1234.5, 0, False, "1,235%")]
    for x, d, ratio, want in table:
        assert core.format_percent(x, d, ratio=ratio) == want, (x, d, ratio)
    assert core.format_percent(None) == "n/a" and core.format_percent(float("nan"), ratio=True) == "n/a"
    rng = random.Random(4)
    for _ in range(1500):
        k, d = rng.randint(-2_000_000, 2_000_000), rng.randint(0, 4)
        assert core.format_percent(k / 10000, d, ratio=True) == _text(Fraction(k, 100), d) + "%", (k, d)
        assert core.format_percent(k / 100, d) == _text(Fraction(k, 100), d) + "%", (k, d)


def test_format_money_oracle_currency_first_scales_and_exact_fractions():
    """halvaro.core.format.format_money: the currency code comes first, k, m and bn divide by a thousand, a million and a billion and append the letter, decimals default to 0 or 1 when scaled; the
    random cases use exact fractions and the table is by hand."""
    table = [(1234567.5, "DKK", None, None, "DKK 1,234,568"), (1234567, "DKK", "m", None, "DKK 1.2m"), (1234567, "DKK", "k", None, "DKK 1,234.6k"), (2.5e9, "EUR", "bn", None, "EUR 2.5bn"),
             (1234567, "SEK", "m", 3, "SEK 1.235m"), (-1000, "EUR", None, None, "EUR -1,000"), (0, "SEK", None, None, "SEK 0"), (49999, "DKK", "k", 0, "DKK 50k"), (-49500, "DKK", "k", 0, "DKK -50k"),
             (None, "DKK", None, None, "DKK n/a"), (float("nan"), "EUR", "m", None, "EUR n/a")]
    for amount, cur, scale, dec, want in table:
        assert core.format_money(amount, cur, scale, dec) == want, (amount, cur, scale, dec)
    div = {None: (1, ""), "k": (10**3, "k"), "m": (10**6, "m"), "bn": (10**9, "bn")}
    rng = random.Random(6)
    for x in _random_floats(3, 800):
        scale, cur, d = rng.choice(list(div)), rng.choice(["DKK", "EUR", "SEK"]), rng.randint(0, 4)
        n, suffix = div[scale]
        assert core.format_money(x, cur, scale, d) == f"{cur} {_text(Fraction(repr(x)) / n, d)}{suffix}", (x, cur, scale, d)


@pytest.mark.parametrize("currency", ["USD", "dkk", "", None, "DKK ", "NOK"])
def test_format_money_oracle_only_dkk_eur_and_sek_are_accepted(currency):
    """halvaro.core.format.format_money: any other currency text, a lower case code or no currency raises FrameError, also for a missing amount; an unknown scale is refused."""
    for amount in (1.0, None):
        with pytest.raises(core.FrameError):
            core.format_money(amount, currency)
    with pytest.raises(core.FrameError):
        core.format_money(1.0, "DKK", scale="x")
