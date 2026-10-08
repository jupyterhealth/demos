"""ipywidgets composition for the Laude dashboard.

This module only *lays out*. It accepts the plain view dict the notebook prepares ---
patient facts, comparison cards, per-session AGP metrics/bands/percentiles, provenance,
and per-session pandas frames for the explorer --- and returns one widget tree. All
retrieval, decoding, session filtering, AGP math, and previous/current derivation happen
in the notebook; no analytical math lives here and no browser-side JavaScript computes a
metric.
"""

from __future__ import annotations

from html import escape
from importlib import resources

import ipywidgets as widgets
import plotly.graph_objects as go

from .figures import agp_profile_figure, explorer_figure, session_bounds

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
    widget.layout.width = None
    widget.layout.autosize = True
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
        segments.append(
            f'<div class="jh-agp-seg jh-band-{key}" style="flex-grow:{max(percent, 1.4):.3f}" '
            f'title="{escape(label)} {percent:.1f}%">'
            f'<span>{percent:.0f}%</span></div>'
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


def _profile_panel(profile: go.FigureWidget) -> widgets.VBox:
    return widgets.VBox(
        [
            _html('<div class="jh-agp-head jh-agp-head-wide">24-hour glucose profile</div>'),
            profile,
        ],
        layout=FULL_WIDTH,
    )


def _segmented(options: list[tuple[str, str]], on_change) -> widgets.ToggleButtons:
    control = widgets.ToggleButtons(
        options=options,
        value=options[0][1],
        layout=widgets.Layout(width="auto"),
        style={"button_width": "auto"},
    )
    control.add_class("jh-segmented")
    control.observe(lambda change: on_change(change["new"]), names="value")
    return control


def build_dashboard(view: dict) -> widgets.VBox:
    """Compose the clinician dashboard widget tree for Voilà or notebook output."""
    sessions = view["sessions"]
    explorers = {explorer["name"]: explorer for explorer in view["explorers"]}
    initial = sessions[0]["name"]

    metrics_by = {session["name"]: _agp_report_html(session) for session in sessions}
    profile_by = {session["name"]: _figure(agp_profile_figure(session)) for session in sessions}
    profile_panels = {session["name"]: _profile_panel(profile_by[session["name"]])
                      for session in sessions}
    explorer_by = {name: _figure(explorer_figure(explorer))
                   for name, explorer in explorers.items()}
    bounds_by = {name: session_bounds(explorer) for name, explorer in explorers.items()}

    report_widget = _html(metrics_by[initial])
    profile_box = widgets.Box([profile_panels[initial]], layout=FULL_WIDTH)
    explorer_box = widgets.Box([explorer_by[initial]], layout=FULL_WIDTH)

    reset_button = widgets.Button(
        description="Reset to All",
        layout=widgets.Layout(width="auto"),
    )
    reset_button.add_class("jh-reset")

    def set_full_range(name: str) -> None:
        bounds = bounds_by[name]
        if not bounds or bounds[0] is None:
            return
        start, end = bounds
        explorer = explorer_by[name]
        for axis in ("xaxis", "xaxis2", "xaxis3"):
            getattr(explorer.layout, axis).range = [start, end]

    def on_session_change(name: str) -> None:
        report_widget.value = metrics_by[name]
        profile_box.children = (profile_panels[name],)
        explorer_box.children = (explorer_by[name],)
        set_full_range(name)

    def on_reset(_: widgets.Button) -> None:
        set_full_range(selector.value)

    selector = _segmented(
        [(session["label"], session["name"]) for session in sessions], on_session_change
    )
    reset_button.on_click(on_reset)

    return widgets.VBox(
        [
            load_theme(),
            _patient_header(view),
            _context_section(view),
            _section(
                _section_head("Ambulatory glucose profile", selector),
                report_widget,
                profile_box,
            ),
            _section(
                _section_head("Glucose explorer", reset_button),
                _html(
                    '<p class="jh-note">Presets 1 / 3 / 7 days or All · drag the overview slider '
                    "to adjust the window · meals, activity and sleep share one time axis.</p>"
                ),
                explorer_box,
            ),
        ],
        layout=widgets.Layout(
            width="100%",
            max_width="1440px",
            margin="0 auto",
            padding="0 28px 120px",
        ),
    )
