"""Oracle of halvaro.core.frames.reduce_chunks (lane L1): the grouped aggregates over chunks equal a plain Python loop over all rows, whatever the cut into chunks, and equal one pandas
groupby of the baseline."""
import math

import numpy as np
import pandas as pd
import pytest

import halvaro.core as core


def _ref(frame: pd.DataFrame, by: list, aggs: dict) -> list:
    """Rows (key tuple, outputs) from a loop over all rows: a missing key is its own group, sorted last; sum and count skip missing values, min and max of nothing are NaN."""
    groups: dict = {}
    for row in frame.to_dict("records"):
        key = tuple(None if pd.isna(row[b]) else row[b] for b in by)
        groups.setdefault(key, []).append(row)
    out = []
    for key in sorted(groups, key=lambda k: tuple((v is None, v if v is not None else 0) for v in k)):
        vals = {}
        for name, (col, fn) in aggs.items():
            xs = [r[col] for r in groups[key] if not pd.isna(r[col])]
            vals[name] = {"sum": sum(xs), "count": len(xs), "min": min(xs) if xs else math.nan, "max": max(xs) if xs else math.nan}[fn]
        out.append((key, vals))
    return out


def _frame(seed: int, n: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    f = pd.DataFrame({"g": rng.choice(["a", "b", "c", None], n), "h": rng.integers(1, 4, n), "x": rng.integers(-50, 50, n).astype(float), "y": rng.normal(0, 10, n)})
    f.loc[rng.random(n) < 0.15, "x"] = np.nan
    f.loc[f["g"] == "c", "y"] = np.nan                     # a group where y is missing everywhere
    return f


def _cut(frame: pd.DataFrame, seed: int) -> list:
    rng = np.random.default_rng(seed)
    cuts = sorted(rng.choice(np.arange(len(frame) + 1), size=int(rng.integers(1, 9)), replace=True).tolist())
    parts = [frame.iloc[a:b] for a, b in zip([0, *cuts], [*cuts, len(frame)])]
    assert sum(len(p) for p in parts) == len(frame)
    return [frame.iloc[0:0], *parts[:2], frame.iloc[0:0], *parts[2:], frame.iloc[0:0]]          # empty chunks first, in the middle and last, on purpose


AGGS = {"sx": ("x", "sum"), "nx": ("x", "count"), "lo": ("y", "min"), "hi": ("y", "max"), "sy": ("y", "sum"), "ny": ("y", "count")}


@pytest.mark.parametrize("seed", [1, 2, 3, 4])
@pytest.mark.parametrize("by", [["g"], ["g", "h"], ["h"], "g", []])
def test_reduce_chunks_oracle_loop_over_all_rows_for_any_cut_into_chunks(seed, by):
    """halvaro.core.frames.reduce_chunks: for four random chunkings (with empty chunks first, in the middle and last) crossed with five ways to group, a missing group key and an all missing group, the result equals the loop over all
    rows; the columns are the keys then the outputs in the order given; groups are sorted; the order of the chunks (reversed and a random permutation) does not matter."""
    frame = _frame(seed)
    keys = [by] if isinstance(by, str) else list(by)
    want = _ref(frame, keys, AGGS)
    chunks = _cut(frame, seed)
    got = core.reduce_chunks(iter(chunks), by, AGGS)
    assert list(got.columns) == [*keys, *AGGS]
    assert len(got) == len(want)
    for (key, vals), row in zip(want, got.to_dict("records")):
        assert tuple(None if pd.isna(row[k]) else row[k] for k in keys) == key
        for name, v in vals.items():
            assert row[name] == pytest.approx(v, nan_ok=True), (key, name)
    order = np.random.default_rng(seed + 100).permutation(len(chunks))
    pd.testing.assert_frame_equal(got, core.reduce_chunks(list(reversed(chunks)), by, AGGS))
    pd.testing.assert_frame_equal(got, core.reduce_chunks([chunks[i] for i in order], by, AGGS))
    pd.testing.assert_frame_equal(got, core.reduce_chunks([frame], by, AGGS))


def test_reduce_chunks_oracle_empty_chunks_no_chunk_and_wrong_columns():
    """halvaro.core.frames.reduce_chunks: only empty chunks give an empty frame with the output columns, no chunk at all is refused, a chunk without a needed column is refused with its number,
    and an unknown function name is refused before anything is read."""
    empty = pd.DataFrame({"g": pd.Series(dtype=object), "x": pd.Series(dtype=float)})
    got = core.reduce_chunks([empty, empty], "g", {"s": ("x", "sum")})
    assert got.empty and list(got.columns) == ["g", "s"]
    with pytest.raises(core.FrameError, match="no chunk"):
        core.reduce_chunks([], "g", {"s": ("x", "sum")})
    good = pd.DataFrame({"g": ["a"], "x": [1.0]})
    with pytest.raises(core.FrameError, match="chunk 2"):
        core.reduce_chunks([good, good.drop(columns="x")], "g", {"s": ("x", "sum")})
    def never():
        raise AssertionError("the chunks were read")
        yield good
    with pytest.raises(core.FrameError, match="median"):
        core.reduce_chunks(never(), "g", {"s": ("x", "median")})
    before = good.copy()
    core.reduce_chunks([good], "g", {"s": ("x", "sum")})
    pd.testing.assert_frame_equal(good, before)
