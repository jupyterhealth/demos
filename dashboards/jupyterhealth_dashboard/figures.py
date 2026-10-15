"""Plotly figure factories for the CGM demo dashboard.

These factories only *draw*. They accept the plain frames and dicts the notebook
prepares, so every figure in the notebook and in the served Voilà page is drawn
from the same numbers the notebook computed --- no analytical math and no data
retrieval live here.

Two rules are encoded deliberately:

* the conventional glucose target band (70--180 mg/dL) and range colours are
  used instead of a generic product palette; and
* the glucose trace is split into contiguous segments wherever the recording has
  a gap, so a missing window is never bridged by a straight line.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

DUKE_NAVY = "#012169"
DUKE_BLUE = "#00539b"
INK = "#111318"
MUTED = "#5b6674"
GRID = "#dfe5eb"
TARGET_FILL = "#edf5eb"
TARGET_LINE = "#c7dcc0"
# Ambulatory Glucose Profile (AGP) palette. The filled region between the 5th
# and 95th percentiles is coloured by the *glucose value* band it occupies, not
# by which percentile rank produced it. A pale-green 70--180 target field stays
# behind the profile, the 54 / 70 / 180 boundary lines stay on top, and only the
# green 50th-percentile median is drawn as a stroke.
AGP_TARGET_LINE = "#3aa35c"      # green 70 / 180 target boundaries
AGP_LOW_LINE = "#d0342c"         # red 54 mg/dL hypoglycaemia boundary
AGP_MEDIAN = "#0f9d46"           # green 50th-percentile median
AGP_VALUE_VERY_LOW = "#7a1a1a"   # < 54 mg/dL dark red
AGP_VALUE_LOW = "#d64545"        # 54--<70 mg/dL red
AGP_VALUE_TARGET = "#74c476"     # 70--180 mg/dL green
AGP_VALUE_HIGH = "#f0c04c"       # >180--250 mg/dL yellow
AGP_VALUE_VERY_HIGH = "#e8913a"  # >250 mg/dL orange
MEAL_AMBER = "#d49318"
MEAL_BORDER = "#704b08"
ACTIVITY_BLUE = "#617fa8"
DEEP = "#2c5282"
LIGHT = "#63a4d8"
REM = "#8b5cf6"
NO_WALK = "#d2681c"
WITH_WALK = DUKE_BLUE

_MAX_TRACE_GAP = timedelta(minutes=15)

_BASE_LAYOUT = {
    "template": "plotly_white",
    "font": {"family": "Inter, system-ui, sans-serif", "size": 12, "color": INK},
    "paper_bgcolor": "white",
    "plot_bgcolor": "white",
    "margin": {"l": 48, "r": 16, "t": 24, "b": 36},
    "hovermode": "closest",
}


def _wall_clock(moment: datetime) -> datetime:
    """Render study-local wall clock so the time axis matches the recorded local day."""
    return moment.replace(tzinfo=None)


def _minute_label(minute: int) -> str:
    hours, remainder = divmod(int(minute), 60)
    return f"{hours:02d}:{remainder:02d}"


def _meal_label(label: str) -> str:
    """Presentation-only: drop the generator's ``Synthetic`` prefix and sentence-case."""
    text = str(label).removeprefix("Synthetic ").strip() or "Meal"
    return text[:1].upper() + text[1:]


def _meal_customdata(meals: pd.DataFrame) -> list[list]:
    """Build hover payload rows for every meal without painting text on the plot.

    Each row carries the complete meal name plus meal type, macros, energy, and the
    notebook-derived activity context when present. Missing optional columns fall
    back to zero or an empty activity string so synthetic/test frames stay valid.
    """
    rows: list[list] = []
    for row in meals.itertuples():
        rows.append(
            [
                _meal_label(row.label),
                str(getattr(row, "meal_type", "meal") or "meal"),
                float(getattr(row, "carbohydrate_g", 0.0) or 0.0),
                float(getattr(row, "protein_g", 0.0) or 0.0),
                float(getattr(row, "fat_g", 0.0) or 0.0),
                float(getattr(row, "fiber_g", 0.0) or 0.0),
                float(getattr(row, "calories_kcal", 0.0) or 0.0),
                str(getattr(row, "activity_context", "") or ""),
            ]
        )
    return rows


def _glucose_segments(glucose: pd.DataFrame) -> list[pd.DataFrame]:
    """Split the trace wherever consecutive samples are more than 15 minutes apart."""
    if glucose.empty:
        return []
    ordered = glucose.sort_values("recorded_at").reset_index(drop=True)
    breaks = ordered["recorded_at"].diff() > _MAX_TRACE_GAP
    segments: list[pd.DataFrame] = []
    start = 0
    for index in range(1, len(ordered)):
        if bool(breaks.iloc[index]):
            segments.append(ordered.iloc[start:index])
            start = index
    segments.append(ordered.iloc[start:])
    return segments


def _nearest_glucose(glucose: pd.DataFrame, moment: datetime) -> float:
    if glucose.empty:
        return 40.0
    target = _wall_clock(moment)
    deltas = (glucose["recorded_at"].map(_wall_clock) - target).abs()
    return float(glucose.loc[deltas.idxmin(), "mg_dl"])


def recording_bounds(explorer: dict) -> tuple[datetime | None, datetime | None]:
    """Return the actual start/end of the selected recording."""
    glucose = explorer.get("glucose", pd.DataFrame())
    if glucose.empty:
        return None, None
    start = min(_wall_clock(value) for value in glucose["recorded_at"])
    end = max(_wall_clock(value) for value in glucose["recorded_at"])
    return start, end


def _trace_axis(span: timedelta) -> tuple[int, str]:
    """Choose a readable tick interval and label for the selected span."""
    if span <= timedelta(days=2):
        return 6 * 3600 * 1000, "%a %-d<br>%H:%M"
    if span <= timedelta(days=8):
        return 24 * 3600 * 1000, "%a %-d"
    return 2 * 24 * 3600 * 1000, "%b %-d"


_AGP_VALUE_BANDS = (
    (AGP_VALUE_VERY_LOW, "Very low (<54)", None, 54, False, False, 1),
    (AGP_VALUE_LOW, "Low (54–<70)", 54, 70, True, False, 2),
    (AGP_VALUE_TARGET, "Target (70–180)", 70, 180, True, True, 3),
    (AGP_VALUE_HIGH, "High (>180–250)", 180, 250, False, True, 4),
    (AGP_VALUE_VERY_HIGH, "Very high (>250)", 250, None, False, False, 5),
)
def _agp_rows(percentiles: list) -> list[dict]:
    """Return valid percentile rows sorted by minute, dropping malformed entries."""
    rows: list[dict] = []
    for point in percentiles or []:
        try:
            rows.append(
                {
                    "minute": float(point["minute"]),
                    "p05": float(point["p05"]),
                    "p25": float(point["p25"]),
                    "p50": float(point["p50"]),
                    "p75": float(point["p75"]),
                    "p95": float(point["p95"]),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return sorted(rows, key=lambda row: row["minute"])


def _agp_segments(rows: list[dict]) -> list[list[dict]]:
    """Split sorted rows wherever a bin is missing so gaps are never interpolated."""
    if not rows:
        return []
    diffs = [
        right["minute"] - left["minute"]
        for left, right in zip(rows, rows[1:])
        if right["minute"] > left["minute"]
    ]
    bin_width = min(diffs) if diffs else 15.0
    gap_threshold = bin_width * 1.5
    segments: list[list[dict]] = []
    current = [rows[0]]
    for left, right in zip(rows, rows[1:]):
        if right["minute"] - left["minute"] > gap_threshold:
            segments.append(current)
            current = [right]
        else:
            current.append(right)
    segments.append(current)
    return segments


def _lerp(x0: float, y0: float, x1: float, y1: float, x: float) -> float:
    if x1 == x0:
        return y0
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def _crossing_x(x0: float, y0: float, x1: float, y1: float, threshold: float) -> float | None:
    """Return the exact x where a linear segment crosses a horizontal threshold."""
    if y0 == y1 or (y0 - threshold) * (y1 - threshold) >= 0:
        return None
    return x0 + (x1 - x0) * (threshold - y0) / (y1 - y0)


def _eval_series(rows: list[dict], x: float, key: str) -> float:
    """Evaluate a piecewise-linear percentile series at an arbitrary x."""
    if x <= rows[0]["minute"]:
        return rows[0][key]
    if x >= rows[-1]["minute"]:
        return rows[-1][key]
    for left, right in zip(rows, rows[1:]):
        if left["minute"] <= x <= right["minute"]:
            return _lerp(left["minute"], left[key], right["minute"], right[key], x)
    return rows[-1][key]


def _clean_polygon(polygon: list[tuple[float, float]]) -> list[tuple[float, float]]:
    cleaned: list[tuple[float, float]] = []
    for point in polygon:
        if cleaned and abs(point[0] - cleaned[-1][0]) < 1e-9 and abs(point[1] - cleaned[-1][1]) < 1e-9:
            continue
        cleaned.append(point)
    if len(cleaned) > 1 and abs(cleaned[0][0] - cleaned[-1][0]) < 1e-9 and abs(cleaned[0][1] - cleaned[-1][1]) < 1e-9:
        cleaned.pop()
    return cleaned if len(cleaned) >= 3 else []


def _interval_active_ranges(
    x0: float,
    p05_0: float,
    p95_0: float,
    x1: float,
    p05_1: float,
    p95_1: float,
    y_low: float,
    y_high: float,
    lo_inclusive: bool,
    hi_inclusive: bool,
) -> list[tuple[float, float]]:
    """Exact x sub-ranges where the p05--p95 strip intersects a value band."""
    points = {x0, x1}
    for f0, f1 in ((p05_0, p05_1), (p95_0, p95_1)):
        for threshold in (y_low, y_high):
            if math.isinf(threshold):
                continue
            crossing = _crossing_x(x0, f0, x1, f1, threshold)
            if crossing is not None and x0 < crossing < x1:
                points.add(crossing)
    ordered = sorted(points)
    ranges: list[tuple[float, float]] = []
    for left, right in zip(ordered, ordered[1:]):
        mid = (left + right) / 2
        p05_mid = _lerp(x0, p05_0, x1, p05_1, mid)
        p95_mid = _lerp(x0, p95_0, x1, p95_1, mid)
        lower_ok = p95_mid >= y_low if lo_inclusive else p95_mid > y_low
        upper_ok = p05_mid <= y_high if hi_inclusive else p05_mid < y_high
        if lower_ok and upper_ok:
            ranges.append((left, right))
    return ranges


def _value_polygon(
    rows: list[dict],
    y_low: float,
    y_high: float,
    x_start: float,
    x_end: float,
) -> list[tuple[float, float]]:
    """Build one closed polygon for the strip's intersection with [y_low, y_high]."""
    xs = {x_start, x_end}
    for left, right in zip(rows, rows[1:]):
        x0 = left["minute"]
        x1 = right["minute"]
        if x1 <= x0:
            continue
        for key in ("p05", "p95"):
            for threshold in (y_low, y_high):
                if math.isinf(threshold):
                    continue
                crossing = _crossing_x(x0, left[key], x1, right[key], threshold)
                if crossing is not None and x_start - 1e-9 <= crossing <= x_end + 1e-9:
                    xs.add(crossing)
    for row in rows:
        if x_start - 1e-9 <= row["minute"] <= x_end + 1e-9:
            xs.add(row["minute"])
    ordered = sorted(xs)
    bottom = []
    top = []
    for x in ordered:
        p05 = _eval_series(rows, x, "p05")
        p95 = _eval_series(rows, x, "p95")
        bottom.append((x, max(p05, y_low)))
        top.append((x, min(p95, y_high)))
    return _clean_polygon(bottom + list(reversed(top)))


def _agp_value_polygons(
    rows: list[dict],
    y_low: float,
    y_high: float,
    lo_inclusive: bool,
    hi_inclusive: bool,
) -> list[list[tuple[float, float]]]:
    """Collect the value-band polygons for one contiguous percentile segment."""
    polygons: list[list[tuple[float, float]]] = []
    start_x: float | None = None
    end_x: float | None = None
    for index in range(len(rows) - 1):
        left = rows[index]
        right = rows[index + 1]
        x0 = left["minute"]
        x1 = right["minute"]
        if x1 <= x0:
            continue
        ranges = _interval_active_ranges(
            x0, left["p05"], left["p95"], x1, right["p05"], right["p95"], y_low, y_high,
            lo_inclusive, hi_inclusive,
        )
        for start, end in ranges:
            if start_x is None:
                start_x, end_x = start, end
            elif abs(start - end_x) < 1e-9:
                end_x = end
            else:
                polygons.append(_value_polygon(rows, y_low, y_high, start_x, end_x))
                start_x, end_x = start, end
        if not ranges and start_x is not None:
            polygons.append(_value_polygon(rows, y_low, y_high, start_x, end_x))
            start_x = end_x = None
    if start_x is not None:
        polygons.append(_value_polygon(rows, y_low, y_high, start_x, end_x))
    return polygons


def _agp_series_xy(segments: list[list[dict]], key: str) -> tuple[list, list]:
    xs: list = []
    ys: list = []
    for segment in segments:
        if xs:
            xs.append(None)
            ys.append(None)
        for row in segment:
            xs.append(row["minute"])
            ys.append(row[key])
    return xs, ys


def _agp_series_text(segments: list[list[dict]]) -> list:
    text: list = []
    for segment in segments:
        if text:
            text.append(None)
        for row in segment:
            text.append(_minute_label(int(row["minute"])))
    return text


def _agp_y_axis(rows: list[dict]) -> tuple[float, float, list[float]]:
    """Dynamic y range so no percentile value is clipped outside the canvas."""
    if not rows:
        return 40.0, 300.0, [40, 54, 70, 180, 250, 300]
    lows = [row["p05"] for row in rows]
    highs = [row["p95"] for row in rows]
    y_low = min(40.0, math.floor(min(lows) / 10.0) * 10.0)
    y_high = max(300.0, math.ceil(max(highs) / 10.0) * 10.0)
    base = [40, 54, 70, 180, 250, 300]
    ticks = sorted(set([y_low, y_high] + [value for value in base if y_low <= value <= y_high]))
    return y_low, y_high, ticks


def _agp_bottom_margin(legend_items: int) -> int:
    """Reserve enough bottom space for the wrapped outside-the-plot legend."""
    rows = max(1, math.ceil(legend_items / 2))
    return 62 + 30 * rows


def agp_profile_figure(glucose: dict, height: int = 580) -> go.Figure:
    """Full-width 24-hour 5/25/50/75/95 percentile profile with the 70--180 band.

    The percentile series are computed by the notebook and passed in through
    ``glucose["percentiles"]``. This factory only draws them; it never invents a
    series, never retrieves data, and stays autosized/responsive rather than pinned
    to a fixed desktop pixel width.

    The region between the actual 5th and 95th percentile curves is filled by
    absolute glucose value (``<54`` dark red, ``54--<70`` red, ``70--180`` green,
    ``>180--250`` yellow, ``>250`` orange). Polygons are clipped exactly at the
    54/70/180/250 thresholds---including sloped crossings between sample times---so
    a warm fill never appears inside the 70--180 target band. The envelope remains,
    but the 5/95 and 25/75 percentile boundary *lines* are
    intentionally not drawn. Only the green 50th-percentile median is exposed as a
    stroke, keeping the density distinction without implying a fixed percentile
    rank = severity mapping.
    """
    rows = _agp_rows(glucose.get("percentiles"))
    segments = _agp_segments(rows)
    has_data = bool(rows)

    figure = go.Figure()
    figure.add_hrect(y0=70, y1=180, fillcolor=TARGET_FILL, line_width=0, layer="below")

    if has_data:
        for color, label, low, high, lo_inclusive, hi_inclusive, rank in _AGP_VALUE_BANDS:
            y_low = -math.inf if low is None else float(low)
            y_high = math.inf if high is None else float(high)
            polygons: list[list[tuple[float, float]]] = []
            for segment in segments:
                polygons.extend(_agp_value_polygons(segment, y_low, y_high, lo_inclusive, hi_inclusive))
            for index, polygon in enumerate(polygons):
                figure.add_trace(
                    go.Scatter(
                        x=[point[0] for point in polygon],
                        y=[point[1] for point in polygon],
                        mode="lines",
                        fill="toself",
                        fillcolor=color,
                        line={"width": 0},
                        name=label,
                        legendgroup=label,
                        legendrank=rank,
                        showlegend=index == 0,
                        hoverinfo="skip",
                    )
                )

        median_x, median_y = _agp_series_xy(segments, "p50")
        figure.add_trace(
            go.Scatter(
                x=median_x,
                y=median_y,
                mode="lines",
                name="50th median",
                legendrank=8,
                line={"color": AGP_MEDIAN, "width": 2.4},
                hovertemplate="%{text}<br>median %{y:.0f} mg/dL<extra></extra>",
                text=_agp_series_text(segments),
            )
        )

    figure.add_hline(y=180, line={"color": AGP_TARGET_LINE, "width": 1})
    figure.add_hline(y=70, line={"color": AGP_TARGET_LINE, "width": 1})
    figure.add_hline(y=54, line={"color": AGP_LOW_LINE, "width": 1.4})

    y_low, y_high, y_ticks = _agp_y_axis(rows)
    visible_legend_items = (
        len({trace.legendgroup for trace in figure.data if trace.showlegend is not False})
        if has_data
        else 0
    )
    figure.update_layout(
        **_BASE_LAYOUT,
        height=height,
        autosize=True,
        showlegend=has_data,
        legend={
            "orientation": "h",
            "x": 0,
            "xanchor": "left",
            "y": -0.20,
            "yanchor": "top",
            "font": {"size": 11},
            "tracegroupgap": 2,
        },
    )
    figure.update_layout(
        margin={"l": 48, "r": 16, "t": 18, "b": _agp_bottom_margin(visible_legend_items) if has_data else 40}
    )
    figure.update_xaxes(
        range=[0, 1440],
        tickvals=list(range(0, 1441, 180)),
        ticktext=["12am", "3am", "6am", "9am", "12pm", "3pm", "6pm", "9pm", "12am"],
        gridcolor=GRID,
        title="",
    )
    figure.update_yaxes(
        range=[y_low, y_high],
        tickvals=y_ticks,
        ticktext=[str(int(value)) if float(value).is_integer() else str(value) for value in y_ticks],
        gridcolor=GRID,
        title="mg/dL",
    )
    return figure


def glucose_trace_figure(explorer: dict, height: int = 760) -> go.Figure:
    """Full-width timeline for the single selected CGM recording period."""
    figure = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.56, 0.21, 0.23],
        subplot_titles=(
            "Glucose · mg/dL",
            "Activity · steps / 30 min",
            "Sleep stages · minutes",
        ),
    )

    glucose = explorer.get("glucose", pd.DataFrame())
    if "session" not in glucose.columns:
        glucose = glucose.assign(session="latest_period")

    for session_name, rows in glucose.groupby("session", sort=False):
        for index, segment in enumerate(_glucose_segments(rows)):
            figure.add_trace(
                go.Scatter(
                    x=[_wall_clock(value) for value in segment["recorded_at"]],
                    y=segment["mg_dl"],
                    mode="lines",
                    name="Glucose",
                    showlegend=index == 0,
                    legendgroup="glucose",
                    line={"color": DUKE_NAVY, "width": 1.5},
                    hovertemplate=(
                        "%{x|%b %-d, %H:%M}<br>%{y:.0f} mg/dL"
                        "<extra>Glucose</extra>"
                    ),
                ),
                row=1,
                col=1,
            )
    figure.add_hrect(
        y0=70, y1=180, fillcolor=TARGET_FILL, line_width=0, layer="below", row=1, col=1
    )

    meals = explorer.get("meals", pd.DataFrame())
    if not meals.empty:
        meal_times = [_wall_clock(value) for value in meals["occurred_at"]]
        figure.add_trace(
            go.Scatter(
                x=meal_times,
                y=[_nearest_glucose(glucose, value) for value in meals["occurred_at"]],
                mode="markers",
                name="Meals",
                cliponaxis=False,
                marker={
                    "symbol": "diamond",
                    "size": 10,
                    "color": MEAL_AMBER,
                    "line": {"width": 1, "color": MEAL_BORDER},
                },
                customdata=_meal_customdata(meals),
                hovertemplate=(
                    "%{x|%b %-d, %H:%M}<br>%{customdata[0]} · %{customdata[1]}"
                    "<br>Carbs %{customdata[2]:.0f} g · Protein %{customdata[3]:.0f} g"
                    " · Fat %{customdata[4]:.0f} g · Fiber %{customdata[5]:.0f} g"
                    "<br>%{customdata[6]:.0f} kcal · %{customdata[7]}"
                    "<extra>Meal</extra>"
                ),
            ),
            row=1,
            col=1,
        )

    activity = explorer.get("activity", pd.DataFrame())
    if not activity.empty:
        figure.add_trace(
            go.Bar(
                x=[_wall_clock(value) for value in activity["bucket_at"]],
                y=activity["steps"],
                name="Activity",
                marker_color=ACTIVITY_BLUE,
                hovertemplate="%{x|%b %-d, %H:%M}<br>%{y:.0f} steps<extra>Activity</extra>",
            ),
            row=2,
            col=1,
        )

    sleep = explorer.get("sleep", pd.DataFrame())
    if not sleep.empty:
        starts = [_wall_clock(value) for value in sleep["start_at"]]
        deep = sleep["deep_minutes"].astype(float)
        light = sleep["light_minutes"].astype(float)
        rem = sleep["rem_minutes"].astype(float)
        for label, values, bases, color in (
            ("Deep", deep, [0.0] * len(starts), DEEP),
            ("Light", light, deep.tolist(), LIGHT),
            ("REM", rem, (deep + light).tolist(), REM),
        ):
            figure.add_trace(
                go.Bar(
                    x=starts,
                    y=values,
                    base=bases,
                    name=label,
                    marker_color=color,
                    customdata=[
                        [row.efficiency_percent, row.total_sleep_minutes]
                        for row in sleep.itertuples()
                    ],
                    hovertemplate=(
                        "%{x|%b %-d}<br>"
                        + label
                        + " %{y:.0f} min<br>efficiency %{customdata[0]:.0f}%"
                        " · total %{customdata[1]:.0f} min<extra>"
                        + label
                        + "</extra>"
                    ),
                ),
                row=3,
                col=1,
            )

    figure.update_layout(
        **_BASE_LAYOUT,
        height=height,
        autosize=True,
        barmode="overlay",
        legend={"orientation": "h", "yanchor": "top", "y": -0.16, "x": 0},
    )
    figure.update_yaxes(title="mg/dL", row=1, col=1)
    figure.update_yaxes(title="steps", row=2, col=1, rangemode="tozero")
    figure.update_yaxes(title="minutes", row=3, col=1, rangemode="tozero")

    span_start, span_end = recording_bounds(explorer)
    if span_start is not None and span_end is not None:
        dtick_ms, tickformat = _trace_axis(span_end - span_start)
        figure.update_xaxes(dtick=dtick_ms, tickformat=tickformat, gridcolor=GRID)
        pad = timedelta(minutes=45)
        figure.update_xaxes(range=[span_start - pad, span_end + pad])
        if not glucose.empty:
            lo = max(0.0, float(glucose["mg_dl"].min()) - 20)
            hi = float(glucose["mg_dl"].max()) + 45
            figure.update_yaxes(range=[lo, hi], row=1, col=1)
    else:
        figure.update_xaxes(tickformat="%b %-d", gridcolor=GRID)

    figure.update_xaxes(rangeslider={"visible": False}, row=3, col=1)
    return figure


def _chat_label(meal: dict) -> str:
    label = str(meal.get("label") or "Meal")
    suffix = "with walk" if meal.get("had_walk") else "no walk"
    if suffix not in label.lower():
        label = f"{label} ({suffix})"
    return label


def scripted_sushi_figure(analysis: dict, height: int = 400) -> go.Figure:
    """Inspectable two-meal comparison used by the scripted patient chat."""
    minutes = analysis["minutes"]
    figure = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.14,
        row_heights=[0.66, 0.34],
        subplot_titles=(
            "Glucose around each sushi meal · mg/dL",
            "Walking context · steps / 5 min",
        ),
    )

    meals = analysis["meals"]
    traces = analysis["traces"]
    activity = analysis["activity"]
    for meal, trace, steps in zip(meals, traces, activity):
        color = WITH_WALK if meal.get("had_walk") else NO_WALK
        label = _chat_label(meal)
        figure.add_trace(
            go.Scatter(
                x=minutes,
                y=trace["glucose"],
                mode="lines",
                name=label,
                legendgroup=label,
                line={"color": color, "width": 2.2},
                hovertemplate=(
                    "%{x:+d} min<br>%{y:.0f} mg/dL<extra>"
                    + label
                    + "</extra>"
                ),
            ),
            row=1,
            col=1,
        )
        figure.add_trace(
            go.Bar(
                x=minutes,
                y=steps["steps"],
                name=f"{label} steps",
                legendgroup=label,
                marker_color=color,
                opacity=0.55,
                hovertemplate=(
                    "%{x:+d} min<br>%{y:.0f} steps<extra>"
                    + label
                    + "</extra>"
                ),
            ),
            row=2,
            col=1,
        )

    figure.add_hrect(
        y0=70, y1=180, fillcolor=TARGET_FILL, line_width=0, layer="below", row=1, col=1
    )
    for row in (1, 2):
        figure.add_vline(
            x=0, line={"color": MUTED, "width": 1, "dash": "dash"}, row=row, col=1
        )
    figure.add_annotation(
        x=0,
        xref="x",
        y=0.97,
        yref="paper",
        text="Meal time",
        showarrow=False,
        xanchor="left",
        xshift=5,
        yanchor="top",
        font={"size": 11, "color": MUTED},
    )

    figure.update_layout(
        **_BASE_LAYOUT,
        height=height,
        autosize=True,
        legend={"orientation": "h", "yanchor": "top", "y": -0.18, "x": 0},
    )
    figure.update_xaxes(range=[min(minutes), max(minutes)], gridcolor=GRID)
    figure.update_xaxes(title="Minutes from meal", row=2, col=1)
    figure.update_yaxes(title="mg/dL", gridcolor=GRID, row=1, col=1)
    figure.update_yaxes(title="steps", gridcolor=GRID, rangemode="tozero", row=2, col=1)
    return figure
