"""Offline layout and source contracts for the dashboard figure factories."""

from __future__ import annotations

import ast
import math
import unittest
from datetime import datetime, timedelta
from pathlib import Path

try:
    import pandas as pd

    from jupyterhealth_dashboard import core, figures

    HAS_PLOTLY = True
except Exception:  # pragma: no cover - dependency-specific environment
    HAS_PLOTLY = False


FIGURES_PATH = Path(__file__).resolve().parents[1] / "figures.py"

# Shared synthetic 24-hour 5/25/50/75/95 percentile profile used by the AGP tests.
# This one crosses 70 and 180 but stays above 54 and below 250.
AGP_SAMPLE = [
    {"minute": minute, "p05": 55, "p25": 80, "p50": 110, "p75": 160, "p95": 245}
    for minute in range(0, 1441, 15)
]

# Entirely inside the 70--180 target band: no warm fill may appear anywhere.
AGP_IN_RANGE = [
    {"minute": minute, "p05": 80, "p25": 90, "p50": 110, "p75": 130, "p95": 160}
    for minute in range(0, 1441, 15)
]

# Crosses every AGP threshold (54, 70, 180, and 250) with sloped segments.
AGP_CROSSING_ALL = [
    {"minute": 0, "p05": 48, "p25": 65, "p50": 100, "p75": 210, "p95": 265},
    {"minute": 15, "p05": 60, "p25": 90, "p50": 120, "p75": 200, "p95": 240},
    {"minute": 30, "p05": 82, "p25": 100, "p50": 130, "p75": 190, "p95": 258},
    {"minute": 45, "p05": 74, "p25": 95, "p50": 120, "p75": 175, "p95": 205},
]

# The five semantic value bands in display order and their inclusive clip bounds.
AGP_BAND_BOUNDS = {
    "Very low (<54)": (-math.inf, 54),
    "Low (54–<70)": (54, 70),
    "Target (70–180)": (70, 180),
    "High (>180–250)": (180, 250),
    "Very high (>250)": (250, math.inf),
}


def _agp_fill_traces(figure):
    return [trace for trace in figure.data if trace.fill == "toself"]


class FigureSourceContractTests(unittest.TestCase):
    def test_no_fixed_desktop_width_constant_is_used(self):
        source = FIGURES_PATH.read_text()
        tree = ast.parse(source)
        self.assertNotIn("DESKTOP_DEMO_CONTENT_WIDTH", source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "DESKTOP_DEMO_CONTENT_WIDTH":
                        self.fail("fixed desktop content width assignment still exists")

    def test_meal_text_is_not_painted_as_chart_text(self):
        source = FIGURES_PATH.read_text()
        self.assertNotIn("markers+text", source)
        self.assertNotIn("textposition", source)
        self.assertNotIn("textfont", source)
        self.assertIn("customdata=_meal_customdata(meals)", source)
        self.assertIn("customdata[0]", source)
        self.assertIn("customdata[7]", source)


@unittest.skipUnless(HAS_PLOTLY, "plotly/pandas are not installed in this interpreter")
class FigureLayoutContractTests(unittest.TestCase):
    def test_glucose_trace_is_autosized_and_has_no_fixed_width(self):
        start = datetime(2026, 10, 1, 8, 0)
        glucose = pd.DataFrame(
            {
                "recorded_at": [start + timedelta(minutes=5 * i) for i in range(6)],
                "mg_dl": [90, 110, 130, 120, 100, 95],
            }
        )
        explorer = {
            "glucose": glucose,
            "meals": pd.DataFrame(
                {
                    "occurred_at": [start],
                    "label": ["Lunch"],
                    "meal_type": ["meal"],
                    "carbohydrate_g": [45.0],
                    "calories_kcal": [400.0],
                }
            ),
            "activity": pd.DataFrame(),
            "sleep": pd.DataFrame(),
        }
        figure = figures.glucose_trace_figure(explorer, height=620)
        self.assertTrue(figure.layout.autosize)
        self.assertIsNone(figure.layout.width)
        self.assertEqual(figure.layout.height, 620)

    def test_scripted_sushi_figure_is_autosized(self):
        figure = figures.scripted_sushi_figure(core.scripted_sushi_fallback(), height=420)
        self.assertTrue(figure.layout.autosize)
        self.assertIsNone(figure.layout.width)
        self.assertEqual(figure.layout.height, 420)

    def test_agp_profile_is_autosized_and_has_no_fixed_width(self):
        figure = figures.agp_profile_figure({"percentiles": AGP_SAMPLE}, height=430)
        self.assertTrue(figure.layout.autosize)
        self.assertIsNone(figure.layout.width)
        self.assertEqual(figure.layout.height, 430)

    def test_agp_profile_default_height_is_in_the_requested_material_range(self):
        figure = figures.agp_profile_figure({"percentiles": AGP_SAMPLE})
        self.assertGreaterEqual(figure.layout.height, 560)
        self.assertLessEqual(figure.layout.height, 600)

    def test_agp_target_field_keeps_the_70_180_band(self):
        figure = figures.agp_profile_figure({"percentiles": AGP_SAMPLE}, height=430)
        self.assertEqual(figure.layout.shapes[0].y0, 70)
        self.assertEqual(figure.layout.shapes[0].y1, 180)

    def test_agp_entirely_in_range_has_only_green_fill(self):
        figure = figures.agp_profile_figure({"percentiles": AGP_IN_RANGE}, height=430)
        fills = _agp_fill_traces(figure)
        self.assertTrue(fills)
        for trace in fills:
            self.assertEqual(trace.name, "Target (70–180)")
            self.assertEqual(trace.fillcolor, figures.AGP_VALUE_TARGET)
            self.assertEqual(trace.line.width, 0)
            self.assertEqual(trace.hoverinfo, "skip")
            ys = [value for value in trace.y if value is not None]
            self.assertGreaterEqual(min(ys), 70)
            self.assertLessEqual(max(ys), 180)

    def test_agp_no_low_fill_when_all_percentiles_are_at_or_above_70(self):
        profile = [
            {"minute": minute, "p05": 70, "p25": 90, "p50": 110, "p75": 140, "p95": 180}
            for minute in range(0, 1441, 15)
        ]
        figure = figures.agp_profile_figure({"percentiles": profile}, height=430)
        fill_names = {trace.name for trace in _agp_fill_traces(figure)}
        self.assertEqual(fill_names, {"Target (70–180)"})

    def test_agp_crossing_thresholds_clips_fill_extents(self):
        figure = figures.agp_profile_figure({"percentiles": AGP_CROSSING_ALL}, height=430)
        by_name: dict[str, list[float]] = {}
        for trace in _agp_fill_traces(figure):
            by_name.setdefault(trace.name, []).extend(
                value for value in trace.y if value is not None
            )

        self.assertEqual(set(by_name), set(AGP_BAND_BOUNDS))
        for name, ys in by_name.items():
            low, high = AGP_BAND_BOUNDS[name]
            self.assertGreaterEqual(min(ys), low)
            self.assertLessEqual(max(ys), high)

    def test_agp_clipping_keeps_exact_sloped_crossings(self):
        profile = [
            {"minute": 0, "p05": 60, "p25": 90, "p50": 120, "p75": 170, "p95": 200},
            {"minute": 15, "p05": 80, "p25": 90, "p50": 120, "p75": 170, "p95": 200},
        ]
        figure = figures.agp_profile_figure({"percentiles": profile}, height=430)

        low = next(
            trace for trace in _agp_fill_traces(figure) if trace.name == "Low (54–<70)"
        )
        self.assertTrue(
            any(abs(x - 7.5) < 1e-9 and abs(y - 70.0) < 1e-9 for x, y in zip(low.x, low.y))
        )

        target = next(
            trace for trace in _agp_fill_traces(figure) if trace.name == "Target (70–180)"
        )
        target_xs = list(target.x)
        self.assertTrue(any(abs(x - 7.5) < 1e-9 for x in target_xs))
        self.assertTrue(any(abs(x - 0.0) < 1e-9 for x in target_xs))
        self.assertTrue(any(abs(x - 15.0) < 1e-9 for x in target_xs))

    def test_agp_median_line_is_green_and_drawn_on_top(self):
        figure = figures.agp_profile_figure({"percentiles": AGP_SAMPLE}, height=430)
        median = figure.data[-1]
        self.assertEqual(median.name, "50th median")
        self.assertEqual(median.line.color, figures.AGP_MEDIAN)
        self.assertIsNone(median.fill)
        self.assertIn("median", median.hovertemplate)
        self.assertIn("mg/dL", median.hovertemplate)
        fill_indices = [
            index for index, trace in enumerate(figure.data) if trace.fill == "toself"
        ]
        self.assertGreater(len(figure.data) - 1, max(fill_indices))

    def test_agp_has_only_median_as_a_stroke_line(self):
        figure = figures.agp_profile_figure({"percentiles": AGP_SAMPLE}, height=430)
        stroke_traces = [
            trace
            for trace in figure.data
            if trace.mode == "lines" and getattr(trace, "fill", None) is None
        ]
        self.assertEqual([trace.name for trace in stroke_traces], ["50th median"])
        self.assertEqual(stroke_traces[0].line.color, figures.AGP_MEDIAN)
        for forbidden in ("p05", "p25", "p75", "p95", "5th–95th", "25th–75th"):
            self.assertNotIn(forbidden, [trace.name for trace in stroke_traces])

    def test_agp_legend_lists_value_bands_and_only_the_median_rank(self):
        figure = figures.agp_profile_figure({"percentiles": AGP_SAMPLE}, height=430)
        legend = figure.layout.legend
        self.assertTrue(figure.layout.showlegend)
        self.assertEqual(legend.orientation, "h")
        self.assertEqual(legend.x, 0)
        self.assertLess(legend.y, 0)
        self.assertEqual(legend.yanchor, "top")
        self.assertGreaterEqual(getattr(figure.layout, "margin").b, 100)

        visible = [trace for trace in figure.data if trace.showlegend is not False]
        ordered = sorted(visible, key=lambda trace: trace.legendrank)
        names = [trace.name for trace in ordered]
        self.assertIn("50th median", names)
        for present in ("Low (54–<70)", "Target (70–180)", "High (>180–250)"):
            self.assertIn(present, names)
        for absent in ("Very low (<54)", "Very high (>250)"):
            self.assertNotIn(absent, names)
        for old_rank in ("5th–95th", "25th–75th", "5th–25th", "25th–50th", "50th–75th", "75th–95th"):
            self.assertNotIn(old_rank, names)

    def test_agp_in_range_legend_has_no_warm_categories(self):
        figure = figures.agp_profile_figure({"percentiles": AGP_IN_RANGE}, height=430)
        fill_names = {trace.name for trace in _agp_fill_traces(figure)}
        self.assertEqual(fill_names, {"Target (70–180)"})
        names = {trace.name for trace in figure.data if trace.showlegend is not False}
        for warm in ("Very low (<54)", "Low (54–<70)", "High (>180–250)", "Very high (>250)"):
            self.assertNotIn(warm, names)

    def test_agp_y_axis_range_covers_all_percentiles(self):
        profile = [
            {"minute": 0, "p05": 48, "p25": 60, "p50": 100, "p75": 230, "p95": 320}
        ]
        figure = figures.agp_profile_figure({"percentiles": profile}, height=430)
        self.assertLessEqual(figure.layout.yaxis.range[0], 48)
        self.assertGreaterEqual(figure.layout.yaxis.range[1], 320)

    def test_agp_has_no_on_plot_percentile_annotations(self):
        figure = figures.agp_profile_figure({"percentiles": AGP_SAMPLE}, height=430)
        self.assertEqual(len(figure.layout.annotations), 0)

    def test_agp_boundary_lines_use_green_targets_and_red_low(self):
        figure = figures.agp_profile_figure({"percentiles": AGP_SAMPLE}, height=430)
        shapes = {getattr(shape, "y0", None): shape for shape in figure.layout.shapes}
        self.assertEqual(shapes[70].line.color, figures.AGP_TARGET_LINE)
        self.assertEqual(shapes[180].line.color, figures.AGP_TARGET_LINE)
        self.assertEqual(shapes[54].line.color, figures.AGP_LOW_LINE)

    def test_agp_profile_handles_missing_percentiles(self):
        figure = figures.agp_profile_figure({}, height=430)
        self.assertTrue(figure.layout.autosize)
        self.assertEqual(len(figure.data), 0)
        self.assertFalse(figure.layout.showlegend)
        self.assertEqual(len(figure.layout.annotations), 0)

    def test_meal_marker_carries_tooltip_customdata_without_chart_text(self):
        start = datetime(2026, 10, 1, 8, 0)
        glucose = pd.DataFrame(
            {
                "recorded_at": [start + timedelta(minutes=5 * i) for i in range(6)],
                "mg_dl": [90, 110, 130, 120, 100, 95],
            }
        )
        explorer = {
            "glucose": glucose,
            "meals": pd.DataFrame(
                {
                    "occurred_at": [start],
                    "label": ["Sushi lunch"],
                    "meal_type": ["lunch"],
                    "carbohydrate_g": [52.0],
                    "protein_g": [18.0],
                    "fat_g": [12.0],
                    "fiber_g": [3.0],
                    "calories_kcal": [420.0],
                    "activity_context": ["~900 steps in 60 min after meal"],
                }
            ),
            "activity": pd.DataFrame(),
            "sleep": pd.DataFrame(),
        }
        figure = figures.glucose_trace_figure(explorer, height=620)
        meal_trace = next(trace for trace in figure.data if trace.name == "Meals")

        self.assertEqual(meal_trace.mode, "markers")
        self.assertFalse(meal_trace.text)
        self.assertIn("customdata", meal_trace.hovertemplate)
        self.assertIn("customdata[0]", meal_trace.hovertemplate)
        self.assertIn("customdata[7]", meal_trace.hovertemplate)

        self.assertEqual(meal_trace.customdata[0][0], "Sushi lunch")
        self.assertEqual(meal_trace.customdata[0][1], "lunch")
        self.assertEqual(meal_trace.customdata[0][2], 52.0)
        self.assertEqual(meal_trace.customdata[0][7], "~900 steps in 60 min after meal")

        for annotation in figure.layout.annotations:
            self.assertNotEqual(annotation.text, "Sushi lunch")

    def test_empty_optional_modalities_add_no_traces(self):
        start = datetime(2026, 10, 1, 8, 0)
        explorer = {
            "glucose": pd.DataFrame(
                {
                    "recorded_at": [start + timedelta(minutes=5 * i) for i in range(6)],
                    "mg_dl": [90, 110, 130, 120, 100, 95],
                }
            ),
            "meals": pd.DataFrame(),
            "activity": pd.DataFrame(),
            "sleep": pd.DataFrame(),
        }
        figure = figures.glucose_trace_figure(explorer, height=620)
        names = {trace.name for trace in figure.data}
        self.assertNotIn("Meals", names)
        self.assertNotIn("Activity", names)
        self.assertNotIn("Deep", names)
        self.assertNotIn("Light", names)
        self.assertNotIn("REM", names)


if __name__ == "__main__":
    unittest.main()
