"""Local icon registry for the dashboard.

The dashboard never loads icons from a CDN and never uses emoji. Each semantic
key maps to a vendored Tabler SVG file under ``icons/``. If a file has not been
vendored yet, :func:`render_icon` returns an empty, text-safe span so the
adjacent visible label still carries the meaning.
"""

from __future__ import annotations

from html import escape
from importlib import resources
from urllib.parse import quote

# Semantic key -> expected vendored filename. See ``icons/README.md`` for the
# exact Tabler asset names and license note. Keep this list in sync with that
# file when assets are added.
ICON_FILES = {
    "activity": "tabler-walk.svg",
    "assistant": "tabler-sparkles.svg",
    "bmi": "tabler-body-scan.svg",
    "bp": "tabler-heart-rate-monitor.svg",
    "chat": "tabler-messages.svg",
    "close": "tabler-x.svg",
    "glucose": "tabler-droplet.svg",
    "hba1c": "tabler-test-pipe.svg",
    "heart": "tabler-heartbeat.svg",
    "height": "tabler-ruler.svg",
    "hrv": "tabler-wave-sine.svg",
    "meal": "tabler-tools-kitchen-2.svg",
    "medication": "tabler-pill.svg",
    "minimize": "tabler-chevron-down.svg",
    "notes": "tabler-notes.svg",
    "send": "tabler-send.svg",
    "status_high": "tabler-alert-triangle.svg",
    "status_in_range": "tabler-circle-check.svg",
    "status_low": "tabler-arrow-down-circle.svg",
    "weight": "tabler-weight.svg",
}


def _read_icon(filename: str) -> str:
    path = resources.files("jupyterhealth_dashboard").joinpath("icons", filename)
    try:
        return path.read_text().strip()
    except (FileNotFoundError, OSError):
        return ""


def render_icon_svg(svg: str, *, label: str = "") -> str:
    """Render already-read inline SVG without adding any remote reference."""
    if not svg.strip():
        return ""
    return (
        '<span class="jh-icon" aria-hidden="true" '
        f'title="{escape(label)}">{svg.strip()}</span>'
    )


def render_icon(key: str, *, label: str = "") -> str:
    """Return safe inline SVG markup for ``key`` or an empty fallback.

    The fallback is deliberately empty rather than an emoji or a remote asset:
    callers always render a text label next to the icon slot.
    """
    filename = ICON_FILES.get(key)
    if not filename:
        return ""
    svg = _read_icon(filename)
    return render_icon_svg(svg, label=label)


def icon_background(key: str, *, color: str = "#ffffff") -> str:
    """Return a CSS ``url(data:image/svg+xml,...)`` for painting ``key`` on a button.

    Native ipywidgets buttons can only carry plain text, so icon-only controls use
    the same vendored SVG as a ``background-image``. The local registry remains the
    single source for the artwork, and no CDN, emoji, or remote asset is involved.
    """
    filename = ICON_FILES.get(key)
    if not filename:
        return ""
    svg = _read_icon(filename)
    if not svg.strip():
        return ""
    svg = svg.replace('stroke="currentColor"', f'stroke="{color}"')
    encoded = quote(svg, safe="")
    return f'url("data:image/svg+xml,{encoded}")'
