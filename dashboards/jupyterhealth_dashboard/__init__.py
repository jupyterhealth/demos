"""Visualization and layout components for the Voilà-served CGM demo.

``dashboards/cgm-demo.ipynb`` is the application. It reads the hosted Exchange
records itself with the official ``jupyterhealth-client``, decodes and
normalizes them in ordinary pandas cells, computes the glucose metrics and
latest clinical values, and finally hands a plain view dict to
:func:`build_dashboard`.

The package only draws: :mod:`jupyterhealth_dashboard.figures`,
:mod:`jupyterhealth_dashboard.ui`, :mod:`jupyterhealth_dashboard.chat`, and the
packaged ``theme.css``. It contains no Exchange access, retrieval, decoding,
normalization, or check.

The practitioner report-delivery feed opens the supplied UC HTN Way 3.0 Box
shared link in a new tab beside a selected Randomize control. The iCKM Advisor
header keeps a hidden, keyboard-focusable double-click gesture; a successful
double-click appends the scripted randomized-arm outcome once as a separate
assistant message. The older locally vendored algorithm image remains packaged
but is not used as the report destination.

The ``build_dashboard`` export is lazy so tests and the notebook can import the
dependency-free :mod:`jupyterhealth_dashboard.core` module without importing
pandas, plotly, or ipywidgets.
"""

__all__ = ["build_dashboard"]


def __getattr__(name: str):
    if name == "build_dashboard":
        from .ui import build_dashboard

        return build_dashboard
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
