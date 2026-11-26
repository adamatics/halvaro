"""Property style tests of the core modules access, frames, testing and theme (standard 3.2.3, lane W1, issue #504).

Seeded random inputs, no extra package. Each rule is written from the documented behaviour of the function (the Rule or Returns text of its docstring) and never from its body.
"""
import datetime as dt
import random

import numpy as np
import pandas as pd
import pytest

import halvaro.core as core
from halvaro.core import Context, snapshot

STAGES = ("day1", "month3", "month12")


def rng(seed: int) -> random.Random:
    return random.Random(20261120 + seed)


# ---------------------------------------------------------------- access
def test_visible_sources_are_monotone_in_the_stage_and_agree_with_source_stage():
    """visible_sources(stage) is cumulative: a source is visible at a stage exactly when its own stage (source_stage) is that stage or an earlier one."""
    sources = sorted(snapshot.load()["stages"])
    seen = [core.visible_sources(s) for s in STAGES]
    assert seen[0] <= seen[1] <= seen[2] and seen[0] and seen[2] == frozenset(sources)
    order = {s: i for i, s in enumerate(STAGES)}
    for stage in STAGES:
        for source in sources:
            assert (source in core.visible_sources(stage)) == (order[core.source_stage(source)] <= order[stage]), (stage, source)


def test_require_sources_property_it_refuses_exactly_the_sources_above_the_stage():
    """require_sources raises StageRefusal exactly when a source is above the stage of the context, for any random choice of sources."""
    r = rng(1)
    sources = sorted(snapshot.load()["stages"])
    order = {s: i for i, s in enumerate(STAGES)}
    for _ in range(100):
        stage, picked = r.choice(STAGES), r.sample(sources, r.randint(1, 4))
        above = [s for s in picked if order[core.source_stage(s)] > order[stage]]
        ctx = Context(stage=stage, role="analyst")
        if above:
            with pytest.raises(core.StageRefusal):
                core.require_sources(ctx, picked)
        else:
            core.require_sources(ctx, picked)


def test_strip_restricted_is_idempotent_keeps_the_order_and_leaves_the_input_alone():
    r = rng(2)
    restricted = sorted(snapshot.load()["restricted_columns"])
    for _ in range(40):
        cols = r.sample(["emp_key", "team_key", "hire_date", "role_key"] + [c.rsplit(".", 1)[-1] for c in restricted] + restricted[:2], r.randint(2, 6))
        frame = pd.DataFrame({c: [1, 2] for c in dict.fromkeys(cols)})
        before = frame.copy()
        once = core.strip_restricted(frame, Context(stage="day1", role="analyst"))
        assert frame.equals(before) and list(once.columns) == [c for c in frame.columns if c in once.columns]
        assert core.strip_restricted(once, Context(stage="day1", role="analyst")).equals(once)
        kept = core.strip_restricted(frame, Context(stage="day1", role="analyst", restricted_ok=True))
        assert kept.equals(frame) and len(once.columns) <= len(frame.columns)
        bare = {c.rsplit(".", 1)[-1] for c in restricted}
        assert all(str(c).rsplit(".", 1)[-1] not in bare for c in once.columns)                          # nothing restricted is left
        assert [c for c in frame.columns if str(c).rsplit(".", 1)[-1] not in bare] == list(once.columns)  # everything else is kept


# ---------------------------------------------------------------- frames
def keyed(r: random.Random, n: int, pool: str) -> pd.DataFrame:
    return pd.DataFrame({"k": [r.choice(pool) for _ in range(n)], "v": range(n)})


def test_join_report_symmetry_swapping_the_frames_swaps_the_counts_of_the_keys_without_a_partner():
    """Symmetry: the keys only on the left of (a, b) are the keys only on the right of (b, a); and a left join keeps every left row."""
    r = rng(3)
    for _ in range(60):
        a, b = keyed(r, r.randint(1, 15), "ABCDEFG"), keyed(r, r.randint(1, 15), "EFGHIJK").drop_duplicates("k")
        ab, ba = core.join_report(a, b, on="k"), core.join_report(b, a, on="k")
        assert ab.report.counts["left_only_keys"] == ba.report.counts["right_only_keys"]
        assert ab.report.counts["right_only_keys"] == ba.report.counts["left_only_keys"]
        assert len(ab.frame) == len(a)                                                                # a left join with a unique right keeps the rows of the left
        assert ab.report.counts["left_only_keys"] == len(set(a["k"]) - set(b["k"]))


def test_join_report_is_invariant_under_the_order_of_the_rows_and_leaves_the_inputs_alone():
    r = rng(4)
    for _ in range(40):
        a, b = keyed(r, 12, "ABCDEF"), keyed(r, 8, "DEFGHI").drop_duplicates("k")
        before = (a.copy(), b.copy())
        first = core.join_report(a, b, on="k")
        assert a.equals(before[0]) and b.equals(before[1])
        again = core.join_report(a.sample(frac=1, random_state=r.randint(0, 99)), b.sample(frac=1, random_state=r.randint(0, 99)), on="k")
        assert first.report.counts == again.report.counts and sorted(first.frame["v"]) == sorted(again.frame["v"])


def test_reduce_chunks_sum_of_the_parts_equals_the_whole_whatever_way_the_rows_are_cut():
    """Splitting a frame into chunks and reducing the chunks gives the aggregate of the whole frame (sum of parts equals total)."""
    r = rng(5)
    for _ in range(40):
        frame = pd.DataFrame({"g": [r.choice("ab") for _ in range(30)], "x": [r.randint(0, 9) for _ in range(30)]})
        cuts = sorted(r.sample(range(1, 30), r.randint(1, 4)))
        chunks = [frame.iloc[i:j] for i, j in zip([0, *cuts], [*cuts, 30])]
        whole = core.reduce_chunks([frame], "g", {"x": ("x", "sum")}).sort_index()
        parts = core.reduce_chunks(chunks, "g", {"x": ("x", "sum")}).sort_index()
        assert whole.equals(parts) and int(parts["x"].sum()) == int(frame["x"].sum())


# ---------------------------------------------------------------- testing
def test_asof_stable_property_rows_after_the_date_do_not_matter_and_an_earlier_change_fails():
    r = rng(6)
    day = dt.date(2026, 3, 1)

    def call(frames, as_of):
        t = frames["t"]
        return t[pd.to_datetime(t["d"]) <= pd.Timestamp(as_of)]

    for _ in range(30):
        base = pd.DataFrame({"k": [f"K{i}" for i in range(6)], "d": [(day - dt.timedelta(days=r.randint(0, 50))).isoformat() for _ in range(6)]})
        later = pd.concat([base, pd.DataFrame({"k": ["N1", "N2"], "d": [(day + dt.timedelta(days=r.randint(1, 30))).isoformat() for _ in range(2)]})], ignore_index=True)
        assert core.asof_stable(call, {"t": base}, {"t": later}, day, key="k") is True
        changed = later.copy()
        changed.loc[0, "d"] = (day + dt.timedelta(days=5)).isoformat()                                  # a row that was before the date moves after it
        with pytest.raises(AssertionError):
            core.asof_stable(call, {"t": base}, {"t": changed}, day, key="k")


# ---------------------------------------------------------------- theme
def test_caption_gives_the_same_line_for_every_form_of_the_same_date_round_trip():
    """The date as a date, a timestamp or an ISO text gives the same caption, and the caption holds the ISO text of the date."""
    r = rng(7)
    for _ in range(100):
        d = dt.date(2020, 1, 1) + dt.timedelta(days=r.randint(0, 2500))
        lines = {core.caption("actual cost", x) for x in (d, pd.Timestamp(d), d.isoformat())}
        assert len(lines) == 1 and d.isoformat() in lines.pop()


def test_line_with_gaps_invariant_every_point_kept_sorted_by_x_and_a_null_only_where_the_step_is_large():
    r = rng(8)
    for _ in range(60):
        xs = sorted(r.sample(range(0, 200), r.randint(4, 20)))
        ys = [float(r.randint(1, 9)) for _ in xs]
        order = list(range(len(xs)))
        r.shuffle(order)
        out = core.line_with_gaps([xs[i] for i in order], [ys[i] for i in order])
        real = out.dropna(subset=["y"])
        assert real["x"].tolist() == xs and real["y"].tolist() == ys                                    # no point lost, sorted by x
        assert out["x"].is_monotonic_increasing and int(out["y"].isna().sum()) == len(out) - len(xs)
        steps = np.diff(xs)
        big = [i for i, step in enumerate(steps) if step > 1.5 * np.median(steps)]                       # the documented threshold: 1.5 times the median step
        assert int(out["y"].isna().sum()) == len(big)                                                    # a null exactly where a step is large
        assert sorted(out.loc[out["y"].isna(), "x"].tolist()) == [xs[i] + steps[i] / 2 for i in big]     # at half way through the gap


def test_line_with_gaps_even_steps_give_no_null_and_one_big_step_gives_exactly_one():
    even = core.line_with_gaps([0, 1, 2, 3, 4], [1.0] * 5)
    assert even["y"].notna().all() and even["x"].tolist() == [0, 1, 2, 3, 4]
    broken = core.line_with_gaps([0, 1, 2, 10, 11], [1.0, 2.0, 3.0, 4.0, 5.0])
    assert broken["x"].tolist() == [0, 1, 2, 6.0, 10, 11] and broken["y"].isna().tolist() == [False, False, False, True, False, False]
