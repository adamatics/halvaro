"""Presentation helpers (plan 5.10, C5 and C6): captions, the stage placeholder, a line that breaks at gaps and the theme tokens. No plotting package is imported: the package is not decided (plan section 9),
so apply_theme works on any figure that has the plotly or the matplotlib interface. Token values are PROPOSED (LOW): they wait for a design review."""
from __future__ import annotations

import datetime as dt
from typing import Any, Iterable, cast

import numpy as np
import pandas as pd

from .access import stage_banner
from .envelope import Envelope
from .errors import FrameError, StageRefusal
from .registry import function

SYNTHETIC_LABEL = "synthetic data"
VERIFY_LABEL = "provisional legal parameter, VERIFY"

# PROPOSED (LOW): both modes, text at least 4.5 to 1 on the background, the categorical colours of the series at least 3 to 1. The grid lines are decoration and are held to no ratio. Colour is never the only carrier of meaning.
TOKENS = {
    "light": {"background": "#FFFFFF", "text": "#1F2933", "grid": "#D5DAE0", "font": "sans-serif", "categorical": ("#1F6FB2", "#C2571A", "#2E8B57", "#7A4EA3", "#8A6D00", "#4A5568")},
    "dark": {"background": "#14181D", "text": "#E6EAF0", "grid": "#3A424C", "font": "sans-serif", "categorical": ("#6FB1E8", "#F0975A", "#6CC391", "#B792D9", "#D7B743", "#A0AEC0")},
}


OSM_ATTRIBUTION = "\u00a9 OpenStreetMap contributors"


@function(sources=(), oracle="none, returns the constant text SYNTHETIC_LABEL, no logic")
def synthetic_label() -> str:
    """Use this when you need the text 'synthetic data' that goes in the corner of every chart, table and map, in both modes.

    Rule: returns the constant text SYNTHETIC_LABEL; nothing is computed.

    Args:
        None: the function takes no input.

    Returns:
        str: the text "synthetic data".

    Raises:
        None: the function takes no input and has no error path.

    Example:
        >>> from halvaro.core import synthetic_label
        >>> synthetic_label()
        'synthetic data'
    """
    return SYNTHETIC_LABEL


@function(sources=(), oracle="none, returns the constant label text with the basemap attribution, no logic")
def map_label() -> str:
    """Use this when you need the label of a map: 'synthetic data' and the basemap attribution, because the networks drawn on the map are fictional (visualisations.md).

    Rule: the text SYNTHETIC_LABEL, a semicolon and a space, then the attribution text with a copyright sign and 'OpenStreetMap contributors'; nothing is computed.

    Args:
        None: the function takes no input.

    Returns:
        str: the label, "synthetic data; " followed by the attribution.

    Raises:
        None: the function takes no input and has no error path.

    Example:
        >>> from halvaro.core import map_label
        >>> map_label().startswith("synthetic data; ")
        True
        >>> map_label().endswith("OpenStreetMap contributors")
        True
    """
    return f"{SYNTHETIC_LABEL}; {OSM_ATTRIBUTION}"


def _day(value: Any) -> str:
    if value is None:
        return "as-of not stated"
    if isinstance(value, str):
        try:
            value = dt.date.fromisoformat(value)
        except ValueError:
            raise FrameError(f"as_of {value!r} is not an ISO date; expected YYYY-MM-DD such as 2026-11-30") from None
    if not isinstance(value, (dt.date, pd.Timestamp)):
        raise FrameError(f"as_of must be a date or an ISO date text, not {type(value).__name__}")
    return f"as of {value:%Y-%m-%d}"


@function(sources=(), oracle="py:../libs/halvaro-core/tests/test_oracle_theme.py::test_caption_oracle_hand_worked_texts_and_date_types")
def caption(basis: str | None, as_of: dt.date | pd.Timestamp | str | None) -> str:
    """Use this when a figure or a table needs the basis and as-of line under it.

    Rule: the line is "<basis>, as of <date>". A missing basis is written "basis not stated" and a missing date "as-of not stated"; neither is left out.

    Args:
        basis: What the figures are (for example "actual cost"), or None.
        as_of: The as-of date as a date, a timestamp or an ISO date text, or None.

    Returns:
        str: the caption line.

    Raises:
        FrameError: as_of is neither empty, a date, a timestamp nor an ISO date text.

    Example:
        >>> import datetime as dt
        >>> from halvaro.core import caption
        >>> caption("actual cost", dt.date(2026, 11, 30)), caption(None, None)
        ('actual cost, as of 2026-11-30', 'basis not stated, as-of not stated')
    """
    return f"{basis or 'basis not stated'}, {_day(as_of)}"


@function(sources=(), oracle="py:../libs/halvaro-core/tests/test_oracle_theme.py::test_footer_oracle_every_combination_of_synthetic_and_status")
def footer(envelope: Envelope) -> str:
    """Use this when you need the caption line of a result envelope: basis and as-of, 'synthetic data' when the envelope says so and 'provisional legal parameter, VERIFY' when its status carries VERIFY.

    Rule: the caption of the envelope's basis and as_of, then 'synthetic data' when envelope.synthetic is true (a missing attribute counts as true), then the VERIFY label when the text VERIFY occurs
    in envelope.status (so VERIFY and VERIFY+synthetic both qualify, and so does a proposed fact whose status carries it); the parts are joined with "; ".

    Args:
        envelope: The result envelope (any object with the attributes basis, as_of, synthetic and status; a missing attribute is read as empty, and synthetic as true).

    Returns:
        str: the footer text.

    Raises:
        FrameError: the as_of of the envelope is not empty, a date, a timestamp or an ISO date text (YYYY-MM-DD).

    Example:
        >>> import datetime as dt
        >>> from halvaro.core import Envelope, footer
        >>> footer(Envelope(value=1, basis="actual cost", as_of=dt.date(2026, 11, 30), status="VERIFY", synthetic=True))
        'actual cost, as of 2026-11-30; synthetic data; provisional legal parameter, VERIFY'
        >>> footer(Envelope(value=1, basis="actual cost", as_of=dt.date(2026, 11, 30), synthetic=False))
        'actual cost, as of 2026-11-30'
    """
    parts = [caption(getattr(envelope, "basis", None), getattr(envelope, "as_of", None))]
    if getattr(envelope, "synthetic", True):
        parts.append(SYNTHETIC_LABEL)
    if "VERIFY" in str(getattr(envelope, "status", "")):
        parts.append(VERIFY_LABEL)
    return "; ".join(parts)


@function(sources=(), oracle="py:../libs/halvaro-core/tests/test_oracle_theme.py::test_stage_placeholder_oracle_text_of_the_refusal_and_no_other_input")
def stage_placeholder(refusal: Exception) -> str:
    """Use this when you need the panel text for a chart whose source is above the stage of the session: what is missing, at which stage it appears and what the session sees.

    Rule: the one-line stage banner of the refusal followed by "The chart is not drawn."; nothing is estimated or drawn.

    Args:
        refusal: The StageRefusal that the data call raised; any other exception type is rejected.

    Returns:
        str: the panel text.

    Raises:
        FrameError: refusal is not a StageRefusal.

    Example:
        >>> from halvaro.core import StageRefusal, stage_placeholder
        >>> stage_placeholder(StageRefusal(["finance.invoice.amount"], "month3", "day1"))
        'Needs finance.invoice.amount (appears at stage month3). This session holds stage day1. The chart is not drawn.'
    """
    if not isinstance(refusal, StageRefusal):
        raise FrameError(f"stage_placeholder takes a StageRefusal, not {type(refusal).__name__}")
    return f"{stage_banner(refusal)} The chart is not drawn."


@function(sources=(), oracle="py:../libs/halvaro-core/tests/test_oracle_theme.py::test_line_with_gaps_oracle_random_series_against_a_loop_over_neighbouring_points")
def line_with_gaps(x: Iterable[Any] | pd.Series, y: Iterable[Any] | pd.Series, *, interval: float | dt.timedelta | None = None, factor: float = 1.5) -> pd.DataFrame:
    """Use this when you need the points of a line with a null row inserted where the step to the next x is too large, so that a plot breaks there instead of joining across the gap.

    Rule: the points are sorted by x (stable). Where the step to the next x is strictly more than the threshold, a row is inserted with x halfway through the gap and y null; a gap is never filled
    with zero and a null y stays null. The threshold is `factor` times `interval` when the caller passes the sampling interval, else `factor` times the median step (1.5 is proposed). Rows with a NaN x sort last and are kept. With fewer than two points the sorted points are returned as they are.

    Args:
        x: The x values (numbers or dates), as a list, array or Series.
        y: The y values, one per x.
        interval: The sampling interval, a number or a timedelta for dates; None takes the median step.
        factor: How many intervals a step may take before the line breaks (proposed 1.5).

    Returns:
        pandas.DataFrame with the columns x and y, sorted by x, with a row of null y added in every gap.

    Raises:
        FrameError: x or y is a scalar or a text and not a list, array or Series, x holds text or other values that are neither numbers nor dates, the interval is not a timedelta for dates or not a number for numbers, x and y differ in length, or the interval (given or median) is zero, negative or unknown; a median step of zero raises it even when a real gap exists (pass interval=).

    Example:
        >>> from halvaro.core import line_with_gaps
        >>> line_with_gaps([1, 2, 3, 6, 7], [10, 20, 30, 60, 70]).to_dict("list")
        {'x': [1.0, 2.0, 3.0, 4.5, 6.0, 7.0], 'y': [10.0, 20.0, 30.0, nan, 60.0, 70.0]}
    """
    for name, v in (("x", x), ("y", y)):
        if isinstance(v, (str, bytes)) or not (hasattr(v, "iloc") or hasattr(v, "__iter__")):
            raise FrameError(f"{name} must be a list, array or Series of values, not {v!r}")
    x, y = pd.Series(list(x) if not hasattr(x, "iloc") else cast(pd.Series, x).to_numpy()), pd.Series(list(y) if not hasattr(y, "iloc") else cast(pd.Series, y).to_numpy())
    if len(x) != len(y):
        raise FrameError("x and y must have the same length")
    d = pd.DataFrame({"x": x, "y": y}).sort_values("x", kind="stable").reset_index(drop=True)
    if len(d) < 2:
        return d
    is_date = pd.api.types.is_datetime64_any_dtype(d["x"])
    if pd.api.types.infer_dtype(d["x"], skipna=True) in ("string", "bytes", "mixed", "mixed-integer", "boolean"):
        raise FrameError(f"x must hold numbers or dates, not {pd.api.types.infer_dtype(d['x'], skipna=True)} values")
    if interval is not None and (is_date or pd.api.types.is_numeric_dtype(d["x"])):
        if is_date and not isinstance(interval, (dt.timedelta, np.timedelta64)):
            raise FrameError(f"interval must be a timedelta when x holds dates, not {interval!r}")
        if not is_date and (isinstance(interval, (dt.timedelta, np.timedelta64)) or not isinstance(interval, (int, float, np.integer, np.floating, np.bool_))):
            raise FrameError(f"interval must be a number when x holds numbers, not {interval!r}")
    step = d["x"].diff().iloc[1:]
    base: Any = interval if interval is not None else step.median()
    zero: Any = pd.Timedelta(0) if pd.api.types.is_datetime64_any_dtype(d["x"]) else 0
    if base is None or pd.isna(base) or base <= zero:
        raise FrameError("the sampling interval is zero or unknown; pass interval=")
    threshold = base * factor
    rows = []
    for i in range(len(d) - 1):
        rows.append((d["x"].iloc[i], d["y"].iloc[i]))
        gap = d["x"].iloc[i + 1] - d["x"].iloc[i]
        if gap > threshold:
            rows.append((d["x"].iloc[i] + gap / 2, np.nan))
    rows.append((d["x"].iloc[-1], d["y"].iloc[-1]))
    return pd.DataFrame(rows, columns=["x", "y"])


@function(sources=(), oracle="py:../libs/halvaro-core/tests/test_oracle_theme.py::test_apply_theme_oracle_text_and_categorical_contrast_and_the_figure_gets_the_tokens")
def apply_theme(figure: Any, mode: str = "light") -> Any:
    """Use this when you need a chart to carry the colours and font of the light or dark theme.

    Rule: the theme tokens of the mode (proposed, they wait for a design review) are set on the figure. A plotly figure (one with update_layout) gets the paper and plot background, the text colour and font, the categorical colours as colorway and the grid colour on both axes. A matplotlib figure (one with axes and set_facecolor) gets the background on the figure and every axes, the text colour on ticks, axis labels and title, and the grid colour. The same figure object is returned.

    Args:
        figure: A plotly figure or a matplotlib figure.
        mode: "light" or "dark". Default "light" (proposed).

    Returns:
        Any: the figure that was passed in, changed in place.

    Raises:
        FrameError: the mode is neither light nor dark (checked first), or the figure is neither a plotly nor a matplotlib figure.

    Example:
        >>> from halvaro.core import apply_theme
        >>> class Fig:
        ...     def update_layout(self, **settings):
        ...         self.layout = settings
        ...     def update_xaxes(self, **settings):
        ...         pass
        ...     def update_yaxes(self, **settings):
        ...         pass
        >>> fig = Fig()
        >>> apply_theme(fig, "dark") is fig
        True
        >>> fig.layout["paper_bgcolor"], len(fig.layout["colorway"])
        ('#14181D', 6)
    """
    if mode not in TOKENS:
        raise FrameError(f"mode must be 'light' or 'dark', not {mode!r}")
    t = TOKENS[mode]
    if hasattr(figure, "update_layout"):
        figure.update_layout(paper_bgcolor=t["background"], plot_bgcolor=t["background"], font={"color": t["text"], "family": t["font"]}, colorway=list(t["categorical"]))
        figure.update_xaxes(gridcolor=t["grid"])
        figure.update_yaxes(gridcolor=t["grid"])
        return figure
    if hasattr(figure, "axes") and hasattr(figure, "set_facecolor"):
        figure.set_facecolor(t["background"])
        for ax in figure.axes:
            ax.set_facecolor(t["background"])
            ax.tick_params(colors=t["text"])
            ax.xaxis.label.set_color(t["text"])
            ax.yaxis.label.set_color(t["text"])
            ax.title.set_color(t["text"])
            ax.grid(color=t["grid"])
        return figure
    raise FrameError(f"apply_theme does not know a figure of type {type(figure).__name__}; it supports plotly and matplotlib figures")
