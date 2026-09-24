from .loader import load_sleep_data
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import pandas as pd
import numpy as np
from typing import Literal, Optional

class HypnogramExtension:
    """
    Draw a hypnogram with stage bands and per-episode lines for sleep stages.

    Parameters
    ----------
    source : {'file', 'client'}
        Source of sleep data (on-disk file or in-memory dataframe).
    base_path : str or None, default None
        Base directory for file-based loading (if `source='file'`).
    subject_id : int or None, default None
        Optional subject identifier (for file-based loaders).
    filename : str or None, default None
        File name for file-based loaders.
    client_df : pandas.DataFrame or None, default None
        Preloaded sleep dataframe for `source='client'`.
    gap_threshold : int, default 30
        Maximum allowed gap (minutes) between consecutive episodes to draw
        a vertical connector (i.e., visually “stitch” transitions).

    Notes
    -----
    Expected columns in the sleep dataframe:
    - ``start`` : episode start (datetime)
    - ``end``   : episode end (datetime)
    - ``stage`` : one of {'Awake', 'REM_sleep', 'Light_sleep', 'Deep_sleep'}

    Expects the environment to provide:
    - ``load_sleep_data(...)`` function
    - a viewer with ``viewer.view_start``, ``viewer.view_end``
    - Matplotlib axis at ``self.ax``
    - ``mdates`` imported for tick formatting
    """
    def __init__(self,
                 source: Literal["file", "client"],
                 base_path: str | None = None,
                 subject_id: int | None = None,
                 filename: str | None = None,
                 client_df: Optional[pd.DataFrame] = None,
                 gap_threshold: int = 30,
                ):
        self.source = source
        self.base_path = base_path
        self.filename = filename
        self.client_df = client_df
        self.gap_threshold = pd.Timedelta(minutes=gap_threshold)

    def draw(self):
        viewer = self.viewer
        ax = self.ax
        start, end = viewer.view_start, viewer.view_end

        # Load sleep data for this subject and restrict to current day
        sleep_df = load_sleep_data(source=self.source,
                                   base_path=self.base_path,
                                   filename=self.filename,
                                   client_df=self.client_df
                                  )
        day_sleep = sleep_df[(sleep_df["start"] < end) & (sleep_df["end"] > start)]

        # Stage mapping and background shading
        stage_map = {"Awake": 4, "REM_sleep": 3, "Light_sleep": 2, "Deep_sleep": 1}
        base_color = "#1f77b4"
        alphas = {4: 0.1, 3: 0.25, 2: 0.45, 1: 0.7}

        for val in [1, 2, 3, 4]:
            ax.axhspan(val - 0.5, val + 0.5, color=base_color, alpha=alphas[val])

        if not day_sleep.empty:
            prev_end = None
            prev_stage = None

            for _, row in day_sleep.iterrows():
                y_val = stage_map.get(row["stage"], None)
                if y_val is None:
                    continue

                seg_start = max(row["start"], start)
                seg_end = min(row["end"], end)

                ax.hlines(y_val, seg_start, seg_end, color="navy", linewidth=2)

                if prev_end is not None and (row["start"] - prev_end) <= self.gap_threshold:
                    ax.vlines(row["start"], prev_stage, y_val, color="navy", linewidth=2)

                prev_end = row["end"]
                prev_stage = y_val

        # Axis formatting
        ax.set_xlim(start, end)
        ax.set_ylim(0.5, 4.5)
        ax.set_yticks([1, 2, 3, 4])
        ax.set_yticklabels(["Deep", "Light", "REM", "Awake"])
        ax.set_ylabel(
            "Sleep Stage",
            color="0.2",
            fontsize=10
        )

        ax.xaxis.set_major_locator(mdates.HourLocator(interval=viewer.scale(2, 6), tz=start.tzinfo))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%-I %p", tz=start.tzinfo))
        ax.tick_params(labelsize=viewer.scale(10, 7))


# Stage order and colours for SleepCompositionExtension; stacked bottom-up.
SLEEP_STAGE_COLORS = {
    "deep_h": ("#1b3a5c", "Deep"),
    "light_h": ("#4a7fb5", "Light"),
    "rem_h": ("#8fc0e8", "REM"),
    "awake_h": ("#d9d9d9", "Awake"),
}


class SleepCompositionExtension:
    """Per-night stacked stage composition, as a second subplot row.

    This is deliberately NOT a hypnogram. Stage *timing within* the night is not
    recorded in an aggregate sleep-stage-summary record, so it cannot be
    reconstructed. Each night renders as one stacked bar positioned at its sleep
    window: height carries the stage quantities, x-position carries the window.

    For a true hypnogram use :class:`HypnogramExtension`, which needs
    ``sleep_stage_episodes_*`` -- present in the Open mHealth sample data, absent
    from JHE study 30006.

    Parameters
    ----------
    nights : pandas.DataFrame
        Output of :func:`~cgmsandbox.loader.load_sleep_nights`.
    bar_width_h : float
        Bar width in hours.
    y_max : float or None
        Y-axis ceiling. Defaults to one hour above the longest night in bed.
    show_efficiency : bool
        Annotate each bar with the night's sleep efficiency.
    """

    def __init__(self, nights: pd.DataFrame, bar_width_h: float = 6.0,
                 y_max: float | None = None, show_efficiency: bool = True):
        self.nights = nights
        self.bar_width = pd.Timedelta(hours=bar_width_h)
        self.y_max = y_max if y_max is not None else float(
            np.ceil(nights["in_bed_h"].max()) + 1.0)
        self.show_efficiency = show_efficiency

    def draw(self):
        viewer, ax = self.viewer, self.ax
        start, end = viewer.view_start, viewer.view_end
        vis = self.nights[(self.nights.sleep_end > start) & (self.nights.sleep_start < end)]

        seen: set[str] = set()
        for _, r in vis.iterrows():
            center = r.sleep_start + (r.sleep_end - r.sleep_start) / 2
            bottom = 0.0
            for col, (color, label) in SLEEP_STAGE_COLORS.items():
                h = float(r.get(col) or 0.0)
                if h <= 0:
                    continue
                ax.bar(center, h, bottom=bottom, width=self.bar_width,
                       color=color, edgecolor="white", linewidth=0.7,
                       label=label if label not in seen else None, zorder=3)
                seen.add(label)
                bottom += h

            if self.show_efficiency and pd.notna(r.efficiency_pct):
                ax.text(center, bottom + 0.12, f"{r.efficiency_pct:.0f}% eff.",
                        ha="center", va="bottom", fontsize=8, color="0.35")

        ax.set_ylim(0, self.y_max)
        ax.set_ylabel("Sleep (h)", color="0.2", fontsize=10)
        if seen:
            ax.legend(ncol=4, fontsize=9, frameon=False, loc="upper right")
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(length=0)
        step = viewer.scale(2, 6)
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=step, tz=start.tzinfo))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%-I %p", tz=start.tzinfo))
        ax.tick_params(labelsize=viewer.scale(10, 7))


# Matches the clinician dashboard's "Daily step count" bars.
STEP_BAR_COLOR = "#2878B5"


class StepCountExtension:
    """Per-day step totals as a bar chart, in a second subplot row.

    Mirrors the clinician dashboard's "Daily step count" panel. Each bar is
    positioned at its day's interval and carries that day's total; because the
    record is a daily sum, the bars cannot be subdivided into intraday activity.

    Parameters
    ----------
    steps : pandas.DataFrame
        Output of :func:`~cgmsandbox.loader.load_step_count`.
    bar_width_h : float
        Bar width in hours. Below 24 so consecutive days read as separate bars.
    y_max : float or None
        Y-axis ceiling. Defaults to ~15% headroom above the tallest day.
    show_values : bool
        Annotate each bar with its step total.
    """

    def __init__(self, steps: pd.DataFrame, bar_width_h: float = 18.0,
                 y_max: float | None = None, show_values: bool = True):
        self.steps = steps
        self.bar_width = pd.Timedelta(hours=bar_width_h)
        self.y_max = y_max if y_max is not None else float(steps["steps"].max()) * 1.15
        self.show_values = show_values

    def draw(self):
        viewer, ax = self.viewer, self.ax
        start, end = viewer.view_start, viewer.view_end
        vis = self.steps[(self.steps["end"] > start) & (self.steps["start"] < end)]
        if vis.empty:
            vis = self.steps

        for _, r in vis.iterrows():
            r_start, r_end, n = r["start"], r["end"], float(r["steps"])
            center = r_start + (r_end - r_start) / 2
            ax.bar(center, n, width=self.bar_width,
                   color=STEP_BAR_COLOR, edgecolor="white", linewidth=0.7, zorder=3)
            if self.show_values:
                ax.text(center, n + self.y_max * 0.02, f"{int(n):,}",
                        ha="center", va="bottom", fontsize=8, color="0.35")

        ax.set_ylim(0, self.y_max)
        ax.set_ylabel("Steps", color="0.2", fontsize=10)
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        ax.tick_params(length=0)
        step = viewer.scale(2, 6)
        ax.xaxis.set_major_locator(mdates.HourLocator(interval=step, tz=start.tzinfo))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%-I %p", tz=start.tzinfo))
        ax.tick_params(labelsize=viewer.scale(10, 7))
