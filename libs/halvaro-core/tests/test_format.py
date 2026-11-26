"""Text formats (plan 5.10, section 7): half away from zero, thousands separator, currency code first, no scientific notation, no long dash."""
import numpy as np
import pandas as pd
import pytest

import halvaro.core as core
from halvaro.core import FrameError


def test_format_number_rounds_half_away_from_zero_and_never_uses_scientific_notation():
    assert [core.format_number(x) for x in (0.5, 1.5, 2.5, -0.5, -1.5, -2.5)] == ["1", "2", "3", "-1", "-2", "-3"]
    assert core.format_number(1234567.5) == "1,234,568" and core.format_number(-1234.565, 2) == "-1,234.57" and core.format_number(2.675, 2) == "2.68"
    assert core.format_number(1e12) == "1,000,000,000,000" and core.format_number(1e-7, 6) == "0.000000" and core.format_number(-0.4) == "0"
    assert core.format_number(np.float64(1234.5), 1) == "1,234.5" and core.format_number(np.int64(12345)) == "12,345" and core.format_number(12345) == "12,345"
    assert core.format_number(None) == "n/a" and core.format_number(np.nan) == "n/a"
    assert "—" not in core.format_number(-5) and "–" not in core.format_number(-5)


def test_format_number_refuses_what_is_not_one_number():
    for bad in ("12", [1, 2], pd.Series([1.0]), True, np.inf):
        with pytest.raises(FrameError):
            core.format_number(bad)
    with pytest.raises(FrameError, match="decimals"):
        core.format_number(1.0, 9)
    with pytest.raises(FrameError, match="decimals"):
        core.format_number(1.0, True)


def test_format_percent_takes_percent_or_a_ratio():
    assert core.format_percent(12.345) == "12.3%" and core.format_percent(12.35, 1) == "12.4%" and core.format_percent(-0.05, 1) == "-0.1%"
    assert core.format_percent(0.12345, ratio=True) == "12.3%" and core.format_percent(1.5, 0, ratio=True) == "150%" and core.format_percent(None) == "n/a"


def test_format_money_has_the_currency_code_first_and_the_scales():
    assert core.format_money(1234567.5, "DKK") == "DKK 1,234,568"
    assert core.format_money(1234567.5, "DKK", "m") == "DKK 1.2m" and core.format_money(1234567.5, "EUR", "k") == "EUR 1,234.6k"
    assert core.format_money(-2.5e9, "SEK", "bn") == "SEK -2.5bn" and core.format_money(1234.5, "DKK", decimals=2) == "DKK 1,234.50"
    assert core.format_money(np.nan, "EUR") == "EUR n/a"
    for bad in (("USD", None), ("DKK", "t")):
        with pytest.raises(FrameError):
            core.format_money(1.0, bad[0], bad[1])
    with pytest.raises(FrameError, match="one number"):
        core.format_money(pd.Series([1.0, 2.0]), "DKK")


def test_labels_are_fixed_texts_and_registered():
    assert core.synthetic_label() == "synthetic data"
    assert core.map_label() == "synthetic data; © OpenStreetMap contributors"
    ids = {k.split(".")[-1] for k in core.registered() if k.startswith("halvaro.core.format.") or k.startswith("halvaro.core.theme.")}
    assert {"format_number", "format_percent", "format_money", "synthetic_label", "map_label"} <= ids
