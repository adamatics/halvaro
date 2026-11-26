"""U2: guarded_sum, reduce_chunks, interval_join, the theme helpers and the test helpers. Synthetic frames only, no release."""
import datetime as dt

import numpy as np
import pandas as pd
import pytest

import halvaro.core as core
from halvaro.core import Context, FrameError, StageRefusal, SumGuardError


def test_combine_status_is_registered_and_keeps_its_rule():
    assert "halvaro.core.facts.combine_status" in core.registered()
    assert core.combine_status(["verified", "VERIFY"]) == "VERIFY" and core.combine_status(["synthetic", "proposed"]) == "VERIFY+synthetic" and core.combine_status([]) == "ok"


def test_guarded_sum_refuses_two_currencies_and_sums_per_currency_when_grouped():
    f = pd.DataFrame({"prj": ["a", "a", "b"], "amount": [10.0, 5.0, 2.0], "currency": ["DKK", "EUR", "DKK"]})
    with pytest.raises(SumGuardError, match="currency"):
        core.guarded_sum(f, "amount")
    with pytest.raises(SumGuardError):
        core.guarded_sum(f, "amount", by="prj")
    got = core.guarded_sum(f, "amount", by=["prj", "currency"])
    assert got.to_dict("list") == {"prj": ["a", "a", "b"], "currency": ["DKK", "EUR", "DKK"], "amount": [10.0, 5.0, 2.0]}
    assert core.guarded_sum(f[f.currency == "DKK"], "amount").amount.tolist() == [12.0]
    assert core.guarded_sum(f[f.prj == "b"], "amount", by="prj").amount.tolist() == [2.0]


def test_guarded_sum_needs_a_guard_column_and_guards_units_too():
    with pytest.raises(FrameError, match="currency or unit"):
        core.guarded_sum(pd.DataFrame({"amount": [1.0]}), "amount")
    e = pd.DataFrame({"amount": [1.0, 2.0], "unit": ["t", "kg"]})
    with pytest.raises(SumGuardError, match="unit"):
        core.guarded_sum(e, "amount")
    assert core.guarded_sum(e, "amount", by="unit").amount.tolist() == [2.0, 1.0]


def test_reduce_chunks_equals_the_one_frame_result():
    rng = np.random.default_rng(3)
    big = pd.DataFrame({"g": rng.choice(["x", "y", "z"], 200), "h": rng.integers(0, 2, 200), "v": rng.normal(size=200)})
    big.loc[::17, "v"] = np.nan
    chunks = [big.iloc[i:i + 37] for i in range(0, 200, 37)]
    aggs = {"total": ("v", "sum"), "n": ("v", "count"), "lo": ("v", "min"), "hi": ("v", "max")}
    got = core.reduce_chunks(iter(chunks), ["g", "h"], aggs)
    want = big.groupby(["g", "h"]).agg(total=("v", "sum"), n=("v", "count"), lo=("v", "min"), hi=("v", "max")).reset_index()
    pd.testing.assert_frame_equal(got, want, check_dtype=False)
    one = core.reduce_chunks([big], [], {"n": ("v", "count")})
    assert one.n.tolist() == [int(big.v.notna().sum())]


def test_reduce_chunks_refuses_bad_input():
    with pytest.raises(FrameError, match="no chunk"):
        core.reduce_chunks([], "g", {"n": ("v", "count")})
    with pytest.raises(FrameError, match="lacks"):
        core.reduce_chunks([pd.DataFrame({"g": [1]})], "g", {"n": ("v", "count")})
    with pytest.raises(FrameError, match="function"):
        core.reduce_chunks([pd.DataFrame({"g": [1], "v": [1]})], "g", {"n": ("v", "mean")})
    assert core.reduce_chunks([pd.DataFrame({"g": [], "v": []})], "g", {"n": ("v", "sum")}).empty


def _ts(*h):
    return pd.to_datetime([f"2026-01-01 {x}:00" for x in h])


def test_interval_join_has_an_inclusive_last_sample_and_open_intervals():
    pts = pd.DataFrame({"sensor": ["s1"] * 4 + ["s2"], "ts": _ts("01", "02", "03", "04", "02")})
    iv = pd.DataFrame({"sensor": ["s1", "s1"], "from_ts": _ts("02", "04"), "to_ts": [_ts("03")[0], pd.NaT], "kind": ["spike", "open"]})
    got = core.interval_join(pts, iv, key="sensor")
    assert got.kind.isna().tolist() == [True, False, False, False, True] and got.kind.tolist()[1:4] == ["spike", "spike", "open"]
    assert got[got.sensor == "s1"].ts.dt.hour.tolist() == [1, 2, 3, 4], "one row per point, the last sample (03:00) is inside"
    excl = core.interval_join(pts, iv, key="sensor", inclusive_end=False)
    assert excl[excl.sensor == "s1"].kind.isna().tolist() == [True, False, True, False]
    assert len(core.interval_join(pts, iv, key="sensor", how="inner")) == 3
    with pytest.raises(FrameError):
        core.interval_join(pts, iv.drop(columns="to_ts"), key="sensor")


def test_interval_join_gives_a_point_in_two_intervals_two_rows_and_suffixes_a_clash():
    pts = pd.DataFrame({"ts": _ts("02"), "kind": ["p"]})
    iv = pd.DataFrame({"from_ts": _ts("01", "02"), "to_ts": _ts("03", "04"), "kind": ["a", "b"]})
    got = core.interval_join(pts, iv)
    assert got.kind.tolist() == ["p", "p"] and got.kind_iv.tolist() == ["a", "b"]


def test_caption_and_footer_say_what_is_missing_and_add_the_labels():
    assert core.caption("group pay basis", dt.date(2026, 11, 30)) == "group pay basis, as of 2026-11-30"
    assert core.caption(None, None) == "basis not stated, as-of not stated"
    env = core.make_envelope(1, facts=[core.fact("legal.DK.holiday.annual_days")], as_of=dt.date(2026, 11, 30), basis="booking")
    text = core.footer(env)
    assert text.startswith("booking, as of 2026-11-30") and "synthetic data" in text
    assert ("provisional legal parameter, VERIFY" in text) == ("VERIFY" in env.status)
    quiet = core.make_envelope(1, basis="b", as_of=dt.date(2026, 1, 1), synthetic=False)
    assert core.footer(quiet) == "b, as of 2026-01-01"


def test_stage_placeholder_names_the_missing_source_and_refuses_other_errors():
    with pytest.raises(StageRefusal) as e:
        core.require_sources(Context(stage="day1", role="r"), ["finance.journal_line.amount"])
    text = core.stage_placeholder(e.value)
    assert "finance" in text and "not drawn" in text
    with pytest.raises(FrameError):
        core.stage_placeholder(ValueError("x"))


def test_line_with_gaps_breaks_where_samples_are_missing_and_never_zero_fills():
    t = pd.date_range("2026-01-01", periods=10, freq="h").delete([4, 5, 6])
    got = core.line_with_gaps(t, np.arange(len(t), dtype=float))
    assert got.y.isna().sum() == 1 and len(got) == len(t) + 1 and (got.y.dropna() >= 0).all()
    brk = got[got.y.isna()].x.iloc[0]
    assert t[3] < brk < t[4]
    assert core.line_with_gaps(t, np.arange(len(t), dtype=float), interval=pd.Timedelta(hours=10)).y.isna().sum() == 0, "a wide sampling interval says there is no gap"
    num = core.line_with_gaps([0, 1, 2, 10, 11], [1.0, np.nan, 3.0, 4.0, 5.0])
    assert num.y.isna().sum() == 2 and (num.y.fillna(-1) != 0).all()
    with pytest.raises(FrameError):
        core.line_with_gaps([1, 1, 1], [1, 2, 3])
    assert len(core.line_with_gaps([1], [2.0])) == 1


class _Fig:
    def __init__(self):
        self.calls = []

    def update_layout(self, **kw):
        self.calls.append(("layout", kw))

    def update_xaxes(self, **kw):
        self.calls.append(("x", kw))

    update_yaxes = update_xaxes


def test_apply_theme_sets_both_modes_and_refuses_unknown_figures():
    f = core.apply_theme(_Fig(), "dark")
    assert f.calls[0][1]["paper_bgcolor"] == core.theme.TOKENS["dark"]["background"]
    assert core.apply_theme(_Fig()).calls[0][1]["paper_bgcolor"] == "#FFFFFF"
    with pytest.raises(FrameError):
        core.apply_theme(object())
    with pytest.raises(FrameError):
        core.apply_theme(_Fig(), "sepia")


def _luminance(h):
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4  # noqa: E731
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def test_theme_tokens_meet_the_contrast_the_plan_asks_for():
    for t in core.theme.TOKENS.values():
        ratio = lambda a, b: (max(_luminance(a), _luminance(b)) + 0.05) / (min(_luminance(a), _luminance(b)) + 0.05)  # noqa: E731
        assert ratio(t["text"], t["background"]) >= 4.5
        assert all(ratio(c, t["background"]) >= 3 for c in t["categorical"])


def test_stage_matrix_expects_a_result_or_a_refusal_naming_the_missing_source():
    fid = "halvaro.core.access.require_sources"
    meta = core.registered()["halvaro.core.calendar.public_holidays"]   # a registered function with no sources: always a result
    rows = core.stage_matrix("halvaro.core.calendar.public_holidays", {}, lambda frames, ctx: 1)
    assert all(r["expected"] == "result" and r["ok"] for r in rows) and meta.sources == ()

    # a function that needs a month12 source: the matrix expects a refusal below month12
    from halvaro.core.registry import _REGISTRY, FunctionMeta
    _REGISTRY["halvaro.core.tmp.needs_finance"] = FunctionMeta(id="halvaro.core.tmp.needs_finance", summary="t", sources=("finance.journal_line.amount",))
    try:
        def call(frames, ctx):
            core.require_sources(ctx, ["finance.journal_line.amount"], function="tmp")
        rows = core.stage_matrix("halvaro.core.tmp.needs_finance", {"finance.journal_line": pd.DataFrame()}, call)
        assert {r["expected"] for r in rows} == {"refusal", "result"} and all(r["ok"] for r in rows)
        with pytest.raises(AssertionError, match="expected refusal"):
            core.stage_matrix("halvaro.core.tmp.needs_finance", {}, lambda frames, ctx: 1)
        assert not all(r["ok"] for r in core.stage_matrix("halvaro.core.tmp.needs_finance", {}, lambda frames, ctx: 1, strict=False))
    finally:
        del _REGISTRY["halvaro.core.tmp.needs_finance"]
    with pytest.raises(core.HalvaroError):
        core.stage_matrix("halvaro.core.nope.nothing", {}, lambda f, c: 1)
    assert fid in core.registered()


def test_asof_stable_allows_only_the_named_effective_dated_changes():
    a = {"t": pd.DataFrame({"k": ["x", "y", "z"], "v": [1, 2, 3]})}
    b = {"t": pd.DataFrame({"k": ["x", "y", "z"], "v": [1, 2, 4]})}
    call = lambda frames, as_of: frames["t"]  # noqa: E731
    assert core.asof_stable(call, a, a, dt.date(2026, 11, 30), key="k")
    with pytest.raises(AssertionError, match="z"):
        core.asof_stable(call, a, b, dt.date(2026, 11, 30), key="k")
    assert core.asof_stable(call, a, b, dt.date(2026, 11, 30), key="k", allowed_keys=["z"])
    c = {"t": pd.concat([a["t"], pd.DataFrame({"k": ["w"], "v": [9]})])}
    with pytest.raises(AssertionError, match="w"):
        core.asof_stable(call, a, c, dt.date(2026, 11, 30), key="k")


class _Loader:
    def __init__(self, frame, *, wrong_where=False, tz=False, leak=False, bad_chunks=False):
        self.f, self.wrong_where, self.leak, self.bad_chunks = frame.copy(), wrong_where, leak, bad_chunks
        if tz:
            self.f["ts"] = self.f["ts"].dt.tz_localize("UTC")

    def load(self, source, table, columns=None, where=None):
        f = self.f
        if where and not self.wrong_where:
            for c, v in where.items():
                f = f[f[c] == v]
        if columns:
            f = f[list(columns)]
        return f.reset_index(drop=True)

    def iter_chunks(self, source, table, columns=None, where=None):
        f = self.load(source, table, columns, where)
        yield f.iloc[:2]
        yield f.iloc[3 if self.bad_chunks else 2:]


def test_loader_contract_passes_a_good_loader_and_names_each_breach():
    base = pd.DataFrame({"emp_key": ["EMP-1", "EMP-2", "EMP-3", "EMP-4"], "ts": pd.date_range("2026-01-01", periods=4), "pay": [1, 2, 3, 4]})
    exp = {"hr.employee": ["emp_key", "ts", "pay"]}
    ctx = Context(stage="month12", role="r")
    assert core.loader_contract(_Loader(base), exp, context=ctx, where={"hr.employee": ("emp_key", "EMP-2")}) == []
    assert any("restricted" in x for x in core.loader_contract(_Loader(base), exp, context=ctx, restricted_columns=["pay"]))
    assert core.loader_contract(_Loader(base), exp, context=Context(stage="month12", role="r", restricted_ok=True), restricted_columns=["pay"]) == []
    assert any("tz aware" in x for x in core.loader_contract(_Loader(base, tz=True), exp))
    assert any("where" in x for x in core.loader_contract(_Loader(base, wrong_where=True), exp, where={"hr.employee": ("emp_key", "EMP-2")}))
    assert any("iter_chunks" in x for x in core.loader_contract(_Loader(base, bad_chunks=True), exp))
    assert any("differ" in x for x in core.loader_contract(_Loader(base), {"hr.employee": ["emp_key", "pay", "ts"]}))
