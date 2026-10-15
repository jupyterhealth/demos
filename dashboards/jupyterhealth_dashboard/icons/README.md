# Vendored Tabler icons

`icons.py` resolves the semantic keys used by the dashboard to the official
Tabler SVG files vendored in this directory. The icons were sourced from the
`tabler/tabler-icons` repository, use the 24x24 outline/stroke style, and are
covered by the adjacent `LICENSE` file. No emoji, CDN, or remote asset is used.
If a packaged asset is unexpectedly missing, `render_icon` falls back to an
empty, text-safe slot and the adjacent visible label still carries the meaning.

The vendored MIT-licensed files are:

- `tabler-walk.svg`
- `tabler-sparkles.svg`
- `tabler-body-scan.svg`
- `tabler-heart-rate-monitor.svg`
- `tabler-droplet.svg`
- `tabler-test-pipe.svg`
- `tabler-heartbeat.svg`
- `tabler-ruler.svg`
- `tabler-wave-sine.svg`
- `tabler-tools-kitchen-2.svg`
- `tabler-messages.svg`
- `tabler-pill.svg`
- `tabler-notes.svg`
- `tabler-x.svg`
- `tabler-chevron-down.svg`
- `tabler-send.svg`
- `tabler-alert-triangle.svg`
- `tabler-circle-check.svg`
- `tabler-arrow-down-circle.svg`
- `tabler-weight.svg`

Tabler Icons are MIT licensed. Keep `LICENSE` beside the vendored SVG files.
`tabler-arrow-down-circle.svg` is the local semantic filename for the upstream
`circle-arrow-down.svg` asset; the remaining local filenames mirror upstream.
