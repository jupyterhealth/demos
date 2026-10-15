"""Offline contracts for the role header and compact clinical cards."""

from __future__ import annotations

import re
import unittest
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

try:
    from jupyterhealth_dashboard import ui

    HAS_WIDGETS = True
except Exception:  # pragma: no cover - dependency-specific environment
    HAS_WIDGETS = False


UI_PATH = Path(__file__).resolve().parents[1] / "ui.py"


def _walk(widget):
    yield widget
    for child in getattr(widget, "children", ()):
        yield from _walk(child)


@unittest.skipUnless(HAS_WIDGETS, "ipywidgets/plotly are not installed in this interpreter")
class RoleHeaderContractTests(unittest.TestCase):
    def test_practitioner_heading_is_sole_intro(self):
        html = ui._role_header({"heading": "Hi Dr. Kishore"}).value
        self.assertIn('<h1 class="jh-greeting">Hi Dr. Kishore</h1>', html)
        self.assertNotIn("Continuous glucose monitor", html)
        self.assertNotIn("Review the latest CGM", html)

    def test_patient_heading_is_sole_intro(self):
        html = ui._role_header({"heading": "Hi Alex"}).value
        self.assertIn('<h1 class="jh-greeting">Hi Alex</h1>', html)
        self.assertNotIn("Continuous glucose monitor", html)
        self.assertNotIn("latest recording", html)


@unittest.skipUnless(HAS_WIDGETS, "ipywidgets/plotly are not installed in this interpreter")
class RoleBadgeContractTests(unittest.TestCase):
    def test_practitioner_badge_is_clinician_view_with_notes_icon(self):
        html = ui._role_header({"role": "practitioner", "heading": "Hi Dr. Kishore"}).value
        self.assertIn("jh-role-badge-practitioner", html)
        self.assertIn("Clinician view", html)
        self.assertIn("jh-icon", html)
        self.assertNotIn("Patient view", html)

    def test_patient_badge_is_patient_view_with_body_scan_icon(self):
        html = ui._role_header({"role": "patient", "heading": "Hi Alex"}).value
        self.assertIn("jh-role-badge-patient", html)
        self.assertIn("Patient view", html)
        self.assertIn("jh-icon", html)
        self.assertNotIn("Clinician view", html)


@unittest.skipUnless(HAS_WIDGETS, "ipywidgets/plotly are not installed in this interpreter")
class DashboardLayoutContractTests(unittest.TestCase):
    @staticmethod
    def _view() -> dict:
        start = datetime(2026, 10, 1, 8, 0)
        return {
            "role": "practitioner",
            "heading": "Hi Dr. Kishore",
            "patient": {
                "name": "Alex K.",
                "initials": "AK",
                "facts": ["38 years · male", "MRN 40032"],
            },
            "context_cards": [],
            "medications": [],
            "treatment_options_under_review": True,
            "glucose": {
                "period": "Sep 13 – Sep 26, 2026",
                "time_active_percent": 96.7,
                "metrics": {
                    "mean_mg_dl": 142.3,
                    "gmi_percent": 6.7,
                    "cv_percent": 34.1,
                },
                "bands": [
                    {"key": "very_high", "percent": 2.0},
                    {"key": "high", "percent": 17.3},
                    {"key": "target", "percent": 78.4},
                    {"key": "low", "percent": 2.1},
                    {"key": "very_low", "percent": 0.2},
                ],
                "percentiles": [
                    {"minute": minute, "p05": 55, "p25": 80, "p50": 110, "p75": 160, "p95": 245}
                    for minute in range(0, 1441, 15)
                ],
            },
            "explorer": {
                "glucose": pd.DataFrame(
                    {
                        "recorded_at": [start + timedelta(minutes=5 * i) for i in range(6)],
                        "mg_dl": [90, 110, 130, 120, 100, 95],
                    }
                ),
                "meals": pd.DataFrame(),
                "activity": pd.DataFrame(),
                "sleep": pd.DataFrame(),
            },
        }

    def test_dashboard_uses_full_width_without_fixed_pixel_cap(self):
        dashboard = ui.build_dashboard(self._view())
        self.assertEqual(dashboard.layout.max_width, "100%")
        self.assertEqual(dashboard.layout.width, "100%")
        self.assertEqual(dashboard.layout.margin, "0 auto")

    def test_plotly_widget_is_marked_for_full_width_stretching(self):
        dashboard = ui.build_dashboard(self._view())
        stack = [dashboard]
        plotly_widgets = []
        while stack:
            widget = stack.pop()
            if "jh-plotly-widget" in getattr(widget, "_dom_classes", ()):
                plotly_widgets.append(widget)
            stack.extend(getattr(widget, "children", ()))
        self.assertGreaterEqual(len(plotly_widgets), 1)
        for widget in plotly_widgets:
            self.assertTrue(widget._config.get("responsive"))
            self.assertIsNone(widget.layout.width)

    def test_dashboard_includes_hidden_plotly_resize_control(self):
        dashboard = ui.build_dashboard(self._view())
        controls = [
            widget
            for widget in _walk(dashboard)
            if "jh-plotly-resize" in getattr(widget, "_dom_classes", ())
        ]
        self.assertEqual(len(controls), 1)
        control = controls[0]
        self.assertEqual(control.layout.width, "0px")
        self.assertEqual(control.layout.height, "0px")
        self.assertTrue(control.outputs)
        script = control.outputs[0]["data"]["application/javascript"]
        self.assertIn("ResizeObserver", script)
        self.assertIn("Plotly.Plots.resize", script)
        self.assertIn(".jh-plotly-widget", script)

    def test_plotly_resize_strategy_observes_layout_changes_in_source(self):
        source = UI_PATH.read_text()
        self.assertIn("ResizeObserver", source)
        self.assertIn("Plotly.Plots.resize", source)
        self.assertIn("MutationObserver", source)
        self.assertIn("window.addEventListener(\"resize\", resizeAll)", source)
        self.assertIn("_plotly_resize_control", source)

    def test_dashboard_includes_agp_profile_in_both_roles(self):
        for role in ("patient", "practitioner"):
            view = self._view()
            view["role"] = role
            dashboard = ui.build_dashboard(view)
            stack = [dashboard]
            has_profile_section = False
            has_agp_figure = False
            while stack:
                widget = stack.pop()
                if isinstance(widget, ui.widgets.HTML):
                    if "Glucose profile" in widget.value:
                        has_profile_section = True
                if "jh-plotly-widget" in getattr(widget, "_dom_classes", ()):
                    has_agp_figure = True
                stack.extend(getattr(widget, "children", ()))
            self.assertTrue(has_profile_section, role)
            self.assertTrue(has_agp_figure, role)


@unittest.skipUnless(HAS_WIDGETS, "ipywidgets/plotly are not installed in this interpreter")
class PatientMetadataContractTests(unittest.TestCase):
    def test_patient_header_does_not_render_source_provenance(self):
        html = ui._patient_header(
            {
                "patient": {
                    "name": "Alex K.",
                    "initials": "AK",
                    "facts": [
                        "38 years · male",
                        "MRN 40032",
                    ],
                }
            }
        ).value
        self.assertIn("38 years", html)
        self.assertIn("MRN 40032", html)
        self.assertNotIn("Sep 13", html)
        self.assertNotIn("Source", html)
        self.assertNotIn("local demo fallback", html)
        self.assertNotIn("Berkeley hosted data", html)


@unittest.skipUnless(HAS_WIDGETS, "ipywidgets/plotly are not installed in this interpreter")
class ContextCardContractTests(unittest.TestCase):
    def test_clinical_value_formatter_keeps_units_tight(self):
        self.assertEqual(ui._fmt(6.2, "%", 1), "6.2%")
        self.assertEqual(ui._fmt(7.0, "%", 1), "7.0%")
        self.assertEqual(ui._fmt(112.0, "mg/dL", 0), "112 mg/dL")
        self.assertEqual(ui._fmt(128.0, "mmHg", 0), "128 mmHg")

    def test_card_shows_reference_range_and_elevated_label(self):
        card = ui._context_card(
            {
                "label": "Fasting glucose",
                "value": "112 mg/dL",
                "status": "high",
                "status_label": "Elevated",
                "icon": "glucose",
                "reference": "70–99 mg/dL",
                "date": "Oct 9, 2026",
            }
        )
        self.assertIn("jh-card-reference", card)
        self.assertIn("70–99 mg/dL", card)
        self.assertIn("Elevated", card)
        self.assertIn("jh-status-high", card)

    def test_reference_is_on_the_same_reading_line_as_value(self):
        card = ui._context_card(
            {
                "label": "Fasting glucose",
                "value": "112 mg/dL",
                "status": "high",
                "status_label": "Elevated",
                "icon": "glucose",
                "reference": "70–99 mg/dL",
                "date": "Oct 9, 2026",
            }
        )
        self.assertIn("jh-card-reading", card)
        reading_open = card.index("jh-card-reading")
        reading_close = card.index("</div>", card.index("112 mg/dL"))
        self.assertIn("112 mg/dL", card[reading_open:reading_close])
        self.assertIn("70–99 mg/dL", card[reading_open:reading_close])

    def test_informational_card_keeps_truthful_label(self):
        card = ui._context_card(
            {
                "label": "Weight",
                "value": "82.5 kg",
                "status": "na",
                "status_label": "Informational",
                "icon": "weight",
                "reference": "Reference varies",
            }
        )
        self.assertIn("Reference varies", card)
        self.assertIn("Informational", card)
        self.assertNotIn("Elevated", card)


@unittest.skipUnless(HAS_WIDGETS, "ipywidgets/plotly are not installed in this interpreter")
class GlucoseSummaryContractTests(unittest.TestCase):
    @staticmethod
    def _glucose():
        return {
            "period": "Sep 13 – Sep 26, 2026",
            "time_active_percent": 96.7,
            "metrics": {
                "mean_mg_dl": 142.3,
                "gmi_percent": 6.7,
                "cv_percent": 34.1,
            },
            "bands": [
                {"key": "very_low", "percent": 0.2},
                {"key": "low", "percent": 2.1},
                {"key": "target", "percent": 78.4},
                {"key": "high", "percent": 17.3},
                {"key": "very_high", "percent": 2.0},
            ],
        }

    def test_time_in_ranges_has_five_rows_and_no_goal_copy(self):
        html = ui._band_strip_html(self._glucose())
        self.assertEqual(html.count('class="jh-agp-range-row"'), 5)
        for label in ("Very High", "High", "Target", "Low", "Very Low"):
            self.assertIn(label, html)
        self.assertNotIn("jh-goal", html)
        self.assertNotIn("Goal", html)

    def test_time_in_ranges_uses_horizontal_bar_and_keeps_precision_in_rows(self):
        html = ui._band_strip_html(self._glucose())
        self.assertIn('<div class="jh-agp-strip" role="img"', html)
        self.assertIn(
            'aria-label="Time in ranges: Very High 2.0%; High 17.3%; '
            'Target 78.4%; Low 2.1%; Very Low 0.2%"',
            html,
        )
        self.assertEqual(html.count('class="jh-agp-seg'), 5)
        self.assertIn('title="Very High 2.0%"', html)
        self.assertIn('title="Target 78.4%"', html)
        self.assertIn(">2.1%</span>", html)
        self.assertIn(">0.2%</span>", html)
        self.assertIsNone(re.search(r'class="jh-agp-seg[^>]*><span', html))
        self.assertNotIn("Each 1% time in range", html)
        self.assertNotIn("jh-agp-note", html)

    def test_metrics_panel_inlines_five_rows_without_goal_rows(self):
        html = ui._metrics_html(self._glucose())
        self.assertEqual(html.count('class="jh-metric-row"'), 5)
        self.assertIn("Period", html)
        self.assertIn("Time CGM active", html)
        self.assertIn("Average glucose", html)
        self.assertIn("GMI", html)
        self.assertIn("Glucose variability", html)
        self.assertIn("Target &lt;154 mg/dL", html)
        self.assertNotIn("Goal", html)


@unittest.skipUnless(HAS_WIDGETS, "ipywidgets/plotly are not installed in this interpreter")
class SourceBadgeContractTests(unittest.TestCase):
    @staticmethod
    def _view(role: str, sources) -> dict:
        view = DashboardLayoutContractTests._view()
        view["role"] = role
        view["glucose"]["sources"] = sources
        return view

    @staticmethod
    def _rendered_html(dashboard) -> str:
        return "".join(
            widget.value
            for widget in _walk(dashboard)
            if isinstance(widget, ui.widgets.HTML)
            and "<style" not in widget.value
        )

    def test_glucose_summary_and_profile_badges_are_shown_in_both_roles(self):
        for role in ("patient", "practitioner"):
            rendered = self._rendered_html(
                ui.build_dashboard(self._view(role, ["Dexcom Stelo"]))
            )
            self.assertIn("Dexcom Stelo", rendered, role)
            self.assertIn('class="jh-source-badge"', rendered, role)
            self.assertNotIn("CGM source", rendered, role)
            self.assertNotIn("CGM sources", rendered, role)
            self.assertNotIn('class="jh-source"', rendered, role)

    def test_section_head_places_badges_in_a_top_right_control(self):
        head = ui._section_head("Glucose summary", ui._source_badges_widget(["Dexcom Stelo"]))
        self.assertEqual(len(head.children), 2)
        title_widget, badge_widget = head.children
        self.assertNotEqual(title_widget.layout.width, "100%")
        self.assertIn("Glucose summary", title_widget.value)
        self.assertIn("Dexcom Stelo", badge_widget.value)
        self.assertIn('class="jh-source-badge"', badge_widget.value)
        self.assertEqual(head.layout.justify_content, "space-between")
        self.assertIn("wrap", head.layout.flex_flow)

    def test_section_badges_are_omitted_when_no_valid_source(self):
        for sources in (None, [], ["", "   "], [None]):
            head = ui._section_head(
                "Glucose summary", ui._source_badges_widget(sources)
            )
            self.assertEqual(len(head.children), 1, sources)

    def test_source_names_are_distinct_escaped_and_legible(self):
        html = ui._source_badges_html(
            [" Dexcom Stelo ", "Dexcom Stelo", "Oura Ring", "<script>alert(1)</script>"]
        )
        self.assertIn("Dexcom Stelo", html)
        self.assertIn("Oura Ring", html)
        self.assertEqual(html.count("Dexcom Stelo"), 1)
        self.assertEqual(html.count("Oura Ring"), 1)
        self.assertEqual(html.count('class="jh-source-badge"'), 3)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_card_header_shows_distinct_source_badges_to_right_of_title(self):
        card = ui._context_card(
            {
                "label": "Weight",
                "value": "82.5 kg",
                "status": "na",
                "status_label": "Informational",
                "icon": "weight",
                "reference": "Reference varies",
                "source": [" Oura Ring ", "Oura Ring", "CSV Upload"],
            }
        )
        head = card[card.index("jh-card-head") : card.index("jh-card-reading")]
        self.assertIn("Weight", head)
        self.assertIn('class="jh-source-badge"', head)
        self.assertEqual(head.count("Oura Ring"), 1)
        self.assertEqual(head.count("CSV Upload"), 1)
        self.assertNotIn("source:", card.lower())

    def test_auxiliary_card_does_not_fabricate_ehr_or_oura_on_hrv(self):
        card = ui._context_card(
            {
                "label": "HRV (RMSSD)",
                "value": "42 ms",
                "status": "na",
                "status_label": "Informational",
                "icon": "hrv",
                "reference": "Reference varies",
                "source": "CSV Upload",
            }
        )
        self.assertIn("CSV Upload", card)
        self.assertNotIn("EHR", card)
        self.assertNotIn("Oura Ring", card)

    def test_card_omits_badge_when_no_usable_source(self):
        card = ui._context_card(
            {
                "label": "Weight",
                "value": "82.5 kg",
                "status": "na",
                "status_label": "Informational",
                "icon": "weight",
                "reference": "Reference varies",
                "source": "",
            }
        )
        self.assertNotIn("jh-source-badge", card)

    def test_medication_cards_do_not_invent_sources(self):
        rendered = self._rendered_html(
            ui._medication_section(
                {
                    "medications": [],
                    "treatment_options_under_review": True,
                }
            )
        )
        self.assertNotIn('class="jh-source-badge"', rendered)

    def test_trace_header_attributes_each_available_layer_individually(self):
        html = ui._trace_sources_html(
            {
                "sources": {
                    "glucose": ["Dexcom Stelo"],
                    "activity": ["Oura Ring"],
                    "sleep": ["Oura Ring"],
                    "meals": ["CSV Upload"],
                }
            }
        )
        self.assertIn("Glucose", html)
        self.assertIn("Dexcom Stelo", html)
        self.assertIn("Activity", html)
        self.assertIn("Oura Ring", html)
        self.assertIn("Sleep stages", html)
        self.assertIn("Meals", html)
        self.assertIn("CSV Upload", html)
        self.assertIn('class="jh-trace-source"', html)
        self.assertEqual(html.count("Oura Ring"), 2)

    def test_trace_header_omits_absent_optional_layers(self):
        html = ui._trace_sources_html(
            {
                "sources": {
                    "glucose": ["Dexcom Stelo"],
                    "activity": [],
                    "sleep": [],
                    "meals": [],
                }
            }
        )
        self.assertIn("Glucose", html)
        self.assertIn("Dexcom Stelo", html)
        self.assertNotIn("Activity", html)
        self.assertNotIn("Sleep", html)
        self.assertNotIn("Meals", html)

    def test_trace_source_values_are_escaped(self):
        html = ui._trace_sources_html(
            {
                "sources": {
                    "glucose": ["<b>Dexcom</b>"],
                }
            }
        )
        self.assertNotIn("<b>Dexcom</b>", html)
        self.assertIn("&lt;b&gt;Dexcom&lt;/b&gt;", html)


@unittest.skipUnless(HAS_WIDGETS, "ipywidgets/plotly are not installed in this interpreter")
class OptionalSectionContractTests(unittest.TestCase):
    def test_family_history_is_not_referenced_in_ui_source(self):
        source = UI_PATH.read_text()
        self.assertNotIn("_family_history_panel", source)
        self.assertNotIn("family_history", source)
        self.assertNotIn("Family history", source)

    def test_context_section_is_omitted_when_there_are_no_cards(self):
        dashboard = ui.build_dashboard(self._view_with_empty_context())
        rendered = "".join(
            widget.value
            for widget in _walk(dashboard)
            if isinstance(widget, ui.widgets.HTML)
            and getattr(widget, "value", "")
            and "<style" not in widget.value
        )
        self.assertNotIn("Labs and vitals", rendered)
        self.assertNotIn('<div class="jh-lab-grid">', rendered)

    @staticmethod
    def _view_with_empty_context() -> dict:
        return {
            "role": "practitioner",
            "heading": "Hi Dr. Kishore",
            "patient": {
                "name": "Alex K.",
                "initials": "AK",
                "facts": ["38 years · male", "MRN 40032"],
            },
            "context_cards": [],
            "medications": [],
            "treatment_options_under_review": True,
            "glucose": {
                "period": "Sep 13 – Sep 26, 2026",
                "time_active_percent": 96.7,
                "metrics": {
                    "mean_mg_dl": 142.3,
                    "gmi_percent": 6.7,
                    "cv_percent": 34.1,
                },
                "bands": [
                    {"key": "very_high", "percent": 2.0},
                    {"key": "high", "percent": 17.3},
                    {"key": "target", "percent": 78.4},
                    {"key": "low", "percent": 2.1},
                    {"key": "very_low", "percent": 0.2},
                ],
                "percentiles": [],
            },
            "explorer": {
                "glucose": pd.DataFrame(),
                "meals": pd.DataFrame(),
                "activity": pd.DataFrame(),
                "sleep": pd.DataFrame(),
            },
        }

    def test_glucose_trace_note_does_not_claim_missing_meals(self):
        explorer = {
            "glucose": pd.DataFrame(
                {
                    "recorded_at": [datetime(2026, 10, 1, 8, 0)],
                    "mg_dl": [110.0],
                }
            ),
            "meals": pd.DataFrame(),
            "activity": pd.DataFrame(),
            "sleep": pd.DataFrame(),
        }
        section = ui._trace_section({"explorer": explorer})
        rendered = "".join(
            widget.value for widget in _walk(section) if isinstance(widget, ui.widgets.HTML)
        )
        self.assertNotIn("Meals", rendered)
        self.assertNotIn("meals", rendered)


if __name__ == "__main__":
    unittest.main()
