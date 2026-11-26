"""Type aliases of the public signatures (lane P3, #457): what a date, a time or a window argument accepts."""
from __future__ import annotations

import datetime as dt
from typing import Sequence, Union

import numpy as np
import pandas as pd

DateLike = Union[dt.date, pd.Timestamp, np.datetime64, str]
"""A day: a date, a datetime or Timestamp (read as its day) or an ISO text YYYY-MM-DD."""

TimesLike = Union[pd.Series, pd.Index, np.ndarray, Sequence[DateLike], DateLike]
"""One timestamp or many (a Series, an index, an array or a list)."""

Window = tuple[DateLike, DateLike]
"""First and last day, both included."""
