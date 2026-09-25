from .loader import load_sleep_data, load_food_entry_data
from pandas import Timedelta
import pandas as pd
import numpy as np
import mplcursors
from typing import Literal, Optional

from .cgm_methods import extract_wakeup_glucose
from .cgmquantify import summarize_measures, cv, mage_ma_segments

from typing import Literal



# --------------------------------
# Make your own Overlay!
# --------------------------------
class MeanGlucoseOverlay:
    """
    Overlay that draws a horizontal mean glucose line for each visible panel
    or across the full CGM tracing, with optional interactive hover tooltips
    showing the mean glucose value.

    Parameters
    ----------
    source : {'file', 'client'}
        Source of CGM data (either loaded from file or provided as an in-memory dataframe).
    base_path : str or None, optional
        Base directory path for file-based loading (used when ``source='file'``).
    subject_id : int or None, optional
        Subject identifier, required when loading from file-based datasets.
    filename : str or None, optional
        Specific filename for file-based data loading.
    client_df : pandas.DataFrame or None, optional
        In-memory dataframe containing CGM data when ``source='client'`` is used.
    scope : {'daily', 'full'}, default 'daily'
        Defines the time window over which the mean glucose is calculated.
        - ``'daily'``: compute mean glucose within each visible axis window.
        - ``'full'``: compute a single mean glucose value across the entire dataset.

    Notes
    -----
    This overlay:
        - Plots a horizontal line at the mean glucose level for each axis panel.
        - Uses a semi-transparent dark blue-gray line for clarity and simplicity.
        - Optionally attaches interactive hover tooltips (if `mplcursors` is installed)
          that display the mean glucose value in mg/dL.

    Requirements
    ------------
    The parent viewer must provide:
        - ``viewer.df`` with columns ``["time", "gl"]`` representing glucose readings.
        - ``viewer.iter_axes_by_time()`` yielding ``(ax, start, end)`` for each visible subplot.
        - ``viewer.scale(hi, lo)`` for DPI-aware linewidth scaling.
        - ``viewer.view_start`` and ``viewer.view_end`` indicating the current time bounds.

    See Also
    --------
    mplcursors : Library used to attach interactive hover tooltips to matplotlib artists.
    """
    def __init__(self,
                 source: Literal["file", "client"],
                 base_path: str | None = None,
                 subject_id: int | None = None,
                 filename: str | None = None,
                 client_df: Optional[pd.DataFrame] = None,
                 scope: Literal["daily", "full"] = "daily",
                ):
        self.scope = scope
        self.source = source
        self.base_path = base_path
        self.subject_id = subject_id
        self.filename = filename
        self.client_df = client_df
        self._cursor = None

    def draw(self):
        viewer = self.viewer

        # Variables required for the cursor
        lines = []
        hover_info = {}

        # Iterate through main viewer axis and plot the mean glucose line
        for ax, start, end in viewer.iter_axes_by_time():
            # Compute mean based on the scope indicated
            if self.scope == "daily":
                # Only select the CGM data for a given start to end date provided by the viewer
                sub = viewer.df[(viewer.df["time"] >= start) & (viewer.df["time"] < end)]
                g = pd.to_numeric(sub["gl"], errors="coerce").dropna()
                mean_val = float(np.round(np.nanmean(g), 2))
            # Compute mean for the full (~10 days) CGM tracing
            elif self.scope == "full":
                g = pd.to_numeric(viewer.df["gl"], errors="coerce")
                # Compute mean and round to 2 decimal places
                mean_val = float(np.round(np.nanmean(g), 2))
            else:
                raise ValueError(f"scope must be 'daily' or 'full', got {self.scope!r}")

            # Draw mean line
            ln = ax.axhline(mean_val,
                            color="#2c3e50",
                            alpha=0.7,
                            lw=viewer.scale(2.2, 1.6),
                            zorder=4)
            lines.append(ln)
            hover_info[ln] = {"mean": mean_val}

        # Optional hover tooltips using mplcursors
        try:
            # For more details, see mplcursors documentation: https://mplcursors.readthedocs.io/en/stable/
            import mplcursors
            self._cursor = mplcursors.cursor(lines, hover=True)

            @self._cursor.connect("add")
            def _on_hover(sel):
                data = hover_info.get(sel.artist, {})
                text = (f"$\\bf{{Mean}}$: {data.get('mean', np.nan):.0f} mg/dL")
                sel.annotation.set_text(text)
                patch = sel.annotation.get_bbox_patch()
                patch.set(fc="#f5f5f5", ec="#cfcfcf", lw=0.8, alpha=0.95)
        except Exception:
            self._cursor = None


# --------------------------------
# Basic Overlays
# --------------------------------
class TimeInRangeOverlay:
    """
    Overlay that color-codes CGM traces by time-in-range (TIR) categories.

    The signal is segmented into continuous runs, breaking at state transitions
    (below/in/above range) or large time gaps. Each segment is drawn with a
    distinct color.

    Parameters
    ----------
    low : float, default 70
        Lower glucose threshold (mg/dL).
    high : float, default 180
        Upper glucose threshold (mg/dL).
    colors : dict or None, default None
        Mapping of state keys to colors. Expected keys are
        ``{"in", "low", "high", "line"}``. If ``None``, sensible defaults are used.
    show_lines : bool, default True
        If True, draw horizontal threshold guide lines at `low` and `high`.
    gap_minutes : int, default 10
        Maximum allowed time gap between consecutive points in a segment. Larger
        gaps start a new segment.

    Notes
    -----
    Requires the viewer to expose:
    - ``viewer.df`` with columns ``["time", "gl"]``
    - ``viewer.iter_axes_by_time()`` yielding ``(ax, start, end)``
    - ``viewer.scale(hi, lo)`` for DPI-aware linewidth scaling.
    """
    def __init__(self, low=70, high=180,
                 colors=None, show_lines=True, gap_minutes=10):
        self.low = low
        self.high = high
        self.show_lines = show_lines
        self.gap = Timedelta(minutes=gap_minutes)
        self.colors = colors or {
            "in":   "#22a559",
            "low":  "#d9534f",
            "high": "#f39c12",
            "line": "#e0e0e0"
        }

    def draw(self):
        v = self.viewer
        for ax, start, end in v.iter_axes_by_time():
            # Threshold lines
            if self.show_lines:
                ax.axhline(self.low,  color=self.colors["line"], linewidth=1.0, zorder=1)
                ax.axhline(self.high, color=self.colors["line"], linewidth=1.0, zorder=1)

            # Data in this axis window
            sub = v.df[(v.df["time"] >= start) & (v.df["time"] <= end)][["time", "gl"]].dropna()
            sub = sub.sort_values("time").reset_index(drop=True)

            # Classify each point: -1 (below), 0 (in), +1 (above)
            state = np.where(sub["gl"] < self.low, -1,
                             np.where(sub["gl"] > self.high, 1, 0))
            sub["_state"] = state

            # Break segments at state changes or big time gaps
            breaks = (sub["time"].diff() > self.gap) | (sub["_state"].diff().fillna(0) != 0)
            seg_id = breaks.cumsum()

            lw = v.scale(2.5, 1.2)
            for _, seg in sub.groupby(seg_id):
                s = int(seg["_state"].iloc[0])
                color = self.colors["in"] if s == 0 else (self.colors["high"] if s > 0 else self.colors["low"])
                i0 = int(seg.index.min())
                if i0 > 0:
                    seg = pd.concat([sub.loc[[i0-1]], seg], axis=0)
                ax.plot(seg["time"], seg["gl"],
                        color=color, linewidth=lw,
                        solid_capstyle="round", zorder=4, clip_on=True)


class FoodEntryOverlay:
    """
    Overlay a marker that annotates CGM with food log entries, scaling marker size by
    carbohydrate amount and showing hover tooltips.

    Parameters
    ----------
    source : {'file', 'client'}
        Source of the food entries (on-disk file vs. JHE client dataframe).
    base_path : str or None, default None
        Base directory for file-based loading (if `source='file'`).
    subject_id : int or None, default None
        Optional subject identifier for file-based loaders.
    filename : str or None, default None
        File name for file-based loaders.
    client_df : pandas.DataFrame or None, default None
        Preloaded food dataframe for `source='client'`.

    Notes
    -----
    Expected columns in the loaded food dataframe include at least:
    ``["time", "food_name", "carbohydrate"]``.
    """
    def __init__(self,
                 source: Literal["file", "client"],
                 base_path: str | None = None,
                 subject_id: int | None = None,
                 filename: str | None = None,
                 client_df: Optional[pd.DataFrame] = None
                ):
        self.source = source
        self.base_path = base_path
        self.filename = filename
        self.client_df = client_df
        self._cursor = None

    def _size_from_carbs(self, carbs: float, viewer) -> float:
        carbs = float(np.clip(carbs, 0.0, 100.0))
        s_min = viewer.scale(40, 15)
        s_max = viewer.scale(280, 80)
        return np.interp(carbs, [0.0, 100.0], [s_min, s_max])

    def draw(self):
        viewer = self.viewer
        food_df = load_food_entry_data(source=self.source,
                                       base_path=self.base_path,
                                       subject_id=viewer.subject_id,
                                       filename=self.filename,
                                       client_df=self.client_df)

        day_meals = food_df[
            (food_df["time"] >= viewer.view_start) & (food_df["time"] < viewer.view_end)
        ]
        if day_meals.empty:
            return

        points, tooltips = [], {}
        for ax, start, end in viewer.iter_axes_by_time():
            ax_df = day_meals[(day_meals["time"] >= start) & (day_meals["time"] < end)]

            for _, row in ax_df.iterrows():
                food_name = row.get("food_name", "food_entry")
                carbs_val = row.get("carbohydrate")

                tip = f"{food_name}\n$\\bf{{Carbs:}}$ {carbs_val:.0f} g"

                idx = (viewer.df["time"] - row["time"]).abs().idxmin()
                gl = viewer.df.loc[idx, "gl"]

                s = self._size_from_carbs(carbs_val, viewer)

                pt = ax.scatter(row["time"], gl, s=s, color="orange", alpha=0.7,
                                linewidth=1.2, edgecolor="white", zorder=5)
                points.append(pt)
                tooltips[pt] = tip

        self._cursor = mplcursors.cursor(points, hover=True)

        @self._cursor.connect("add")
        def on_hover(sel):
            sel.annotation.set_text(tooltips.get(sel.artist, ""))
            sel.annotation.get_bbox_patch().set(fc="orange", alpha=0.4)

        @self._cursor.connect("remove")
        def on_unhover(sel):
            if sel.annotation is not None:
                sel.annotation.set_visible(False)
                if sel.annotation.figure:
                    sel.annotation.figure.canvas.draw_idle()


# --------------------------------
# CGM Biomarker Overlays
# --------------------------------
class CgmMeasuresOverlay:
    """
    Overlay that summarizes key CGM measures (e.g., TIR, CV, GMI, MAGE, HBGI, LBGI)
    in a compact annotation on the CGM axis.

    Parameters
    ----------
    sd_multiplier : float, default 1.0
        MAGE threshold multiplier used in the underlying summary function.
    loc : {'top-left', 'top-right'}, default 'top-left'
        Horizontal anchor for the annotation box.
    y : float, default 0.965
        Y-position in axis coordinates for the annotation box.
    margin : float, default 0.008
        Horizontal margin in axis coordinates from the anchored side.
    facecolor : str, default '#f7f7f7'
        Background color of the annotation box.
    edgecolor : str, default '#dcdcdc'
        Edge color of the annotation box.
    text_color : str, default '#111'
        Text color.
    pad : float, default 0.10
        Padding passed to the Matplotlib boxstyle.

    Notes
    -----
    Expects a function ``summarize_measures(df, sd_multiplier)`` to be available
    and the viewer to provide ``viewer.ax_cgm`` and ``viewer.scale``.
    """
    def __init__(self,
                 sd_multiplier: float = 1.0,
                 loc: str = "top-left",
                 y: float = 0.965,
                 margin: float = 0.008,
                 facecolor: str = "#f7f7f7",
                 edgecolor: str = "#dcdcdc",
                 text_color: str = "#111",
                 pad: float = 0.10):
        self.sd_multiplier = sd_multiplier
        self.loc = loc
        self.y = y
        self.margin = margin
        self.facecolor = facecolor
        self.edgecolor = edgecolor
        self.text_color = text_color
        self.pad = pad

    @staticmethod
    def _fmt(v, unit=""):
        if v is None or (isinstance(v, float) and not np.isfinite(v)):
            return "—"
        return f"{v:.1f}{unit}"

    @staticmethod
    def _math_bold(label: str) -> str:
        safe = label.replace("–", "-")
        safe = safe.replace(" ", r"\ ")
        return rf"$\bf{{{safe}}}$"

    def draw(self):
        viewer = getattr(self, "viewer", None)
        ax = getattr(viewer, "ax_cgm", None)
        if viewer is None or ax is None or viewer.df.empty:
            return

        m = summarize_measures(viewer.df, sd_multiplier=self.sd_multiplier)

        parts = [
            (self._math_bold("TIR"),        self._fmt(m.get("in_range_70_180"), "%")),
            (self._math_bold("CV"),         self._fmt(m.get("cv_percent"), "%")),
            (self._math_bold("GMI"),        self._fmt(m.get("gmi_percent"), "%")),
            (self._math_bold("MAGE"),       self._fmt(m.get("MAGE"), " mg/dL")),
            (self._math_bold("HBGI"),       self._fmt(m.get("HBGI"))),
            (self._math_bold("LBGI"),       self._fmt(m.get("LBGI"))),
        ]

        text = " | ".join([f"{lbl}: {val}" for lbl, val in parts])

        ha = "left" if self.loc == "top-left" else "right"
        x = self.margin if ha == "left" else 1.0 - self.margin

        ax.text(
            x, self.y, text,
            ha=ha, va="center",
            fontsize=viewer.scale(10, 8),
            family="monospace",
            color=self.text_color,
            transform=ax.transAxes,
            bbox=dict(
                facecolor=self.facecolor,
                edgecolor=self.edgecolor,
                boxstyle=f"round,pad={self.pad}",
            ),
            zorder=15,
            clip_on=False,
        )


class CvOverlay:
    """
    Overlay that visualizes mean glucose and ±1 SD band, and annotates CV%.

    Parameters
    ----------
    color : str, default '#4a90e2'
        Base color for mean line and SD band.
    alpha : float, default 0.14
        Fill alpha for the SD band.
    scope : {'window', 'full'}, default 'window'
        Data scope for statistics. If 'window', use the visible range;
        if 'full', use the entire dataframe.

    Notes
    -----
    Requires a ``cv(df)`` helper that returns CV in percent and
    a viewer exposing ``viewer.df``, ``viewer.ax_cgm``, and ``viewer.scale``.
    """
    def __init__(self, color="#4a90e2", alpha=0.14, scope="window"):
        self.color = color
        self.alpha = alpha
        self.scope = scope

    def draw(self):
        viewer = getattr(self, "viewer", None)
        ax = getattr(viewer, "ax_cgm", None)

        if ax is None:
            return

        if self.scope == "full":
            w = viewer.df
        else:
            start, end = viewer.view_start, viewer.view_end
            w = viewer.df[(viewer.df["time"] >= start) & (viewer.df["time"] < end)]

        g = pd.to_numeric(w["gl"], errors="coerce").dropna()

        mean = float(np.nanmean(g))
        cv_percent = float(cv(w))
        sd = (cv_percent * mean) / 100.0

        # Visualization
        ax.axhline(mean, color=self.color, linewidth=viewer.scale(1.8, 1.2), alpha=0.7, zorder=-2)
        ax.axhspan(mean - sd, mean + sd, color=self.color, alpha=self.alpha, zorder=-3)

        # Annotation pill (top-right), bold label via mathtext
        txt = f"$\\bf{{CV}}$: {cv_percent:.1f}%   $\\bf{{Mean}}$: {mean:.1f}   $\\bf{{±1SD}}$: {sd:.1f}"
        ax.text(
            0.995, 0.965, txt,
            ha="right", va="center",
            fontsize=viewer.scale(10, 8), family="monospace", color="#111",
            transform=ax.transAxes,
            bbox=dict(facecolor="#f7f7f7", edgecolor="#dcdcdc", boxstyle="round,pad=0.10"),
            zorder=5, clip_on=False
        )


class MageOverlay:
    """
    Visualize Mean Amplitude of Glucose Excursions (MAGE) within the current
    window using spans and amplitude whiskers.

    The overlay shades each counted MAGE segment, draws a vertical amplitude
    line at the segment midpoint from local min → max, and can optionally
    plot short/long moving averages for context.

    Parameters
    ----------
    resample_rule : str, default '5min'
        Resampling rule for the intermediate regular grid used by MAGE logic.
    short_win : str, default '30min'
        Rolling window for the short moving average.
    long_win : str, default '2h'
        Rolling window for the long moving average.
    sd_multiplier : float, default 1.0
        Threshold multiplier for excursion eligibility (threshold = `mult` * SD).
    show_ma : bool, default False
        If True, draw thin short/long moving average lines for context.

    Notes
    -----
    Expects a function ``mage_ma_segments(df, resample_rule, short_win, long_win, sd_multiplier)``
    returning iterable of dicts with keys ``{"t0","t1","t_mid"}``, and a viewer with
    ``viewer.df``, ``viewer.view_start``, ``viewer.view_end`` and ``viewer.scale``.
    """
    def __init__(self,
                 resample_rule: str = "5min",
                 short_win: str = "30min",
                 long_win: str = "2h",
                 sd_multiplier: float = 1.0,
                 show_ma: bool = False):
        self.resample_rule = resample_rule
        self.short_win = short_win
        self.long_win = long_win
        self.sd_multiplier = sd_multiplier
        self.show_ma = show_ma

    def _subset_window(self, df: pd.DataFrame, start, end) -> pd.DataFrame:
        return df[(df["time"] >= start) & (df["time"] < end)].copy()

    def _local_minmax(self, df: pd.DataFrame, t0, t1) -> tuple[float, float, float, float]:
        w = df[(df["time"] >= t0) & (df["time"] <= t1)]
        g = pd.to_numeric(w["gl"], errors="coerce").dropna()

        gmin = float(g.min())
        gmax = float(g.max())

        g_first = float(g.iloc[0])
        g_last = float(g.iloc[-1])
        return gmin, gmax, g_first, g_last

    def _draw_ma_thin(self, ax, df: pd.DataFrame, viewer):
        s = pd.Series(pd.to_numeric(df["gl"], errors="coerce").values,
                      index=pd.to_datetime(df["time"], errors="coerce")).dropna()
        if s.empty:
            return
        s = s.sort_index()
        s5 = s.resample(self.resample_rule).mean().interpolate("time").dropna()
        sma = s5.rolling(self.short_win, min_periods=1, center=True).mean()
        lma = s5.rolling(self.long_win,  min_periods=1, center=True).mean()

        ax.plot(sma.index, sma.values, color="#2c7fb8",
                linewidth=viewer.scale(1.0, 0.8), alpha=0.7, zorder=2)
        ax.plot(lma.index, lma.values, color="#7b3294",
                linewidth=viewer.scale(1.0, 0.8), alpha=0.7, zorder=2)

    def draw(self):
        viewer = getattr(self, "viewer", None)
        ax = getattr(viewer, "ax_cgm", None)
        if viewer is None or ax is None:
            return

        window_df = self._subset_window(viewer.df, viewer.view_start, viewer.view_end)
        if window_df.empty:
            return

        segs = mage_ma_segments(
            window_df,
            resample_rule=self.resample_rule,
            short_win=self.short_win,
            long_win=self.long_win,
            sd_multiplier=self.sd_multiplier
        )

        if self.show_ma:
            self._draw_ma_thin(ax, window_df, viewer)

        dt_total = (viewer.view_end - viewer.view_start)
        cap_half = dt_total * 0.006

        for seg in segs:
            t0, t1 = seg["t0"], seg["t1"]
            t_mid = seg["t_mid"]

            gmin, gmax, g_first, g_last = self._local_minmax(window_df, t0, t1)

            is_up = (g_last >= g_first)
            color = "#8bd3c7" if is_up else "#f4a6b8"

            # Shade the segment duration
            ax.axvspan(t0, t1, color=color, alpha=0.18, zorder=1)

            # Amplitude whisker at midpoint
            ax.vlines(t_mid, gmin, gmax, color=color,
                      linewidth=viewer.scale(2.0, 1.5), alpha=0.9, zorder=3)

            # Small end-caps at min/max (to visually bracket amplitude)
            ax.hlines(gmin, t_mid - cap_half, t_mid + cap_half, color=color,
                      linewidth=viewer.scale(1.5, 1.2), alpha=0.9, zorder=3)
            ax.hlines(gmax, t_mid - cap_half, t_mid + cap_half, color=color,
                      linewidth=viewer.scale(1.5, 1.2), alpha=0.9, zorder=3)


# --------------------------------
# Multi-modal Biomarker Overlays
# --------------------------------
class WakeupGlucoseOverlay:
    """
    Overlay that marks wake-up glucose values derived from sleep data.

    Parameters
    ----------
    source : {'file', 'client'}
        Source of the sleep data (file-based or in-memory).
    base_path : str or None, default None
        Base directory for file-based loading (if `source='file'`).
    subject_id : int or None, default None
        Optional subject identifier (not used for client data).
    filename : str or None, default None
        File name for file-based loaders.
    client_df : pandas.DataFrame or None, default None
        Preloaded sleep dataframe for `source='client'`.
    min_sleep_hours : float, default 8.0
        Minimum sleep duration (hours) to qualify for a wake-up event.
    nights : pandas.DataFrame or None, default None
        Output of :func:`~cgmsandbox.loader.load_sleep_nights`. Use this instead of
        ``source`` when the study records aggregate nightly sleep with no stage
        episodes, in which case ``load_sleep_data`` has nothing to read.

    Notes
    -----
    Relies on helper functions ``load_sleep_data(...)`` and
    ``extract_wakeup_glucose(cgm_df, sleep_df, min_sleep_hours)``.
    """
    def __init__(self,
                 source: Literal["file", "client"],
                 base_path: str | None = None,
                 subject_id: int | None = None,
                 filename: str | None = None,
                 client_df: Optional[pd.DataFrame] = None,
                 min_sleep_hours=8.0,
                 nights: Optional[pd.DataFrame] = None):
        self.source = source
        self.base_path = base_path
        self.filename = filename
        self.client_df = client_df
        self.min_sleep_hours = min_sleep_hours
        self.nights = nights

    def draw(self):
        viewer = self.viewer

        if self.nights is not None:
            # Aggregate per-night sleep: no stage episodes exist to load, so build
            # the block shape the helper reads from the night windows instead.
            sleep_df = _nights_as_episodes(self.nights)
        else:
            sleep_df = load_sleep_data(source=self.source,
                               base_path=self.base_path,
                               filename=self.filename,
                               client_df=self.client_df
                              )

        wg_df = extract_wakeup_glucose(viewer.df, sleep_df, min_sleep_hours=self.min_sleep_hours)
        if wg_df.empty:
            return

        wg_df = wg_df[
            (wg_df["wakeup_time"] >= viewer.view_start) & (wg_df["wakeup_time"] < viewer.view_end)
        ]

        for ax, start, end in viewer.iter_axes_by_time():
            ax_df = wg_df[(wg_df["wakeup_time"] >= start) & (wg_df["wakeup_time"] < end)]
            for _, row in ax_df.iterrows():
                s = viewer.scale(150, 60)
                fs = viewer.scale(10, 7)

                ax.scatter(row["wakeup_time"], row["wakeup_glucose"],
                           color="blue", s=s, edgecolor="white", linewidth=1.2, alpha=1, zorder=5)
                if getattr(viewer, "view_mode", None) != "full":
                    ax.text(
                        row["wakeup_time"], row["wakeup_glucose"] - viewer.scale(70, 30),
                        f"Wakeup Glucose:\n{row['wakeup_glucose']:.0f} mg/dL",
                        fontsize=fs, fontweight="bold", color="darkblue", ha="center", va="bottom",
                        bbox=dict(boxstyle="round,pad=0.3", fc="blue", alpha=0.1, ec="black", lw=0.8),
                        clip_on=True
                    )


class PPGROverlay:
    """
    Overlay that draws postprandial glucose responses (PPGR) following logged meals.

    Parameters
    ----------
    source : {'file', 'client'}
        Source of the meal data (file-based or in-memory).
    base_path : str or None, default None
        Base directory for file-based loading (if `source='file'`).
    subject_id : int or None, default None
        Optional subject identifier (for file-based loaders).
    filename : str or None, default None
        File name for file-based loaders.
    client_df : pandas.DataFrame or None, default None
        Preloaded meals dataframe for `source='client'`.
    window_minutes : int, default 120
        Length of the PPGR window after each meal.
    gap_minutes : int or None, default 10
        Maximum allowed time gap for continuous segments; if ``None``, traces are not broken.

    Notes
    -----
    Expects a viewer with ``viewer.df``, ``viewer.iter_axes_by_time()``, and
    scaling via ``viewer.scale``. Loaded meal dataframe should contain at least
    ``["time"]``; carbohydrate values are not required for drawing PPGR lines.
    """
    def __init__(self,
                 source: Literal["file", "client"],
                 base_path: str | None = None,
                 subject_id: int | None = None,
                 filename: str | None = None,
                 client_df: Optional[pd.DataFrame] = None,
                 window_minutes: int = 120,
                 gap_minutes: int | None = 10):
        self.source = source
        self.base_path = base_path
        self.filename = filename
        self.client_df = client_df
        self.window = pd.Timedelta(minutes=window_minutes)
        self.gap = (pd.Timedelta(minutes=gap_minutes) if gap_minutes is not None else None)

    def draw(self):
        v = self.viewer
        tz = getattr(v.view_start, "tzinfo", None)

        # Load food log aligned to the viewer's timezone (same pattern you use elsewhere)
        food_df = load_food_entry_data(source=self.source,
                                       base_path=self.base_path,
                                       subject_id=v.subject_id,
                                       filename=self.filename,
                                       client_df=self.client_df)

        # Meals that overlap the visible window once expanded by the PPGR window
        meals = food_df[(food_df["time"] < v.view_end) & (food_df["time"] + self.window > v.view_start)]

        lw = v.scale(3.0, 1.6)

        for ax, start, end in v.iter_axes_by_time():
            m_ax = meals[(meals["time"] < end) & (meals["time"] + self.window > start)]
            if m_ax.empty:
                continue

            for _, m in m_ax.iterrows():
                t0 = max(m["time"], start)
                t1 = min(m["time"] + self.window, end)

                sub = v.df[(v.df["time"] >= t0) & (v.df["time"] <= t1)][["time", "gl"]].dropna()
                if sub.shape[0] < 2:
                    continue
                sub = sub.sort_values("time").reset_index(drop=True)

                # Break only across large dropouts; keep continuous color otherwise
                if self.gap is not None:
                    seg_id = (sub["time"].diff() > self.gap).fillna(False).cumsum()
                else:
                    seg_id = pd.Series(0, index=sub.index)

                for _, seg in sub.groupby(seg_id):
                    if len(seg) < 2:
                        continue
                    ax.plot(
                        seg["time"], seg["gl"],
                        color="#6c5ce7",
                        linewidth=lw, solid_capstyle="round",
                        zorder=6, clip_on=True
                    )


class SleepWindowOverlay:
    """Shade sleep windows behind the glucose trace.

    Registered via ``viewer.add_overlay(...)``. Works in both 'daily' and 'full'
    view because it walks ``viewer.iter_axes_by_time()``.

    Parameters
    ----------
    nights : pandas.DataFrame
        Output of :func:`~cgmsandbox.loader.load_sleep_nights`.
    color : str
        Fill colour of the sleep band.
    alpha : float
        Fill opacity. Keep it low so the glucose trace stays readable.
    outline : bool
        Draw a hairline on the band edges so boundaries stay legible where the
        band overlaps the target range shading.
    """

    def __init__(self, nights: pd.DataFrame, color: str = "#3b6ea5",
                 alpha: float = 0.13, outline: bool = True):
        self.nights = nights
        self.color = color
        self.alpha = alpha
        self.outline = outline

    def draw(self):
        for ax, start, end in self.viewer.iter_axes_by_time():
            for _, r in self.nights.iterrows():
                s = max(r.sleep_start, start)
                e = min(r.sleep_end, end)
                if s < e:
                    ax.axvspan(
                        s, e, facecolor=self.color, alpha=self.alpha, zorder=0,
                        edgecolor=self.color if self.outline else "none",
                        linewidth=0.8 if self.outline else 0,
                    )


def _nights_as_episodes(nights: pd.DataFrame) -> pd.DataFrame:
    """Present aggregate per-night sleep in the episode shape the helpers want.

    ``load_sleep_nights`` returns one row per night with ``sleep_start`` and
    ``sleep_end``. Studies that record only aggregate durations have no stage
    episodes, so the episode-consuming helpers cannot read them directly. One
    night is one block of sleep, which is all ``extract_wakeup_glucose`` needs to
    find a wake time, so this maps each night onto a single ``asleep`` episode.
    """
    return pd.DataFrame({
        "start": nights["sleep_start"],
        "end": nights["sleep_end"],
        "stage": "asleep",
    }).sort_values("start").reset_index(drop=True)


class MageJumpOverlay:
    """Mark the glucose jumps that a consecutive-difference MAGE averages.

    MAGE is reported as a single number: the mean of the absolute difference
    between consecutive readings, counting only differences above a threshold.
    That definition is easy to state and hard to picture, because nothing in the
    number shows *which* jumps produced it. This overlay draws a segment across
    every qualifying jump, so the values behind the mean are visible on the trace.

    Jumps are measured on ``viewer.df``, the frame the viewer actually draws, so
    every segment lands on two readings you can see. ``process_cgm`` trims the
    first and last partial days and the first 24 hours, so the set here is a
    subset of the one behind a MAGE computed over an untrimmed frame. The mean of
    the marked segments is therefore close to, but not identical to, a value
    computed before trimming.

    See Also
    --------
    MageOverlay : the moving-average segment method, which resamples first and
        shades counted segments instead of consecutive reading pairs.
    mage_ma_segments : the segment detector behind :class:`MageOverlay`.

    Parameters
    ----------
    threshold : float
        Differences above this value count as excursions. Pass the same 1 SD
        figure the notebook used when it computed MAGE.
    color : str
        Colour of the marked segments.
    width : float
        Segment linewidth in the daily view, scaled down for the full view.
    """

    def __init__(self, threshold: float, color: str = "#c0392b", width: float = 2.4):
        self.threshold = threshold
        self.color = color
        self.width = width

    def draw(self):
        df = self.viewer.df
        for ax, start, end in self.viewer.iter_axes_by_time():
            window = df[(df["time"] >= start) & (df["time"] < end)].sort_values("time")
            if len(window) < 2:
                continue

            g = pd.to_numeric(window["gl"], errors="coerce").reset_index(drop=True)
            times = window["time"].reset_index(drop=True)
            jump = g.diff().abs()

            for i in jump.index[(jump > self.threshold).fillna(False)]:
                if i == 0 or pd.isna(g[i]) or pd.isna(g[i - 1]):
                    continue
                ax.plot(
                    [times[i - 1], times[i]],
                    [g[i - 1], g[i]],
                    color=self.color,
                    lw=self.viewer.scale(self.width, self.width * 0.7),
                    solid_capstyle="round",
                    alpha=0.85,
                    zorder=4,
                )
