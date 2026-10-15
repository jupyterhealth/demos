"""Isolated scheduling contracts for the staged chat playback."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from jupyterhealth_dashboard import core

try:
    from jupyterhealth_dashboard import chat

    HAS_CHAT = True
except Exception:  # pragma: no cover - dependency-specific environment
    HAS_CHAT = False


class FakeScheduler:
    def __init__(self):
        self.calls: list[tuple[float, object]] = []

    def __call__(self, delay: float, callback) -> None:
        self.calls.append((delay, callback))


class SingleSlotCollector:
    def __init__(self):
        self.slot = None
        self.rendered = []
        self.restored = False

    def render(self, html: str) -> None:
        self.slot = html
        self.rendered.append(html)

    def restore(self) -> None:
        self.restored = True


def _patient_chat() -> dict:
    analysis = core.scripted_sushi_fallback()
    return {
        "analysis": analysis,
        "context_cards": [],
        "explanation": analysis["explanation"],
    }


def _patient_plan() -> chat.ChatPlan:
    return chat.build_plan("patient", _patient_chat(), core.PATIENT_CHAT_STARTER)


@unittest.skipUnless(HAS_CHAT, "ipywidgets/plotly are not installed in this interpreter")
class SchedulePlanTests(unittest.TestCase):
    def test_initial_stage_is_rendered_before_any_callback_runs(self):
        plan = _patient_plan()
        scheduler = FakeScheduler()
        collector = SingleSlotCollector()

        chat.schedule_plan(
            plan,
            schedule=scheduler,
            render=collector.render,
            restore=collector.restore,
        )

        self.assertEqual(collector.rendered, [plan.stages[0]])
        self.assertIn("Thinking", collector.slot)
        self.assertIn("jh-chat-stage", collector.slot)
        self.assertEqual(len(scheduler.calls), len(plan.stages))

    def test_callbacks_replace_the_single_slot_in_order_then_install_result(self):
        plan = _patient_plan()
        scheduler = FakeScheduler()
        collector = SingleSlotCollector()

        chat.schedule_plan(
            plan,
            schedule=scheduler,
            render=collector.render,
            restore=collector.restore,
        )

        expected_delays = [1.4 * offset for offset in range(1, len(plan.stages) + 1)]
        self.assertEqual([delay for delay, _ in scheduler.calls], expected_delays)
        for index, (_, callback) in enumerate(scheduler.calls):
            self.assertFalse(collector.restored)
            callback()
            expected = plan.stages[index + 1] if index + 1 < len(plan.stages) else plan.result
            self.assertEqual(collector.slot, expected)

        self.assertTrue(collector.restored)
        self.assertEqual(len(collector.rendered), len(plan.stages) + 1)
        self.assertEqual(collector.rendered[-1], plan.result)
        self.assertNotIn("jh-chat-stage", collector.slot)
        self.assertIn("Sushi dinner (no walk)", collector.slot)

    def test_unsupported_plan_is_immediate_result_and_restore_without_scheduling(self):
        plan = chat.build_plan("patient", {}, "hello there")
        scheduler = FakeScheduler()
        collector = SingleSlotCollector()

        chat.schedule_plan(
            plan,
            schedule=scheduler,
            render=collector.render,
            restore=collector.restore,
        )

        self.assertEqual(scheduler.calls, [])
        self.assertEqual(collector.rendered, [plan.result])
        self.assertTrue(collector.restored)
        self.assertNotIn("jh-chat-stage", collector.slot)


def _find(widget, predicate):
    if predicate(widget):
        return widget
    for child in getattr(widget, "children", ()):
        found = _find(child, predicate)
        if found is not None:
            return found
    return None


@unittest.skipUnless(HAS_CHAT, "ipywidgets/plotly are not installed in this interpreter")
class WidgetSchedulerContractTests(unittest.TestCase):
    @staticmethod
    def _view() -> dict:
        return {
            "role": "patient",
            "show_scripted_chat": True,
            "chat": _patient_chat(),
        }

    @staticmethod
    def _run_callbacks(scheduler, start=0):
        index = start
        while index < len(scheduler.calls):
            _, callback = scheduler.calls[index]
            index += 1
            callback()

    def test_composer_stays_disabled_until_sushi_result_completes(self):
        import ipywidgets as widgets

        scheduler = FakeScheduler()
        with patch.object(chat, "active_scheduler", return_value=scheduler):
            host = chat.scripted_chat_widget(self._view())
        composer = _find(host, lambda widget: isinstance(widget, widgets.Textarea))
        send = _find(
            host,
            lambda widget: isinstance(widget, widgets.Button) and widget.description == "Send",
        )

        composer.value = core.PATIENT_CHAT_STARTER
        send.click()

        self.assertTrue(send.disabled)
        self.assertTrue(composer.disabled)
        self._run_callbacks(scheduler)
        self.assertFalse(send.disabled)
        self.assertFalse(composer.disabled)

    def test_patient_sushi_result_has_no_referral(self):
        import ipywidgets as widgets

        scheduler = FakeScheduler()
        with patch.object(chat, "active_scheduler", return_value=scheduler):
            host = chat.scripted_chat_widget(self._view())
        composer = _find(host, lambda widget: isinstance(widget, widgets.Textarea))
        send = _find(
            host,
            lambda widget: isinstance(widget, widgets.Button) and widget.description == "Send",
        )
        transcript = _find(
            host,
            lambda widget: isinstance(widget, widgets.HTML) and "jh-chat-msg" in widget.value,
        )

        composer.value = core.PATIENT_CHAT_STARTER
        send.click()
        self._run_callbacks(scheduler)

        self.assertIn("Sushi dinner (no walk)", transcript.value)
        self.assertNotIn("jh-chat-referral", transcript.value)
        self.assertNotIn("Med-BEAM", transcript.value)
        self.assertNotIn("Thursday, October 15", transcript.value)
        self.assertNotIn("prototype", transcript.value.lower())


if __name__ == "__main__":
    unittest.main()
