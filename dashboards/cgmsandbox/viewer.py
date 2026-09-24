import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib as mpl
import pandas as pd
from ipywidgets import widgets, VBox, HBox, Output, Layout
from datetime import time, timedelta
from pathlib import Path
from typing import Literal, Optional

import matplotlib.font_manager  # noqa: F401  (ensures mpl.font_manager is bound)

from .loader import load_cgm_data
from .cgm_methods import process_cgm


## Setup fonts — resolved relative to the package so it works wherever it is
## installed (editable checkout, site-packages, or a notebook in another dir).
_PKG_DIR = Path(__file__).resolve().parent
_FONT_PATH = _PKG_DIR / "fonts" / "Lato-Regular.ttf"
if _FONT_PATH.exists():
    mpl.font_manager.fontManager.addfont(str(_FONT_PATH))
    mpl.rcParams["font.family"] = "Lato"


class CGMViewer:
    def __init__(self,
                 source: Literal["file", "client"],
                 base_path: str | None = None,
                 subject_id: int | None = None,
                 filename: str | None = None,
                 client_df: Optional[pd.DataFrame] = None,
                 gl_range=(0, 400)):

        self.subject_id = subject_id
        self.y_min, self.y_max = gl_range

        raw_cgm_df = load_cgm_data(source=source,
                                   base_path=base_path,
                                   subject_id=subject_id,
                                   filename=filename,
                                   client_df=client_df
                                  )
        self.df = process_cgm(raw_cgm_df)

        # Extract unique days
        self.df["date"] = self.df["time"].dt.date
        self.unique_days = sorted(self.df["date"].unique())

        # Components
        self.overlays = []
        self.extensions = []

        # State (updated per render)
        self.selected_date = None
        self.view_start = None
        self.view_end = None
        self.day_df = None
        self.axes = None
        self.ax_cgm = None

        # Widgets
        self.out = Output()
        # Button Layouts
        btn_layout = widgets.Layout(
            width="44px",
            height="30px",
            padding="0",
            border="1px solid #d0d0d0",
            border_radius="10px",
            overflow="hidden"
        )

        self.day_dropdown = widgets.Dropdown(options=self.unique_days)
        self.back_btn = widgets.Button(
            description="←",               # thick, filled arrow
            tooltip="Previous day",
            layout=btn_layout,
            style=widgets.ButtonStyle(button_color="#f5f5f5")  # light gray background, black arrow text
        )

        self.fwd_btn = widgets.Button(
            description="→",
            tooltip="Next day",
            layout=btn_layout,
            style=widgets.ButtonStyle(button_color="#f5f5f5")
        )
        self.day_index = {"idx": 0}

        # Bind callbacks
        self.day_dropdown.observe(self._change_day, names="value")
        self.back_btn.on_click(self._go_back)
        self.fwd_btn.on_click(self._go_fwd)

    # --- Styling ---
    def _style_axis(self, ax):
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        for axis in ["left", "bottom"]:
            ax.spines[axis].set_linewidth(1.8)
            ax.spines[axis].set_color("#D3D3D3")


        ax.tick_params(axis="both", which="both", length=0)
        ax.tick_params(axis="y", pad=8)
        ax.tick_params(axis="x", pad=8)

        ax.set_ylabel(
            "mg/dL",
            rotation=0,
            labelpad=0,
            ha="right",
            color="0.2"
        )
        ax.yaxis.set_label_coords(0, 1.05)
        ax.yaxis.set_label_position("left")

    # --- Public API ---
    def add_overlay(self, overlay):
        overlay.viewer = self
        self.overlays.append(overlay)


    def add_extensions(self, extension):
        extension.viewer = self
        self.extensions.append(extension)


    def show(self, view_mode="daily"):
        # Setting .value fires the dropdown observer (_change_day), which renders.
        # Unhook it for this one assignment so the explicit render below is the
        # only render -- otherwise every show() builds two ipympl figures, which
        # doubles the widget traffic and orphans the first canvas.
        self.day_dropdown.unobserve(self._change_day, names="value")
        try:
            self.day_dropdown.value = self.unique_days[0]
        finally:
            self.day_dropdown.observe(self._change_day, names="value")

        self.selected_date = self.unique_days[0]
        self.render(view_mode=view_mode)

        if view_mode == "daily":
            toolbar = HBox([self.back_btn, self.day_dropdown, self.fwd_btn],
                        layout=widgets.Layout(
                            justify_content="center",
                            align_items="center",
                            width="100%",
                            padding="6px 0 8px 0"
                        ))

            container = VBox([toolbar, self.out],
                             layout=widgets.Layout(align_items="center", width="100%"))

            return container
        else:
            return VBox([self.out])


    def render(self, view_mode="daily"):
        self.view_mode = view_mode
        if view_mode == "daily":
            self._render_day(self.selected_date or self.unique_days[0])
        elif view_mode == "full":
            self._render_full()
        else:
            raise ValueError(f"Unknown view model: {view_mode}")


    # --- Internal rendering ---
    def _render_day(self, selected_date):
        self.selected_date = selected_date
        self.day_df = self.df[self.df["date"] == selected_date]

        tzinfo = self.day_df["time"].iloc[0].tzinfo
        self.view_start = pd.Timestamp.combine(pd.to_datetime(selected_date), time(0, 0)).replace(tzinfo=tzinfo)
        self.view_end = self.view_start + timedelta(days=1)

        nrows = 1 + len(self.extensions)
        heights = [3] + [2] * len(self.extensions)

        with self.out:
            self.out.clear_output(wait=True)
            # ipympl canvases are widgets: leaving the previous one open leaks a
            # comm per redraw and eventually stalls the frontend.
            if getattr(self, "_fig", None) is not None:
                plt.close(self._fig)
                self._fig = None
            fig, self.axes = plt.subplots(
                nrows=nrows, figsize=(15, sum(heights)),
                sharex=True, gridspec_kw={"height_ratios": heights}
            )
            fig.canvas.header_visible = False
            self._fig = fig
            if nrows == 1:
                self.axes = [self.axes]

            # CGM plot
            self.ax_cgm = self.axes[0]
            self.ax_cgm.plot(self.day_df["time"], self.day_df["gl"], color="black")
            self._style_axis(self.ax_cgm)

            self.ax_cgm.set_ylim(self.y_min, self.y_max)
            self.ax_cgm.set_xlim(self.view_start, self.view_end)
            self.ax_cgm.xaxis.set_major_locator(mdates.HourLocator(interval=2, tz=tzinfo))
            self.ax_cgm.xaxis.set_major_formatter(mdates.DateFormatter("%-I %p", tz=tzinfo))

            # Apply overlays
            for overlay in self.overlays:
                overlay.draw()

            # Apply extensions
            for ext, ax in zip(self.extensions, self.axes[1:]):
                ext.ax = ax
                ext.draw()

            plt.tight_layout()
            plt.show()


    def _render_full(self):
        self.df["weekday"] = pd.to_datetime(self.df["date"]).dt.weekday
        self.df["week_index"] = ((pd.to_datetime(self.df["date"]) - pd.to_datetime(self.unique_days[0])).dt.days // 7)

        tzinfo = self.df["time"].iloc[0].tzinfo
        start = self.df["time"].min().replace(hour=0, minute=0, second=0)

        with self.out:
            self.out.clear_output(wait=True)
            if getattr(self, "_fig", None) is not None:
                plt.close(self._fig)
                self._fig = None
            fig, axes = plt.subplots(nrows=2, figsize=(20, 4), sharey=True)
            fig.canvas.header_visible = False
            self._fig = fig
            self.view_start = start
            self.view_end = start + timedelta(days=14)
            self.axes = list(axes)
            self.ax_cgm = None

            for week_idx in range(2):
                ax = axes[week_idx]
                week_df = self.df[self.df["week_index"] == week_idx]
                ax.plot(week_df["time"], week_df["gl"], color="black", linewidth=1)

                # Day boundaries and labels
                days = pd.date_range(start=start + timedelta(days=7 * week_idx), periods=7, freq="D")
                for d in days:
                    # Vertical lines at 12 AM and 12 PM
                    for hour in [0, 12]:
                        ax.axvline(d + timedelta(hours=hour), color="lightgray", linestyle="-", linewidth=0.8)

                    # Day name
                    center = d + timedelta(hours=12)
                    ax.text(center, self.y_max, d.strftime("%A"), ha="center", va="bottom", fontsize=10)

                    # Date box in top-left
                    ax.text(d + timedelta(hours=0.4), self.y_max-15, d.strftime("%-m/%-d"),
                            ha="left", va="top", fontsize=9)

                ax.set_xlim(start + timedelta(days=7 * week_idx), start + timedelta(days=7 * (week_idx + 1)))
                ax.set_ylim(self.y_min, self.y_max)
                ax.set_ylabel("mg/dL")
                ax.xaxis.set_major_locator(mdates.HourLocator(byhour=[12], tz=tzinfo))
                ax.xaxis.set_major_formatter(mdates.DateFormatter("%I %p", tz=tzinfo))
                ax.tick_params(axis='x', labelrotation=0)

            for overlay in self.overlays:
                overlay.draw()

            plt.tight_layout()
            plt.show()

    # --- Navigation ---
    def _change_day(self, change):
        self.day_index["idx"] = self.day_dropdown.options.index(change["new"])
        self._render_day(change["new"])


    def _go_back(self, _):
        idx = self.unique_days.index(self.day_dropdown.value)
        if idx > 0:
            self.day_dropdown.value = self.unique_days[idx - 1]


    def _go_fwd(self, _):
        idx = self.unique_days.index(self.day_dropdown.value)
        if idx < len(self.unique_days) - 1:
            self.day_dropdown.value = self.unique_days[idx + 1]

    # --- Helper ---
    def iter_axes_by_time(self):
        if hasattr(self, "axes") and isinstance(self.axes, (list, tuple)):
            for i, ax in enumerate(self.axes):
                start = self.view_start + timedelta(days=7 * i)
                end = start + timedelta(days=7)
                yield ax, start, end
        elif self.ax_cgm is not None:
            yield self.ax_cgm, self.view_start, self.view_end


    def scale(self, daily_value, full_value):
        return daily_value if self.view_mode == "daily" else full_value
