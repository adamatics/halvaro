"""Violation frames returned by the checkers."""
from __future__ import annotations

from typing import Iterable

import pandas as pd

COLUMNS = ["table", "key", "rule", "detail"]


def frame(rows: Iterable[Iterable[object]]) -> pd.DataFrame:
    """A violation frame (table, key, rule, detail) in a stable order."""
    df = pd.DataFrame(list(rows), columns=COLUMNS)
    return df.sort_values(COLUMNS, kind="stable").reset_index(drop=True)
