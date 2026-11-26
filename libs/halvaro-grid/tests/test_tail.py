"""The tail of an input error names the value received, kept short (lane W2, second round of #531 and #518): never the rows of a frame, never a different error class."""
import pandas as pd
import pytest

from halvaro.grid._tail import value_text


def test_short_values_print_as_their_repr():
    for v in (0, -3.0, "week", ("a", "b"), None, True):
        assert value_text(v) == repr(v)


def test_a_frame_a_series_or_a_mapping_gives_its_type_not_its_rows():
    frame = pd.DataFrame({"x": range(5000)})
    assert value_text(frame) == "DataFrame"
    assert value_text(frame["x"]) == "Series"
    assert value_text({"a": 1}) == "dict"


def test_a_long_text_is_cut_and_an_int_too_long_to_print_gives_its_type():
    assert len(value_text("x" * 5000)) < 100
    assert value_text(10 ** 5000) == "int"
