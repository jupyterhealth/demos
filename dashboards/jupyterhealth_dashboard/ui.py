"""ipywidgets composition for the Laude dashboard.

This module only *lays out*. It accepts the plain view dict the notebook prepares ---
patient facts, comparison cards, per-session AGP metrics/bands/percentiles, provenance,
and per-session pandas frames for the explorer --- and returns one widget tree. All
retrieval, decoding, session filtering, AGP math, and previous/current derivation happen
in the notebook; no analytical math lives here and no browser-side JavaScript computes a
metric.
"""

from __future__ import annotations

from datetime import timedelta
from html import escape
from importlib import resources

import ipywidgets as widgets
import plotly.graph_objects as go

from .figures import (
    agp_profile_figure,
    explorer_figure,
    ppgr_comparison_figure,
    ppgr_distribution_figure,
    session_bounds,
)

FULL_WIDTH = widgets.Layout(width="100%")
_DIVIDER = "1px solid #66717e"
_PANEL_BORDER = "1px solid #d9e0e7"

# Conventional five-range order, printed goal, and bound copy.
BAND_ROWS = (
    ("very_high", "Very High", ">250 mg/dL", "Goal <5%"),
    ("high", "High", "181–250 mg/dL", "Goal <25%"),
    ("target", "Target", "70–180 mg/dL", "Goal ≥70%"),
    ("low", "Low", "54–69 mg/dL", "Goal <4%"),
    ("very_low", "Very Low", "<54 mg/dL", "Goal <1%"),
)


def load_theme() -> widgets.HTML:
    """Embed the packaged stylesheet as notebook output without remote assets."""
    css = resources.files("jupyterhealth_dashboard").joinpath("theme.css").read_text()
    return widgets.HTML(value=f"<style>{css}</style>")


def _html(markup: str) -> widgets.HTML:
    return widgets.HTML(value=markup, layout=FULL_WIDTH)


def _figure(figure: go.Figure) -> go.FigureWidget:
    widget = go.FigureWidget(figure)
    widget._config = {"displayModeBar": False, "responsive": True}
    return widget


def _section(*children: widgets.Widget) -> widgets.VBox:
    return widgets.VBox(
        list(children),
        layout=widgets.Layout(
            width="100%",
            border_top=_DIVIDER,
            padding="15px 0px 0px 0px",
            margin="26px 0px 0px 0px",
        ),
    )


def _section_head(title: str, *controls: widgets.Widget) -> widgets.HBox:
    return widgets.HBox(
        [
            _html(f'<h2 class="jh-h2">{escape(title)}</h2>'),
            *controls,
        ],
        layout=widgets.Layout(
            width="100%",
            display="flex",
            flex_flow="row",
            align_items="flex-end",
            justify_content="space-between",
            margin="0 0 13px 0",
        ),
    )


# --------------------------------------------------------------------------------------
# patient header


def _patient_header(view: dict) -> widgets.HTML:
    patient = view["patient"]
    facts = "".join(
        f'<span class="jh-fact">{escape(fact)}</span>' for fact in patient["facts"] if fact
    )
    return _html(
        '<header class="jh-patient" aria-label="Patient context">'
        f'<div class="jh-avatar" role="img" aria-label="{escape(patient["name"])} initials, '
        f'{escape(patient["initials"])}">{escape(patient["initials"])}</div>'
        '<div class="jh-patient-body">'
        f'<h1 class="jh-patient-name">{escape(patient["name"])}</h1>'
        f'<div class="jh-facts">{facts}</div>'
        "</div></header>"
    )


# --------------------------------------------------------------------------------------
# clinical context: explicit previous -> current comparison, never a bare sparkline


def _context_card(card: dict) -> str:
    if card.get("comparison"):
        reading = (
            '<div class="jh-compare">'
            f'<span class="jh-compare-prev">{escape(card["previous"])}'
            f'<i>{escape(card["previous_date"])}</i></span>'
            '<span class="jh-compare-arrow" aria-hidden="true">→</span>'
            f'<span class="jh-compare-now">{escape(card["current"])}'
            f'<i>{escape(card["current_date"])}</i></span>'
            "</div>"
        )
        delta = (
            f'<span class="jh-delta jh-delta-{escape(card["direction"])}">'
            f'{escape(card["delta"])} <span aria-hidden="true">{escape(card["arrow"])}</span>'
            f'<span class="sr-only"> {escape(card["direction"])}</span></span>'
        )
    else:
        reading = (
            '<div class="jh-compare">'
            f'<span class="jh-compare-now">{escape(card["current"])}</span>'
            "</div>"
        )
        delta = f'<span class="jh-stable">{escape(card["detail"])}</span>'
    return (
        '<article class="jh-lab-card">'
        f'<h3>{escape(card["label"])}</h3>'
        f"{reading}"
        f'<div class="jh-lab-delta">{delta}</div>'
        "</article>"
    )


def _context_section(view: dict) -> widgets.HTML:
    cards = "".join(_context_card(card) for card in view["context_cards"])
    return _html(
        '<section class="jh-section">'
        '<div class="jh-section-head"><h2 class="jh-h2">Labs and vitals</h2></div>'
        f'<div class="jh-lab-grid">{cards}</div>'
        "</section>"
    )


# --------------------------------------------------------------------------------------
# AGP report block: five-band strip + glucose metrics, then the wide percentile plot


def _band_strip_html(session: dict) -> str:
    by_key = {band["key"]: band for band in session["bands"]}
    segments = []
    rows = []
    for key, label, bounds, goal in BAND_ROWS:
        band = by_key.get(key, {"percent": 0.0})
        percent = float(band["percent"])
        # The strip is a geometric encoding: each segment must occupy its actual share.
        # The adjacent rows retain exact values for segments too short to label legibly.
        in_strip_label = f"<span>{percent:.0f}%</span>" if percent >= 8.0 else ""
        segments.append(
            f'<div class="jh-agp-seg jh-band-{key}" style="flex-grow:{percent:.3f}" '
            f'title="{escape(label)} {percent:.1f}%">'
            f"{in_strip_label}</div>"
        )
        rows.append(
            '<div class="jh-agp-range-row">'
            f'<i class="jh-band-{key}" aria-hidden="true"></i>'
            f'<b>{escape(label)}</b>'
            f'<span class="jh-bounds">{escape(bounds)}</span>'
            f'<span class="jh-goal">{escape(goal)}</span>'
            f'<span class="jh-pct">{percent:.1f}%</span>'
            "</div>"
        )
    return (
        '<div class="jh-agp-block jh-agp-ranges">'
        '<div class="jh-agp-head">Time in ranges</div>'
        '<div class="jh-agp-range-body">'
        f'<div class="jh-agp-strip">{"".join(segments)}</div>'
        f'<div class="jh-agp-range-rows">{"".join(rows)}</div>'
        "</div>"
        '<p class="jh-goal-note">Each 1% time in range is about 15 minutes.</p>'
        "</div>"
    )


def _metric_row(label: str, value: str, goal: str) -> str:
    return (
        '<div class="jh-glucose-metric">'
        f'<span class="jh-metric-label">{escape(label)}</span>'
        f'<span class="jh-metric-value">{escape(value)}</span>'
        f'<span class="jh-metric-goal">{escape(goal)}</span>'
        "</div>"
    )


def _fmt(value: float | None, unit: str, decimals: int) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{decimals}f} {unit}"


def _metrics_html(session: dict) -> str:
    metrics = session["metrics"]
    context = (
        '<div class="jh-agp-context">'
        f'<div><span>Period</span><b>{escape(session["period"])}</b></div>'
        f'<div><span>Time CGM active</span><b>'
        f'{_fmt(session["time_active_percent"], "%", 1)}</b></div>'
        "</div>"
    )
    rows = "".join(
        (
            _metric_row("Average glucose", _fmt(metrics["mean_mg_dl"], "mg/dL", 0),
                        "Goal <154 mg/dL"),
            _metric_row("GMI", _fmt(metrics["gmi_percent"], "%", 1), "Goal <7%"),
            _metric_row("Glucose variability", _fmt(metrics["cv_percent"], "%", 1),
                        "Goal ≤36% (CV)"),
        )
    )
    return (
        '<div class="jh-agp-block jh-agp-metrics">'
        '<div class="jh-agp-head">Glucose metrics</div>'
        f"{context}{rows}"
        "</div>"
    )


def _agp_report_html(session: dict) -> str:
    return (
        '<div class="jh-agp-report">'
        f"{_band_strip_html(session)}"
        f"{_metrics_html(session)}"
        "</div>"
    )


def _session_dropdown(options: list[tuple[str, str]], on_change) -> widgets.Dropdown:
    """A compact native session select; the report deliberately has no segmented switch."""
    control = widgets.Dropdown(
        options=options,
        value=options[0][1],
        layout=widgets.Layout(width="285px"),
    )
    control.add_class("jh-session-select")
    control.observe(lambda change: on_change(change["new"]), names="value")
    return control


# --------------------------------------------------------------------------------------
# postprandial response comparison: prepared view in, chart and summary out


def _ppgr_row(label: str, earlier: str, later: str, change: str) -> str:
    # ``data-label`` lets the phone layout pair each value with its column name once the
    # header row is hidden. A count with no delta is marked so the stacked layout drops the
    # dangling empty "Change" line instead of printing the label with no value. Each value is
    # wrapped in an explicit ``jh-ppgr-value`` element so the phone grid has a real second
    # column to constrain; a bare text node would be auto-placed into the label column and
    # overflow the card.
    change_class = "jh-ppgr-change" + ("" if change else " jh-ppgr-empty")

    def value(text: str) -> str:
        return f'<span class="jh-ppgr-value">{escape(text)}</span>'

    return (
        '<div class="jh-ppgr-row">'
        f'<span class="jh-ppgr-metric">{escape(label)}</span>'
        f'<span data-label="Earlier period">{value(earlier)}</span>'
        f'<span data-label="Later period">{value(later)}</span>'
        f'<span class="{change_class}" data-label="Change">{value(change)}</span>'
        "</div>"
    )


def _ppgr_summary_html(view: dict) -> widgets.HTML:
    comparison = view["comparison"]
    sessions = {session["name"]: session for session in view["sessions"]}
    base, follow = sessions["baseline"], sessions["follow_up"]
    adherence = view["adherence"]
    percent = comparison["mean_iauc_percent"]
    change = (
        f'{comparison["mean_iauc_delta"]:+,.0f} mg/dL·min'
        + (f" ({percent:+.1f}%)" if percent is not None else "")
    )
    activity_change = round(
        follow["mean_activity_first_30"] - base["mean_activity_first_30"], 1
    )
    rows = "".join(
        [
            _ppgr_row(
                "Mean iAUC",
                f'{base["mean_iauc"]:,.0f}',
                f'{follow["mean_iauc"]:,.0f}',
                change,
            ),
            _ppgr_row(
                "Mean activity, first 30 min",
                f'{base["mean_activity_first_30"]:.0f} steps/min',
                f'{follow["mean_activity_first_30"]:.0f} steps/min',
                f"{activity_change:+.0f} steps/min",
            ),
            _ppgr_row(
                "Eligible meals",
                f'{base["eligible_meals"]} of {base["total_meals"]}',
                f'{follow["eligible_meals"]} of {follow["total_meals"]}',
                "",
            ),
            _ppgr_row(
                "Meals meeting the post-meal walk rule",
                f'{adherence["baseline"]["walks"]} of {adherence["baseline"]["meals"]}',
                f'{adherence["follow_up"]["walks"]} of {adherence["follow_up"]["meals"]}',
                "",
            ),
        ]
    )
    head = (
        '<div class="jh-ppgr-row jh-ppgr-head">'
        '<span class="jh-ppgr-metric">Comparison summary</span>'
        f'<span>{escape(base["label"])}</span><span>{escape(follow["label"])}</span><span>Change</span></div>'
    )
    return _html(
        '<section class="jh-agp-block jh-ppgr-summary">'
        f"{head}{rows}"
        "</section>"
    )


def _ppgr_section(view: dict) -> widgets.VBox:
    return _section(
        _section_head("Postprandial response comparison"),
        _figure(ppgr_comparison_figure(view)),
        _ppgr_summary_html(view),
        widgets.VBox(
            [
                _html('<div class="jh-agp-head jh-agp-head-wide">iAUC by meal</div>'),
                _figure(ppgr_distribution_figure(view)),
            ],
            layout=FULL_WIDTH,
        ),
    )


def build_dashboard(view: dict) -> widgets.VBox:
    """Compose the clinician dashboard widget tree for Voilà or notebook output."""
    sessions = view["sessions"]
    explorers = {explorer["name"]: explorer for explorer in view["explorers"]}
    initial = sessions[0]["name"]

    metrics_by = {session["name"]: _agp_report_html(session) for session in sessions}
    profile_by = {session["name"]: _figure(agp_profile_figure(session)) for session in sessions}

    # Voilà 0.5.x reliably renders a new FigureWidget supplied through a container,
    # while live Plotly relayout messages are not dependable after initial render.
    # Prepare every permitted range before a widget is wrapped or displayed, then the
    # range controls only replace the holder's child.  ``session_bounds`` returns the
    # notebook's local wall-clock datetimes, and ISO strings preserve those exact bounds.
    explorers_by_session: dict[str, dict[str, go.FigureWidget]] = {}
    explorer_tick_styles = {
        "1": (6 * 60 * 60 * 1000, "%a %-d<br>%H:%M"),
        "3": (12 * 60 * 60 * 1000, "%a %-d<br>%H:%M"),
        "7": (24 * 60 * 60 * 1000, "%a %-d"),
        "all": (7 * 24 * 60 * 60 * 1000, "%b %-d"),
    }
    for name, explorer in explorers.items():
        start, end = session_bounds(explorer)
        ranges = {"all": (start, end)}
        if start is not None and end is not None:
            ranges.update(
                {str(days): (max(start, end - timedelta(days=days)), end) for days in (1, 3, 7)}
            )
        prepared = {}
        for days, bounds in ranges.items():
            figure = explorer_figure(explorer)
            span_start, span_end = bounds
            if span_start is not None and span_end is not None:
                date_range = [span_start.isoformat(), span_end.isoformat()]
                for axis in (figure.layout.xaxis, figure.layout.xaxis2, figure.layout.xaxis3):
                    axis.range = date_range
                    axis.dtick, axis.tickformat = explorer_tick_styles[days]
            prepared[days] = _figure(figure)
        explorers_by_session[name] = prepared
    report_widget = _html(metrics_by[initial])

    reset_button = widgets.Button(
        description="Reset",
        layout=widgets.Layout(width="auto"),
    )
    reset_button.add_class("jh-reset")

    range_values = (("1", "1"), ("3", "3"), ("7", "7"), ("All", "all"))
    range_buttons = {
        days: widgets.Button(description=label, layout=widgets.Layout(width="auto"))
        for label, days in range_values
    }
    for button in range_buttons.values():
        button.add_class("jh-range-button")
    range_controls = widgets.HBox(
        [range_buttons[days] for _, days in range_values],
        layout=widgets.Layout(display="flex", flex_flow="row nowrap", width="auto"),
    )
    range_controls.add_class("jh-range-controls")

    def apply_range(days: str) -> None:
        for value, button in range_buttons.items():
            if value == days:
                button.add_class("jh-range-active")
            else:
                button.remove_class("jh-range-active")
        explorer_section.children = (
            *explorer_section.children[:-1],
            explorers_by_session[selector.value][days],
        )

    def on_session_change(name: str) -> None:
        report_widget.value = metrics_by[name]
        agp_section.children = (*agp_section.children[:-1], profile_by[name])
        apply_range("all")

    def on_reset(_: widgets.Button) -> None:
        apply_range("all")

    selector = _session_dropdown(
        [(session["label"], session["name"]) for session in sessions], on_session_change
    )
    reset_button.on_click(on_reset)
    for days, button in range_buttons.items():
        button.on_click(lambda _, days=days: apply_range(days))
    agp_section = _section(
        _section_head("Ambulatory glucose profile", selector),
        report_widget,
        _html('<div class="jh-agp-head jh-agp-head-wide">24-hour glucose profile</div>'),
        profile_by[initial],
    )
    explorer_section = _section(
        _section_head("Glucose explorer", widgets.HBox([range_controls, reset_button])),
        _html('<p class="jh-note">Meals, activity and sleep share one time axis.</p>'),
        explorers_by_session[initial]["all"],
    )
    apply_range("all")

    sections = [
        load_theme(),
        _patient_header(view),
        _context_section(view),
        agp_section,
        explorer_section,
    ]
    if view.get("ppgr_comparison"):
        sections.append(_ppgr_section(view["ppgr_comparison"]))

    return widgets.VBox(
        sections,
        layout=widgets.Layout(
            width="100%",
            max_width="1440px",
            margin="0 auto",
            padding="0 28px 120px",
        ),
    )
