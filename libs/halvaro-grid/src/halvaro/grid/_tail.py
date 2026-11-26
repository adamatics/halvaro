"""The value an input error names (standard 3.7.5), kept short: the type of a frame, Series, array or mapping, else a repr cut to a bounded length."""
from __future__ import annotations

import reprlib
from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

_REPR = reprlib.Repr()
_REPR.maxstring = 80
_REPR.maxother = 80
_REPR.maxlong = 40
_REPR.maxlist = _REPR.maxtuple = _REPR.maxset = _REPR.maxfrozenset = _REPR.maxdict = 5
_REPR.maxlevel = 2


def value_text(value: Any) -> str:
    """The value received, as text for the tail of an error message: never the rows of a frame, never more than about 80 characters."""
    if isinstance(value, (pd.DataFrame, pd.Series, pd.Index, np.ndarray, Mapping)):
        return type(value).__name__
    if isinstance(value, int) and value.bit_length() > 128:  # about 39 digits: the type, not a long or cut number
        return type(value).__name__
    try:
        return _REPR.repr(value)
    except ValueError:  # an int with more digits than Python prints
        return type(value).__name__
