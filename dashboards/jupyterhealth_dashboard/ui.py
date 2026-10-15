"""ipywidgets composition for the CGM demo dashboard.

This module only *lays out*. It accepts the plain view dict the notebook
prepares --- role copy, patient facts, latest clinical values, medication
state, glucose metrics, the selected CGM explorer frame, and optional scripted
chat --- and returns one widget tree. All retrieval, decoding, period
detection, and metric math happen in the notebook; no analytical math lives
here and no browser-side JavaScript computes a metric.
"""

from __future__ import annotations

from html import escape
from importlib import resources

import ipywidgets as widgets
import plotly.graph_objects as go

from .chat import scripted_chat_widget
from .core import (
    PATIENT_VIEW,
    PRACTITIONER_VIEW,
    TREATMENT_OPTIONS_UNDER_REVIEW,
    distinct_sources,
    format_quantity,
    medication_status,
)
from .figures import agp_profile_figure, glucose_trace_figure
from .icons import render_icon

FULL_WIDTH = widgets.Layout(width="100%")
_DIVIDER = "1px solid #66717e"

_PLOTLY_RESIZE_SCRIPT = r"""
(function () {
  if (window.__jhPlotlyResizeInstalled) return;
  window.__jhPlotlyResizeInstalled = true;

  function plotDiv(widget) {
    if (!widget) return null;
    return widget.matches(".js-plotly-plot")
      ? widget
      : widget.querySelector(".js-plotly-plot");
  }

  function resizeWidget(widget) {
    var gd = plotDiv(widget);
    if (!gd || !window.Plotly) return;
    if (window.Plotly.Plots && typeof window.Plotly.Plots.resize === "function") {
      window.Plotly.Plots.resize(gd);
    } else {
      gd.dispatchEvent(new Event("plotly_resize"));
    }
  }

  var pending = false;
  function resizeAll() {
    if (pending) return;
    pending = true;
    window.requestAnimationFrame(function () {
      pending = false;
      document.querySelectorAll(".jh-plotly-widget").forEach(resizeWidget);
    });
  }

  function observe(widget) {
    if (widget.__jhPlotlyResizeObserved) return;
    widget.__jhPlotlyResizeObserved = true;
    if (typeof ResizeObserver !== "undefined") {
      new ResizeObserver(resizeAll).observe(widget);
    }
  }

  function scan() {
    document.querySelectorAll(".jh-plotly-widget").forEach(observe);
    resizeAll();
  }

  if (typeof MutationObserver !== "undefined") {
    new MutationObserver(scan).observe(document.documentElement, {
      childList: true,
      subtree: true
    });
  }
  window.addEventListener("resize", resizeAll);
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", resizeAll);
  }
  window.setTimeout(scan, 0);
})();
"""

_ROLE_BADGE = {
    PRACTITIONER_VIEW: ("Clinician view", "notes"),
    PATIENT_VIEW: ("Patient view", "bmi"),
}

# Conventional five-range order, clinical bound, and label copy.
BAND_ROWS = (
    ("very_high", "Very High", ">250 mg/dL"),
    ("high", "High", "181–250 mg/dL"),
    ("target", "Target", "70–180 mg/dL"),
    ("low", "Low", "54–69 mg/dL"),
    ("very_low", "Very Low", "<54 mg/dL"),
)

_STATUS_LABELS = {
    "in_range": "In range",
    "high": "Elevated",
    "low": "Below range",
    "na": "Informational",
}
_STATUS_ICON_KEYS = {
    "in_range": "status_in_range",
    "high": "status_high",
    "low": "status_low",
}


def load_theme() -> widgets.HTML:
    """Embed the packaged stylesheet as notebook output without remote assets."""
    css = resources.files("jupyterhealth_dashboard").joinpath("theme.css").read_text()
    return widgets.HTML(value=f"<style>{css}</style>")


def _html(markup: str) -> widgets.HTML:
    return widgets.HTML(value=markup, layout=FULL_WIDTH)


def _source_badges_html(source) -> str:
    """Return compact, escaped source-name badges for one display record.

    ``source`` may be a single string, a list of names, or ``None``. Names are
    trimmed, de-duplicated, and blanks dropped through :func:`distinct_sources`,
    so the UI never invents an ingestion provenance or a device brand.
    """
    if source is None:
        values = []
    elif isinstance(source, str):
        values = [source]
    else:
        values = list(source)
    names = distinct_sources(values)
    if not names:
        return ""
    badges = "".join(
        f'<span class="jh-source-badge">{escape(name)}</span>' for name in names
    )
    return f'<div class="jh-source-badges">{badges}</div>'


def _source_badges_widget(source) -> widgets.HTML | None:
    markup = _source_badges_html(source)
    if not markup:
        return None
    return widgets.HTML(
        value=markup,
        layout=widgets.Layout(
            width="auto",
            flex="0 1 auto",
            min_width="0",
            max_width="100%",
        ),
    )


def _trace_sources_html(explorer: dict) -> str:
    """Return one source badge group per available glucose-trace layer.

    Each layer carries its own modality name and its own distinct source names.
    Optional layers with no usable source are omitted; the CGM layer appears
    whenever the selected recording has a usable source.
    """
    sources = explorer.get("sources", {})
    groups = []
    for key, modality in (
        ("glucose", "Glucose"),
        ("activity", "Activity"),
        ("sleep", "Sleep stages"),
        ("meals", "Meals"),
    ):
        names = distinct_sources(sources.get(key, []))
        if not names:
            continue
        joined = ", ".join(escape(name) for name in names)
        groups.append(
            '<span class="jh-trace-source">'
            f'<span class="jh-trace-source-modality">{escape(modality)}</span>'
            f'<span class="jh-trace-source-names">{joined}</span>'
            "</span>"
        )
    if not groups:
        return ""
    return f'<div class="jh-trace-sources">{"".join(groups)}</div>'


def _trace_sources_widget(explorer: dict) -> widgets.HTML | None:
    markup = _trace_sources_html(explorer)
    if not markup:
        return None
    return widgets.HTML(
        value=markup,
        layout=widgets.Layout(
            width="auto",
            flex="0 1 auto",
            min_width="0",
            max_width="100%",
        ),
    )


def _figure(figure: go.Figure) -> go.FigureWidget:
    widget = go.FigureWidget(figure)
    widget._config = {"displayModeBar": False, "responsive": True}
    widget.add_class("jh-plotly-widget")
    return widget


def _plotly_resize_control() -> widgets.Output:
    """Return a hidden output that keeps Plotly SVGs sized to their visible widget.

    ``responsive: True`` alone tracks window resizes, not layout changes in a
    Jupyter/Voilà output area. This tiny script attaches a ``ResizeObserver`` to
    every ``.jh-plotly-widget`` and calls ``Plotly.Plots.resize`` when the widget's
    rendered width changes, so the inner SVG cannot stay at Plotly's first-paint
    width after the notebook host has finished laying out its output area.
    """
    control = widgets.Output(
        layout=widgets.Layout(width="0px", height="0px", overflow="visible")
    )
    control.add_class("jh-plotly-resize")
    control.outputs = (
        {
            "output_type": "display_data",
            "data": {"application/javascript": _PLOTLY_RESIZE_SCRIPT},
            "metadata": {},
        },
    )
    return control


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
    present = [control for control in controls if control is not None]
    title_widget = widgets.HTML(
        value=f'<h2 class="jh-h2">{escape(title)}</h2>',
        layout=widgets.Layout(flex="1 1 auto", min_width="0"),
    )
    return widgets.HBox(
        [title_widget, *present],
        layout=widgets.Layout(
            width="100%",
            display="flex",
            flex_flow="row wrap",
            align_items="flex-end",
            justify_content="space-between",
            margin="0 0 13px 0",
        ),
    )


# --------------------------------------------------------------------------------------
# role header and patient context


def _role_header(view: dict) -> widgets.HTML:
    role = view.get("role") or PRACTITIONER_VIEW
    label, icon_key = _ROLE_BADGE.get(role, _ROLE_BADGE[PRACTITIONER_VIEW])
    icon = render_icon(icon_key, label=label)
    return _html(
        '<header class="jh-role">'
        '<div class="jh-role-line">'
        f'<h1 class="jh-greeting">{escape(view.get("heading", ""))}</h1>'
        f'<span class="jh-role-badge jh-role-badge-{escape(role)}">{icon}'
        f'<span class="jh-role-badge-label">{escape(label)}</span>'
        "</span>"
        "</div>"
        + "</header>"
    )


def _patient_header(view: dict) -> widgets.HTML:
    patient = view.get("patient", {})
    facts = "".join(
        f'<span class="jh-fact">{escape(fact)}</span>'
        for fact in patient.get("facts", [])
        if fact
    )
    initials = patient.get("initials", "")
    name = patient.get("name", "")
    return _html(
        '<div class="jh-patient-meta" aria-label="Patient context">'
        f'<div class="jh-avatar" role="img" aria-label="{escape(initials)}">'
        f"{escape(initials)}</div>"
        '<div class="jh-patient-meta-body">'
        f'<div class="jh-patient-name">{escape(name)}</div>'
        f'<div class="jh-facts">{facts}</div>'
        "</div></div>"
    )


# --------------------------------------------------------------------------------------
# latest-value clinical cards


def _status_icon(status: str) -> str:
    key = _STATUS_ICON_KEYS.get(status)
    if not key:
        return ""
    return render_icon(key, label=_STATUS_LABELS.get(status, ""))


def _context_card(card: dict) -> str:
    status = card.get("status") or "na"
    status_label = card.get("status_label") or _STATUS_LABELS.get(status, "—")
    reference = card.get("reference") or ""
    date = card.get("date") or ""
    icon = render_icon(card.get("icon", ""), label=card.get("label", ""))
    reference_html = (
        f'<span class="jh-card-reference">{escape(reference)}</span>' if reference else ""
    )
    date_html = f'<span class="jh-card-date">{escape(date)}</span>' if date else ""
    source_html = _source_badges_html(card.get("source"))
    return (
        '<article class="jh-lab-card jh-status-' + escape(str(status)) + '">'
        '<div class="jh-card-head">'
        f'<div class="jh-card-title">{icon}<h3>{escape(card.get("label", ""))}</h3></div>'
        f"{source_html}"
        "</div>"
        '<div class="jh-card-reading">'
        f'<span class="jh-card-value">{escape(str(card.get("value", "n/a")))}</span>'
        f"{reference_html}"
        "</div>"
        '<div class="jh-card-meta">'
        f'<span class="jh-card-status">{_status_icon(status)} {escape(status_label)}</span>'
        f"{date_html}"
        "</div></article>"
    )


def _context_section(view: dict) -> widgets.HTML:
    cards = "".join(_context_card(card) for card in view.get("context_cards", []))
    return _html(
        '<section class="jh-section">'
        '<div class="jh-section-head"><h2 class="jh-h2">Labs and vitals</h2></div>'
        f'<div class="jh-lab-grid">{cards}</div>'
        + "</section>"
    )


# --------------------------------------------------------------------------------------
# medication panel


def _medication_card(icon_key: str, title: str, value: str, status: str, status_label: str) -> str:
    return _context_card(
        {
            "label": title,
            "value": value,
            "status": status,
            "status_label": status_label,
            "icon": icon_key,
        }
    )


def _medication_section(view: dict) -> widgets.VBox:
    entries = view.get("medications", [])
    cards = []
    if entries:
        for entry in entries:
            cards.append(
                _medication_card(
                    entry.get("icon", "medication"),
                    entry.get("name", "Medication"),
                    entry.get("detail", ""),
                    entry.get("status", "na"),
                    entry.get("status_label", ""),
                )
            )
    else:
        cards.append(
            _medication_card(
                "medication",
                "Active medications",
                medication_status(entries),
                "na",
                "None active",
            )
        )
    if view.get("treatment_options_under_review", True):
        cards.append(
            _medication_card(
                "notes",
                "Treatment plan",
                TREATMENT_OPTIONS_UNDER_REVIEW,
                "na",
                "Review",
            )
        )
    return _section(
        _section_head("Medications"),
        _html('<div class="jh-lab-grid jh-med-grid">' + "".join(cards) + "</div>"),
    )


# --------------------------------------------------------------------------------------
# glucose summary and full-period trace


def _band_strip_html(glucose: dict) -> str:
    by_key = {band["key"]: band for band in glucose["bands"]}
    segments = []
    rows = []
    aria_parts = []
    for key, label, bounds in BAND_ROWS:
        band = by_key.get(key, {"percent": 0.0})
        percent = float(band["percent"])
        aria_parts.append(f"{label} {percent:.1f}%")
        segments.append(
            f'<div class="jh-agp-seg jh-band-{key}" style="flex-grow:{percent:.3f}" '
            f'title="{escape(label)} {percent:.1f}%" aria-hidden="true"></div>'
        )
        rows.append(
            '<div class="jh-agp-range-row">'
            f'<i class="jh-band-{key}" aria-hidden="true"></i>'
            f'<b>{escape(label)}</b>'
            f'<span class="jh-bounds">{escape(bounds)}</span>'
            f'<span class="jh-pct">{percent:.1f}%</span>'
            "</div>"
        )
    return (
        '<div class="jh-agp-block jh-agp-ranges">'
        '<div class="jh-agp-head">Time in ranges</div>'
        '<div class="jh-agp-range-body">'
        f'<div class="jh-agp-strip" role="img" aria-label="Time in ranges: '
        f'{escape("; ".join(aria_parts))}">{"".join(segments)}</div>'
        f'<div class="jh-agp-range-rows">{"".join(rows)}</div>'
        "</div>"
        "</div>"
    )


def _metric_row(label: str, value: str, target: str = "") -> str:
    target_html = (
        f'<span class="jh-metric-target">{escape(target)}</span>' if target else ""
    )
    return (
        '<div class="jh-metric-row">'
        f'<span class="jh-metric-label">{escape(label)}</span>'
        f'<span class="jh-metric-value">{escape(value)}</span>'
        f"{target_html}"
        "</div>"
    )


def _fmt(value: float | None, unit: str, decimals: int) -> str:
    return format_quantity(value, unit, decimals)


def _metrics_html(glucose: dict) -> str:
    metrics = glucose["metrics"]
    rows = "".join(
        [
            _metric_row("Period", glucose["period"]),
            _metric_row(
                "Time CGM active",
                _fmt(glucose["time_active_percent"], "%", 1),
            ),
            _metric_row(
                "Average glucose",
                _fmt(metrics["mean_mg_dl"], "mg/dL", 0),
                "Target <154 mg/dL",
            ),
            _metric_row("GMI", _fmt(metrics["gmi_percent"], "%", 1), "Target <7%"),
            _metric_row(
                "Glucose variability",
                _fmt(metrics["cv_percent"], "%", 1),
                "Target ≤36% (CV)",
            ),
        ]
    )
    return (
        '<div class="jh-agp-block jh-agp-metrics">'
        '<div class="jh-agp-head">Glucose metrics</div>'
        f'<div class="jh-metric-rows">{rows}</div>'
        "</div>"
    )


def _glucose_summary_html(glucose: dict) -> str:
    return (
        '<div class="jh-agp-report">'
        f"{_band_strip_html(glucose)}"
        f"{_metrics_html(glucose)}"
        "</div>"
    )


def _glucose_section(view: dict) -> widgets.VBox:
    glucose = view["glucose"]
    return _section(
        _section_head(
            "Glucose summary",
            _source_badges_widget(glucose.get("sources", [])),
        ),
        _html(_glucose_summary_html(view["glucose"])),
    )


def _glucose_profile_section(view: dict) -> widgets.VBox:
    glucose = view["glucose"]
    return _section(
        _section_head(
            "Glucose profile",
            _source_badges_widget(glucose.get("sources", [])),
        ),
        _html(
            '<p class="jh-note">24-hour 5th–95th percentile profile from the latest '
            "CGM period. Target 70–180 mg/dL.</p>"
        ),
        _figure(agp_profile_figure(view["glucose"])),
    )


def _trace_section(view: dict) -> widgets.VBox:
    explorer = view.get("explorer", {})
    overlay_names = []
    if len(explorer.get("meals", [])) > 0:
        overlay_names.append("meals")
    if len(explorer.get("activity", [])) > 0:
        overlay_names.append("activity")
    if len(explorer.get("sleep", [])) > 0:
        overlay_names.append("sleep")
    if overlay_names:
        if len(overlay_names) == 1:
            shared = overlay_names[0]
        elif len(overlay_names) == 2:
            shared = " and ".join(overlay_names)
        else:
            shared = ", ".join(overlay_names[:-1]) + " and " + overlay_names[-1]
        note = f"{shared} share one time axis. Target 70–180 mg/dL."
    else:
        note = "Target 70–180 mg/dL."
    return _section(
        _section_head("Glucose trace", _trace_sources_widget(explorer)),
        _html(f'<p class="jh-note">{escape(note)}</p>'),
        _figure(glucose_trace_figure(view["explorer"])),
    )


def build_dashboard(view: dict) -> widgets.VBox:
    """Compose the role-aware dashboard widget tree for Voilà or notebook output."""
    sections = [
        load_theme(),
        _plotly_resize_control(),
        _role_header(view),
        _patient_header(view),
        _medication_section(view),
        _glucose_section(view),
        _glucose_profile_section(view),
        _trace_section(view),
    ]
    if view.get("context_cards"):
        sections.insert(4, _context_section(view))

    chat = scripted_chat_widget(view)
    if chat is not None:
        sections.append(chat)

    return widgets.VBox(
        sections,
        layout=widgets.Layout(
            width="100%",
            max_width="100%",
            margin="0 auto",
            padding="0 28px 120px",
        ),
    )
