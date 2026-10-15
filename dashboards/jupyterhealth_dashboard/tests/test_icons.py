"""Offline contracts for the local icon registry."""

from __future__ import annotations

import unittest

from jupyterhealth_dashboard import icons


class IconRenderingTests(unittest.TestCase):
    def test_vendored_icon_renders_inline_without_remote_or_emoji_fallback(self):
        rendered = icons.render_icon("activity", label="Activity")
        self.assertIn("<svg", rendered)
        self.assertNotIn("<img", rendered)
        self.assertNotIn('href="', rendered)
        self.assertNotIn("xlink:href", rendered)

    def test_unknown_icon_has_empty_fallback(self):
        self.assertEqual(icons.render_icon("not-a-real-icon", label="Missing"), "")

    def test_existing_svg_is_rendered_inline_without_remote_reference(self):
        svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path d="M1 1"/></svg>'
        rendered = icons.render_icon_svg(svg, label="Activity")
        self.assertIn("<svg", rendered)
        self.assertIn('class="jh-icon"', rendered)
        self.assertNotIn("<img", rendered)
        self.assertNotIn("https://", rendered)
        self.assertNotIn('src="', rendered)
        self.assertNotIn('href="', rendered)
        self.assertNotIn("xlink:href", rendered)
        self.assertNotIn("url(", rendered)

    def test_blank_svg_is_still_an_empty_slot(self):
        self.assertEqual(icons.render_icon_svg("   ", label="Activity"), "")

    def test_icon_background_is_local_data_uri(self):
        background = icons.icon_background("chat", color="#ffffff")
        self.assertIn("data:image/svg+xml", background)
        self.assertNotIn("http://", background)
        self.assertNotIn("https://", background)

    def test_unknown_icon_background_is_empty(self):
        self.assertEqual(icons.icon_background("not-a-real-icon"), "")


if __name__ == "__main__":
    unittest.main()
