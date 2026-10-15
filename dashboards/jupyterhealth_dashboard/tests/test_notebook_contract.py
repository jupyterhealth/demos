"""Programmatic contracts for the regenerated ``dashboards/cgm-demo.ipynb``."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

NOTEBOOK_PATH = (
    Path(__file__).resolve().parents[3] / "dashboards" / "cgm-demo.ipynb"
)


def _notebook_source() -> str:
    notebook = json.loads(NOTEBOOK_PATH.read_text())
    assert notebook.get("nbformat") == 4, "notebook is not nbformat 4"
    return "\n".join(
        "".join(cell.get("source", [])) for cell in notebook.get("cells", [])
    )


class NotebookViewContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = _notebook_source()

    def test_role_is_resolved_from_voila_request_url_into_view_name(self):
        self.assertIn(
            "view_name = requested_view_name(os.environ.get(\"VOILA_REQUEST_URL\"))",
            self.source,
        )
        self.assertIn('"role": view_name', self.source)

    def test_jhe_view_env_precedence_lives_in_core_not_the_notebook(self):
        self.assertNotIn("JHE_VIEW", self.source)
        self.assertIn("requested_view_name", self.source)

    def test_scripted_chat_is_gated_by_show_scripted_chat(self):
        self.assertIn("SHOW_SCRIPTED_CHAT = scripted_chat_enabled()", self.source)
        self.assertIn('"show_scripted_chat": SHOW_SCRIPTED_CHAT', self.source)
        self.assertIn("if SHOW_SCRIPTED_CHAT:", self.source)

    def test_chat_content_is_role_aware(self):
        self.assertIn("build_chat_data", self.source)
        self.assertIn(
            'dashboard_view["chat"] = build_chat_data(',
            self.source,
        )
        self.assertIn("view_name,", self.source)
        self.assertIn("context_cards,", self.source)

    def test_identity_facts_are_age_gender_mrn_without_date(self):
        self.assertIn('f"{age_years} years · {display_gender}"', self.source)
        self.assertIn('f"MRN {patient[\'id\']}"', self.source)
        self.assertNotIn("date_span", self.source)

    def test_latest_period_uses_genuine_percentile_profile(self):
        self.assertIn("def percentile_profile(recording, step_minutes=15):", self.source)
        self.assertIn('"percentiles": percentile_profile(recording)', self.source)

    def test_cgm_source_line_is_derived_from_the_selected_recording(self):
        self.assertIn('distinct_sources(recording["source"])', self.source)
        self.assertIn('"sources": distinct_sources(recording["source"])', self.source)
        # The device/source label must never be a hardcoded brand or the FHIR
        # ingestion provenance.
        self.assertNotIn("Dexcom Stelo", self.source)

    def test_observation_source_is_derived_from_device_display_without_hardcoded_names(self):
        self.assertIn("def observation_source(resource):", self.source)
        self.assertIn('"source": observation_source(resource)', self.source)
        self.assertIn(
            'columns=["code", "recorded_at", "value", "unit", "source"]',
            self.source,
        )
        self.assertNotIn('provenance.get("source_name") or "Exchange"', self.source)
        self.assertNotIn("Oura Ring", self.source)
        self.assertNotIn("CareX", self.source)
        self.assertNotIn("EHR", self.source)

    def test_latest_card_selection_propagates_sources_without_inventing_values(self):
        self.assertIn(
            'list(zip(rows["recorded_at"], rows["value"], rows["source"]))',
            self.source,
        )
        self.assertIn(
            'list(zip(weights["recorded_at"], weights["value"], weights["source"]))',
            self.source,
        )
        self.assertIn(
            'list(zip(heights["recorded_at"], heights["value"], heights["source"]))',
            self.source,
        )
        self.assertIn('"source": source', self.source)

    def test_trace_explorer_sources_are_captured_before_aggregation(self):
        self.assertIn("explorer_sources = {", self.source)
        self.assertIn('"glucose": distinct_sources(recording["source"])', self.source)
        self.assertIn('"activity": distinct_sources(steps["source"])', self.source)
        self.assertIn('"meals": distinct_sources(meals["source"])', self.source)
        self.assertIn('"sleep": distinct_sources(sleep["source"])', self.source)
        self.assertIn('"sources": explorer_sources', self.source)

    def test_visible_report_naming_has_no_algorithm_caption(self):
        self.assertIn("build_chat_data", self.source)
        self.assertNotIn("CLINICAL_ALGORITHM_REFERENCE_CUE", self.source)
        self.assertNotIn('"cue"', self.source)
        self.assertNotIn("Open Med-BEAM report", self.source)

    def test_family_history_is_removed_from_notebook(self):
        for token in (
            "family_history_values",
            '"family_history"',
            "family-history-father-heart-attack",
            "valueString",
        ):
            self.assertNotIn(token, self.source)

    def test_meal_timestamps_are_propagated_from_occurred_at(self):
        self.assertIn("meal_timestamp_label", self.source)
        self.assertIn('"timestamp": meal_timestamp_label(row.occurred_at)', self.source)

    def test_imports_are_grouped_and_not_duplicated(self):
        self.assertEqual(self.source.count("from IPython.display import display"), 1)
        self.assertEqual(self.source.count("import pandas as pd"), 1)
        self.assertEqual(self.source.count("from jupyterhealth_client import"), 1)
        self.assertEqual(self.source.count("from zoneinfo import ZoneInfo"), 1)
        self.assertIn(
            "from zoneinfo import ZoneInfo\n\nimport pandas as pd",
            self.source,
        )
        self.assertLess(
            self.source.index("import pandas as pd"),
            self.source.index("from jupyterhealth_client import"),
        )

    def test_unnecessary_auxiliary_comments_are_absent(self):
        self.assertNotIn(
            "The auxiliary clinical context is small, so fetch each exact synthetic code directly.",
            self.source,
        )
        self.assertNotIn(
            "The synthetic system and FHIR source are configurable for other studies.",
            self.source,
        )

    def test_bounded_researcher_previews_are_present(self):
        for token in (
            "VOILA_REQUEST_URL",
            'head(3)',
            'print("columns:", list(',
            "preview(",
            'preview(recording, "selected CGM recording")',
            'preview(meals, "meals")',
            'preview(steps, "steps")',
            'preview(sleep, "sleep")',
            'preview(heart_rate, "heart rate")',
            'preview(blood_pressure, "blood pressure")',
            'preview(auxiliary, "auxiliary")',
        ):
            self.assertIn(token, self.source)

    def test_chat_content_is_prepared_in_package(self):
        self.assertIn("build_chat_data", self.source)
        self.assertIn(
            'dashboard_view["chat"] = build_chat_data(',
            self.source,
        )
        self.assertNotIn('if view_name == "patient":', self.source)


if __name__ == "__main__":
    unittest.main()
