"""Visualization and layout components for the Voilà-served Laude dashboard.

``notebooks/laude_dashboard.ipynb`` is the whole application. It reads the hosted Exchange records
itself with the official ``jupyterhealth-client``, decodes and normalizes them in ordinary pandas
cells, computes the AGP metrics and the clinical-context comparisons, and finally hands a plain
view dict to :func:`build_dashboard`.

This package only draws: :mod:`jupyterhealth_dashboard.figures`,
:mod:`jupyterhealth_dashboard.ui`, and the packaged ``theme.css``. It contains no Exchange access,
retrieval, decoding, normalization, or check.
"""

from .ui import build_dashboard

__all__ = ["build_dashboard"]
