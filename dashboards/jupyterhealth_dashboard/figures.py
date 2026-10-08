"""Plotly figure factories for the Laude dashboard.

These factories only *draw*. They accept the plain per-session dicts and pandas frames
the notebook prepares, so every figure in the notebook and in the served Voilà page is
drawn from the same numbers the notebook computed --- no analytical math and no data
retrieval live here.

Two rules are encoded deliberately:

* the conventional AGP palette and goals (five ranges, 70--180 target band, percentile
  ribbons) are used instead of a generic product palette; and
* the glucose trace is split into contiguous segments wherever the recording has a gap,
  so a missing window is never bridged by a straight line.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

DUKE_NAVY = "#012169"
DUKE_BLUE = "#00539b"
INK = "#111318"
MUTED = "#5b6674"
LINE = "#d9e0e7"
GRID = "#dfe5eb"
TARGET_FILL = "#edf5eb"
TARGET_LINE = "#c7dcc0"
AGP95_FILL = "#f4d9b7"
AGP75_FILL = "#f2bc84"
MEAL_AMBER = "#d49318"
MEAL_BORDER = "#704b08"
ACTIVITY_BLUE = "#617fa8"
DEEP = "#2c5282"
LIGHT = "#63a4d8"
REM = "#8b5cf6"
PPGR_BASELINE = "#6b7686"
PPGR_FOLLOW = DUKE_NAVY
PPGR_BASELINE_FILL = "rgba(107, 118, 134, 0.12)"
PPGR_FOLLOW_FILL = "rgba(1, 33, 105, 0.12)"

# 1440 px report maximum less 28 px horizontal padding; fixes Voilà FigureWidget's stale
# 700 px first-paint raster at the approved 1600 px desktop demo viewport.
DESKTOP_DEMO_CONTENT_WIDTH = 1384

_SIX_HOURS_MS = 6 * 3600 * 1000
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


def _meal_label(label: str) -> str:
    """Presentation-only: drop the generator's ``Synthetic`` prefix and sentence-case."""
    text = str(label).removeprefix("Synthetic ").strip() or str(label)
    return text[:1].upper() + text[1:]


def _minute_label(minute: int) -> str:
    hours, remainder = divmod(int(minute), 60)
    return f"{hours:02d}:{remainder:02d}"


def agp_profile_figure(session: dict, height: int = 430) -> go.Figure:
    """Wide 24-hour 5/25/50/75/95 percentile profile with the 70--180 target band."""
    percentiles = session["percentiles"]
    minutes = [point["minute"] for point in percentiles]
    p05 = [point["p05"] for point in percentiles]
    p25 = [point["p25"] for point in percentiles]
    p50 = [point["p50"] for point in percentiles]
    p75 = [point["p75"] for point in percentiles]
    p95 = [point["p95"] for point in percentiles]

    figure = go.Figure()
    figure.add_hrect(y0=70, y1=180, fillcolor=TARGET_FILL, line_width=0, layer="below")
    if minutes:
        figure.add_trace(
            go.Scatter(
                x=minutes, y=p95, mode="lines", line={"width": 0},
                hoverinfo="skip", showlegend=False,
            )
        )
        figure.add_trace(
            go.Scatter(
                x=minutes, y=p05, mode="lines", fill="tonexty", fillcolor=AGP95_FILL,
                line={"width": 0}, name="5th–95th", hoverinfo="skip",
            )
        )
        figure.add_trace(
            go.Scatter(
                x=minutes, y=p75, mode="lines", line={"width": 0},
                hoverinfo="skip", showlegend=False,
            )
        )
        figure.add_trace(
            go.Scatter(
                x=minutes, y=p25, mode="lines", fill="tonexty", fillcolor=AGP75_FILL,
                line={"width": 0}, name="25th–75th", hoverinfo="skip",
            )
        )
        figure.add_trace(
            go.Scatter(
                x=minutes, y=p50, mode="lines", name="Median (50th)",
                line={"color": DUKE_NAVY, "width": 2.4},
                hovertemplate="%{text}<br>median %{y:.0f} mg/dL<extra></extra>",
                text=[_minute_label(value) for value in minutes],
            )
        )

    # Right-edge percentile labels, mirroring the conventional report.
    for rank, series in (("95%", p95), ("75%", p75), ("50%", p50), ("25%", p25), ("5%", p05)):
        if not series:
            continue
        figure.add_annotation(
            x=1440, y=series[-1], text=rank, xanchor="left", showarrow=False,
            xshift=6, font={"size": 11, "color": MUTED},
        )

    figure.add_hline(y=180, line={"color": TARGET_LINE, "width": 1})
    figure.add_hline(y=70, line={"color": TARGET_LINE, "width": 1})
    figure.update_layout(
        **_BASE_LAYOUT,
        width=DESKTOP_DEMO_CONTENT_WIDTH,
        height=height,
        autosize=False,
        showlegend=False,
    )
    figure.update_layout(margin={"l": 48, "r": 42, "t": 18, "b": 40})
    figure.update_xaxes(
        range=[0, 1440],
        tickvals=list(range(0, 1441, 180)),
        ticktext=["12am", "3am", "6am", "9am", "12pm", "3pm", "6pm", "9pm", "12am"],
        gridcolor=GRID,
        title="",
    )
    y_ticks = [40, 54, 70, 180, 250, 300]
    figure.update_yaxes(
        range=[40, 300],
        tickvals=y_ticks,
        ticktext=[str(value) for value in y_ticks],
        gridcolor=GRID,
        title="mg/dL",
    )
    return figure


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


def explorer_figure(explorer: dict, height: int = 760) -> go.Figure:
    """Full-width timeline for one selected recording session."""
    figure = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.56, 0.21, 0.23],
        subplot_titles=("Glucose · mg/dL", "Activity · steps / 30 min", "Sleep stages · minutes"),
    )

    glucose = explorer["glucose"]
    session_styles = {"baseline": ("Glucose", "#6b7686"), "follow_up": ("Glucose", DUKE_BLUE)}
    if "session" not in glucose.columns:
        glucose = glucose.assign(session=explorer.get("name", "baseline"))
    for session_name, rows in glucose.groupby("session", sort=False):
        label, color = session_styles.get(session_name, ("Glucose", DUKE_BLUE))
        for index, segment in enumerate(_glucose_segments(rows)):
            figure.add_trace(
                go.Scatter(
                    x=[_wall_clock(value) for value in segment["recorded_at"]],
                    y=segment["mg_dl"],
                    mode="lines",
                    name=label,
                    showlegend=index == 0,
                    legendgroup=session_name,
                    line={"color": color, "width": 1.5},
                    hovertemplate=(
                        "%{x|%b %-d, %H:%M}<br>%{y:.0f} mg/dL"
                        f"<extra>{label}</extra>"
                    ),
                ),
                row=1,
                col=1,
            )
    figure.add_hrect(
        y0=70, y1=180, fillcolor=TARGET_FILL, line_width=0, layer="below", row=1, col=1
    )

    meals = explorer["meals"]
    if not meals.empty:
        figure.add_trace(
            go.Scatter(
                x=[_wall_clock(value) for value in meals["occurred_at"]],
                y=[_nearest_glucose(glucose, value) for value in meals["occurred_at"]],
                mode="markers",
                name="Meals",
                marker={
                    "symbol": "diamond",
                    "size": 10,
                    "color": MEAL_AMBER,
                    "line": {"width": 1, "color": MEAL_BORDER},
                },
                customdata=[
                    [_meal_label(row.label), row.meal_type, row.carbohydrate_g, row.calories_kcal]
                    for row in meals.itertuples()
                ],
                hovertemplate=(
                    "%{x|%b %-d, %H:%M}<br>%{customdata[0]} · %{customdata[1]}"
                    "<br>%{customdata[2]:.0f} g carbs · %{customdata[3]:.0f} kcal"
                    "<extra>Meal</extra>"
                ),
            ),
            row=1,
            col=1,
        )

    activity = explorer["activity"]
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

    sleep = explorer["sleep"]
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
                        "%{x|%b %-d}<br>" + label + " %{y:.0f} min"
                        "<br>efficiency %{customdata[0]:.0f}% · total %{customdata[1]:.0f} min"
                        "<extra>" + label + "</extra>"
                    ),
                ),
                row=3,
                col=1,
            )

    figure.update_layout(
        **_BASE_LAYOUT,
        width=DESKTOP_DEMO_CONTENT_WIDTH,
        height=height,
        autosize=False,
        barmode="overlay",
        legend={"orientation": "h", "yanchor": "top", "y": -0.16, "x": 0},
    )
    figure.update_yaxes(title="mg/dL", row=1, col=1)
    figure.update_yaxes(title="steps", row=2, col=1, rangemode="tozero")
    figure.update_yaxes(title="minutes", row=3, col=1, rangemode="tozero")
    figure.update_xaxes(dtick=_SIX_HOURS_MS, tickformat="%H:%M", gridcolor=GRID)

    figure.update_xaxes(
        rangeslider={"visible": False},
        row=3,
        col=1,
    )
    span_start, span_end = session_bounds(explorer)
    if span_start is not None:
        # Default and reset both show the complete selected recording.
        figure.update_xaxes(range=[span_start, span_end])
    return figure


def session_bounds(explorer: dict) -> tuple[datetime | None, datetime | None]:
    glucose = explorer["glucose"]
    if glucose.empty:
        return None, None
    start = min(_wall_clock(value) for value in glucose["recorded_at"])
    end = max(_wall_clock(value) for value in glucose["recorded_at"])
    return start, end


def ppgr_comparison_figure(view: dict, height: int = 560) -> go.Figure:
    """Baseline vs follow-up mean glucose change with the aligned activity row beneath it.

    Only the prepared view is drawn: the notebook supplies the shared relative-minute axis,
    each session's mean change and 25th/75th range, and the mean aligned steps per minute.
    Every glucose value is already change from the meal's own pre-meal baseline.
    """
    minutes = view["x_minutes"]
    figure = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.12,
        row_heights=[0.66, 0.34],
        subplot_titles=(
            "Glucose change from pre-meal baseline · mg/dL",
            "Aligned activity · steps / min",
        ),
    )
    # Panel captions are Plotly annotations, so they neither wrap nor shrink on their own.
    # On a 430 px phone the long glucose caption overruns the canvas and clips its trailing
    # unit, so stack it onto two short lines at a caption size and reserve top margin for
    # both lines. The activity caption already fits one line. No values or units change.
    if len(figure.layout.annotations) >= 2:
        figure.layout.annotations[0].text = "Glucose change from<br>pre-meal baseline · mg/dL"
    for annotation in figure.layout.annotations:
        annotation.font.size = 13
    for session in view["sessions"]:
        follow = session["name"] == "follow_up"
        color = PPGR_FOLLOW if follow else PPGR_BASELINE
        fill = PPGR_FOLLOW_FILL if follow else PPGR_BASELINE_FILL
        label = session["label"]
        # Rank baseline and follow-up as two blocks (10s then 20s) so the band, its mean, and its
        # activity stay together and the horizontal legend wraps in a readable order on a phone.
        legend_rank = 20 if follow else 10
        # 25th-75th percentile band across the eligible meals, then the mean curve on top. The
        # low edge carries the legend key: a filled Scatter swatch renders as a band using its
        # fillcolor, so the ribbon is attributable from the legend alone.
        figure.add_trace(
            go.Scatter(
                x=minutes,
                y=session["glucose_high"],
                mode="lines",
                line={"width": 0},
                hoverinfo="skip",
                showlegend=False,
                legendgroup=session["name"],
                legendrank=legend_rank,
            ),
            row=1,
            col=1,
        )
        figure.add_trace(
            go.Scatter(
                x=minutes,
                y=session["glucose_low"],
                mode="lines",
                fill="tonexty",
                fillcolor=fill,
                line={"width": 0},
                hoverinfo="skip",
                name=f"{label} 25th–75th percentile",
                showlegend=True,
                legendgroup=session["name"],
                legendrank=legend_rank + 1,
            ),
            row=1,
            col=1,
        )
        figure.add_trace(
            go.Scatter(
                x=minutes,
                y=session["glucose_mean"],
                mode="lines",
                name=f"{label} glucose",
                line={"color": color, "width": 2.6},
                legendgroup=session["name"],
                legendrank=legend_rank + 2,
                hovertemplate=(
                    label + " glucose %{x:+d} min<br>%{y:+.0f} mg/dL<extra></extra>"
                ),
            ),
            row=1,
            col=1,
        )
    # Activity is drawn after the glucose block; legendrank slots each dashed activity trace
    # directly after its session's band and mean, so the shared legend still reads baseline
    # group then follow-up group. Both activity traces are dashed with no area fill, so the
    # style itself separates activity from the solid glucose curves regardless of panel position.
    for session in view["sessions"]:
        follow = session["name"] == "follow_up"
        color = PPGR_FOLLOW if follow else PPGR_BASELINE
        label = session["label"]
        legend_rank = 20 if follow else 10
        figure.add_trace(
            go.Scatter(
                x=minutes,
                y=session["activity_mean"],
                mode="lines",
                name=f"{label} activity",
                line={"color": color, "width": 1.9, "dash": "dash"},
                legendgroup=session["name"],
                legendrank=legend_rank + 3,
                hovertemplate=(
                    label + " activity %{x:+d} min<br>%{y:.1f} steps/min<extra></extra>"
                ),
            ),
            row=2,
            col=1,
        )
    # Meal time is a shared reference, so the rule spans both panels but is labelled once, in the
    # glucose panel, using the muted slate system color instead of the warm meal-marker brown.
    for row in (1, 2):
        figure.add_vline(
            x=0, line={"color": MUTED, "width": 1, "dash": "dash"}, row=row, col=1
        )
    figure.add_annotation(
        x=0,
        xref="x",
        y=0.965,
        yref="paper",
        text="Meal time",
        showarrow=False,
        xanchor="left",
        xshift=5,
        yanchor="top",
        font={"size": 11, "color": MUTED},
    )
    figure.add_hline(y=0, line={"color": "#b9c3cd", "width": 1}, row=1, col=1)
    figure.update_layout(
        **_BASE_LAYOUT,
        height=height,
        legend={"orientation": "h", "yanchor": "top", "y": -0.16, "x": 0, "font": {"size": 11}},
    )
    # Reserve room for the two-line glucose caption; annotations are not auto-margined.
    figure.update_layout(margin={"l": 48, "r": 16, "t": 48, "b": 40})
    figure.update_xaxes(
        range=[min(minutes), max(minutes)],
        tickvals=[-30, 0, 30, 60, 90, 120, 150, 180],
        gridcolor=GRID,
    )
    figure.update_xaxes(title="Minutes from meal", row=2, col=1)
    figure.update_yaxes(title="Δ glucose · mg/dL", gridcolor=GRID, row=1, col=1)
    figure.update_yaxes(title="steps/min", gridcolor=GRID, rangemode="tozero", row=2, col=1)
    return figure


def ppgr_distribution_figure(view: dict, height: int = 250) -> go.Figure:
    """Per-meal iAUC distribution for each session, with the comparator marked."""
    figure = go.Figure()
    for session in view["sessions"]:
        follow = session["name"] == "follow_up"
        color = PPGR_FOLLOW if follow else PPGR_BASELINE
        figure.add_trace(
            go.Box(
                x=session["iauc_values"],
                name=session["label"],
                orientation="h",
                marker={"color": color, "size": 6},
                line={"color": color, "width": 1.4},
                fillcolor=PPGR_FOLLOW_FILL if follow else PPGR_BASELINE_FILL,
                boxpoints="all",
                jitter=0.5,
                pointpos=0,
                hovertemplate=session["label"] + "<br>%{x:.0f} mg/dL·min<extra></extra>",
            )
        )
    figure.add_vline(
        x=view["comparison"]["comparator_value"],
        line={"color": DUKE_BLUE, "width": 1.4, "dash": "dot"},
        annotation_text="earlier-period median",
        annotation_position="top",
    )
    figure.update_layout(**_BASE_LAYOUT, height=height, showlegend=False)
    figure.update_layout(margin={"l": 104, "r": 24, "t": 34, "b": 40})
    figure.update_xaxes(title="iAUC · mg/dL·min", gridcolor=GRID, rangemode="tozero")
    figure.update_yaxes(showgrid=False)
    return figure
