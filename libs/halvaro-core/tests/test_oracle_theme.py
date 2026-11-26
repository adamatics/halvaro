"""Oracles of halvaro.core.theme (lane L1): the text helpers against hand written strings, line_with_gaps against a loop over the steps, and the theme tokens against the contrast ratio the module
promises (text 4.5 to 1, graphics 3 to 1), computed here with the WCAG formula. Plotly and matplotlib are not installed: the figures are small stand-ins with the same interface."""
import datetime as dt
import random
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

import halvaro.core as core
from halvaro.core import theme


def _luminance(hex_colour: str) -> float:
    """Relative luminance of #RRGGBB by the WCAG 2 formula."""
    rgb = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


class PlotlyLike:
    """The three methods of a plotly figure that apply_theme calls; records what it got."""

    def __init__(self):
        self.layout, self.xaxes, self.yaxes = {}, {}, {}

    def update_layout(self, **kw):
        self.layout.update(kw)

    def update_xaxes(self, **kw):
        self.xaxes.update(kw)

    def update_yaxes(self, **kw):
        self.yaxes.update(kw)


class _Label:
    def __init__(self):
        self.colour = None

    def set_color(self, c):
        self.colour = c


class _Axes:
    def __init__(self):
        self.face, self.ticks, self.grid_args = None, None, None
        self.xaxis, self.yaxis, self.title = SimpleNamespace(label=_Label()), SimpleNamespace(label=_Label()), _Label()

    def set_facecolor(self, c):
        self.face = c

    def tick_params(self, **kw):
        self.ticks = kw

    def grid(self, **kw):
        self.grid_args = kw


class MatplotlibLike:
    def __init__(self, n=2):
        self.axes, self.face = [_Axes() for _ in range(n)], None

    def set_facecolor(self, c):
        self.face = c


@pytest.mark.parametrize("mode", ["light", "dark"])
def test_apply_theme_oracle_text_and_categorical_contrast_and_the_figure_gets_the_tokens(mode):
    """halvaro.core.theme.apply_theme: the text colour has at least 4.5 to 1 against the background and every categorical colour at least 3 to 1 (WCAG formula, computed here; the grid colour is not asserted); a plotly like figure
    gets exactly those colours, a matplotlib like figure gets them on figure, axes, ticks, labels, title and grid; the same object comes back and a second call changes nothing."""
    t = core.theme.TOKENS[mode]
    assert _contrast(t["text"], t["background"]) >= 4.5
    assert len(t["categorical"]) >= 6 and all(_contrast(c, t["background"]) >= 3 for c in t["categorical"]), [round(_contrast(c, t["background"]), 2) for c in t["categorical"]]
    assert len(set(t["categorical"])) == len(t["categorical"]), "no colour twice"
    # the grid lines are decoration and are not asserted: their contrast against the background is about 1.4 to 1 (light) and 1.8 to 1 (dark), see item 18 of the review issue
    fig = PlotlyLike()
    assert core.apply_theme(fig, mode) is fig
    assert fig.layout["paper_bgcolor"] == fig.layout["plot_bgcolor"] == t["background"] and fig.layout["font"]["color"] == t["text"] and fig.layout["colorway"] == list(t["categorical"])
    assert fig.layout["font"]["family"] == t["font"] and fig.xaxes == fig.yaxes == {"gridcolor": t["grid"]}
    state = (dict(fig.layout), dict(fig.xaxes))
    core.apply_theme(fig, mode)
    assert (dict(fig.layout), dict(fig.xaxes)) == state
    m = MatplotlibLike(3)
    assert core.apply_theme(m, mode) is m and m.face == t["background"]
    for ax in m.axes:
        assert ax.face == t["background"] and ax.ticks == {"colors": t["text"]} and ax.grid_args == {"color": t["grid"]}
        assert ax.xaxis.label.colour == ax.yaxis.label.colour == ax.title.colour == t["text"]


def test_apply_theme_oracle_modes_differ_and_unknown_input_is_refused():
    """halvaro.core.theme.apply_theme: light and dark give different backgrounds and text colours (a dark mode that equals the light one would be no mode), an unknown mode or figure raises FrameError."""
    light, dark = core.apply_theme(PlotlyLike(), "light"), core.apply_theme(PlotlyLike(), "dark")
    assert light.layout["paper_bgcolor"] != dark.layout["paper_bgcolor"] and light.layout["font"]["color"] != dark.layout["font"]["color"]
    assert _luminance(light.layout["paper_bgcolor"]) > _luminance(dark.layout["paper_bgcolor"]), "light is lighter than dark"
    for bad_mode in ("Light", "", None, "sepia"):
        with pytest.raises(core.FrameError):
            core.apply_theme(PlotlyLike(), bad_mode)
    for bad_figure in (object(), "figure", 3, None):
        with pytest.raises(core.FrameError, match="does not know a figure"):
            core.apply_theme(bad_figure)
    assert core.apply_theme(PlotlyLike()).layout["paper_bgcolor"] == core.theme.TOKENS["light"]["background"], "light is the default"


def test_caption_oracle_hand_worked_texts_and_date_types():
    """halvaro.core.theme.caption: basis, comma, 'as of' and the ISO date, written out by hand; an ISO text, a date and a timestamp give the same line, a missing basis or date is said and a date of
    another type is refused."""
    assert core.caption("DKK, actuals", dt.date(2026, 11, 30)) == "DKK, actuals, as of 2026-11-30"
    assert core.caption("EUR", "2026-01-05") == "EUR, as of 2026-01-05" == core.caption("EUR", pd.Timestamp("2026-01-05 13:45"))
    assert core.caption(None, None) == "basis not stated, as-of not stated" and core.caption("", dt.date(2026, 2, 3)) == "basis not stated, as of 2026-02-03"
    assert core.caption("x", dt.date(2026, 11, 30)) == core.caption("x", "2026-11-30") == core.caption("x", pd.Timestamp("2026-11-30"))
    for bad in (20261130, 3.5, ["2026-11-30"]):
        with pytest.raises(core.FrameError):
            core.caption("x", bad)


def _env(**kw):
    return SimpleNamespace(**kw)


def test_footer_oracle_every_combination_of_synthetic_and_status():
    """halvaro.core.theme.footer: the caption of the envelope, then 'synthetic data' when the envelope is synthetic, then the VERIFY label when its status carries VERIFY; the combinations are written
    out by hand and an envelope without these fields gets the defaults (synthetic, nothing stated)."""
    base = "EUR, as of 2026-11-30"
    table = {(True, "ok"): base + "; synthetic data", (False, "ok"): base, (True, "VERIFY"): base + "; synthetic data; provisional legal parameter, VERIFY",
             (False, "VERIFY"): base + "; provisional legal parameter, VERIFY", (True, "VERIFY+synthetic"): base + "; synthetic data; provisional legal parameter, VERIFY",
             (False, "synthetic"): base, (False, ""): base}
    for (synthetic, status), want in table.items():
        assert core.footer(_env(basis="EUR", as_of=dt.date(2026, 11, 30), synthetic=synthetic, status=status)) == want, (synthetic, status)
    assert core.footer(_env()) == "basis not stated, as-of not stated; synthetic data"
    assert core.footer(_env(basis="DKK", as_of="2026-01-01", status="VERIFY")).endswith("provisional legal parameter, VERIFY")


def test_stage_placeholder_oracle_text_of_the_refusal_and_no_other_input():
    """halvaro.core.theme.stage_placeholder: the panel text is the banner of the stage refusal and the words 'The chart is not drawn.'; anything but a StageRefusal raises FrameError."""
    refusal = core.StageRefusal(["finance"], "month3", "day1")
    assert core.theme.stage_placeholder(refusal) == "Needs finance (appears at stage month3). This session holds stage day1. The chart is not drawn."
    for other in (core.FrameError("x"), ValueError("x"), "finance", None):
        with pytest.raises(core.FrameError, match="takes a StageRefusal"):
            core.theme.stage_placeholder(other)


def _ref_gaps(points: list, threshold) -> list:
    """Points sorted by x and a (midpoint, None) after each step larger than the threshold: a loop over neighbouring pairs."""
    pts = sorted(points, key=lambda p: p[0])
    out = []
    for i, (x, y) in enumerate(pts):
        out.append((x, y))
        if i + 1 < len(pts) and pts[i + 1][0] - x > threshold:
            out.append((x + (pts[i + 1][0] - x) / 2, None))
    return out


def _pairs(frame: pd.DataFrame) -> list:
    return [(r.x, None if pd.isna(r.y) else r.y) for r in frame.itertuples()]


def test_line_with_gaps_oracle_hand_worked_numbers_and_the_given_interval():
    """halvaro.core.theme.line_with_gaps: x 1, 2, 3, 10, 11 with the median step 1 breaks once, halfway through the 3 to 10 gap at 6.5; a given interval of 2 breaks at the same place, an interval of 10 does
    not break; a null y stays null and is never zero."""
    x, y = [1, 2, 3, 10, 11], [5.0, None, 7.0, 8.0, 9.0]
    out = core.line_with_gaps(x, y)
    assert out["x"].tolist() == [1, 2, 3, 6.5, 10, 11] and [None if pd.isna(v) else v for v in out["y"]] == [5.0, None, 7.0, None, 8.0, 9.0]
    assert core.line_with_gaps(x, y, interval=2)["x"].tolist() == [1, 2, 3, 6.5, 10, 11]
    assert core.line_with_gaps(x, y, interval=10)["x"].tolist() == [1, 2, 3, 10, 11]
    assert core.line_with_gaps(x, y, interval=2, factor=4)["x"].tolist() == [1, 2, 3, 10, 11], "a step of 7 is not above 4 times 2"
    assert (out["y"].fillna(-1) != 0).all() and list(out.columns) == ["x", "y"]
    assert core.line_with_gaps([0, 3, 6], [1.0, 2.0, 3.0], interval=2)["x"].tolist() == [0, 3, 6], "a step exactly at the threshold (3 = 1.5 times 2) does not break the line"
    assert core.line_with_gaps([0, 3.5, 7], [1.0, 2.0, 3.0], interval=2)["x"].tolist() == [0, 1.75, 3.5, 5.25, 7], "a step above it breaks, halfway through the step"


@pytest.mark.parametrize("seed", range(6))
def test_line_with_gaps_oracle_random_series_against_a_loop_over_neighbouring_points(seed):
    """halvaro.core.theme.line_with_gaps: for random sampled series with random gaps, unsorted input, null values and both numbers and timestamps, the output equals the loop over neighbouring points,
    the original points are all there in order, and the input is not changed."""
    rng = random.Random(seed)
    steps = [rng.choice([1, 1, 1, 1, 2, 7, 30]) for _ in range(60)]
    xs = np.cumsum(steps).tolist()
    ys = [None if rng.random() < 0.1 else round(rng.uniform(-5, 5), 3) for _ in xs]
    order = list(range(len(xs)))
    rng.shuffle(order)
    ux, uy = [xs[i] for i in order], [ys[i] for i in order]
    ux_before, uy_before = list(ux), list(uy)
    got = core.line_with_gaps(ux, uy, interval=2)
    assert _pairs(got) == _ref_gaps(list(zip(xs, ys)), 3.0)
    assert len(got) > len(xs), "the series has gaps, so at least one row was inserted"
    assert ux == ux_before and uy == uy_before
    kept = [p for p in _pairs(got) if p[0] in set(xs)]
    assert [p[0] for p in kept] == xs, "all original points, in order"
    day0 = pd.Timestamp("2026-01-01")
    times = [day0 + pd.Timedelta(minutes=int(v)) for v in xs]
    got_t = core.line_with_gaps(times, ys, interval=pd.Timedelta(minutes=2))
    assert _pairs(got_t) == _ref_gaps(list(zip(times, ys)), pd.Timedelta(minutes=3))
    assert _pairs(core.line_with_gaps(pd.Series(ux), pd.Series(uy), interval=2)) == _pairs(got) and _pairs(core.line_with_gaps(np.array(ux), np.array(uy, dtype=float), interval=2)) == _pairs(got)
    median_t = core.line_with_gaps(times, ys)
    assert len(median_t) == len(times) + sum(1 for s in steps[1:] if s > 1.5 * float(np.median(steps[1:]))), "timestamps without interval use 1.5 times the median step"
    median_run = core.line_with_gaps(xs, ys)
    assert len(median_run) == len(xs) + sum(1 for s in steps[1:] if s > 1.5 * float(np.median(steps[1:]))), "without interval the threshold is 1.5 times the median step"


def test_line_with_gaps_oracle_short_and_wrong_input():
    """halvaro.core.theme.line_with_gaps: fewer than two points come back as they are, different lengths or a zero interval raise FrameError."""
    assert core.line_with_gaps([5], [1.0]).to_dict("records") == [{"x": 5, "y": 1.0}] and core.line_with_gaps([], []).empty
    with pytest.raises(core.FrameError):
        core.line_with_gaps([1, 2, 3], [1, 2])
    with pytest.raises(core.FrameError):
        core.line_with_gaps([1, 2, 3], [1, 2, 3], interval=0)
    with pytest.raises(core.FrameError):
        core.line_with_gaps([1, 1, 1], [1, 2, 3])
