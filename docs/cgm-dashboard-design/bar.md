# Visual Bar — JupyterHealth CGM Dashboard

The supplied healthcare-dashboard and assistant screenshots establish these visually checkable mechanisms:

1. **The greeting is the only introductory headline.** The page moves directly from `Hi Dr. Kishore` or `Hi Alex` into the patient summary and clinical content; no eyebrow or explanatory paragraph repeats that this is the latest CGM recording.

2. **Clinical metric tiles are compact and uniform.** Desktop tiles form a disciplined grid with consistent height and padding; the numeric value is the dominant line, while the reference range is visibly smaller, lighter, and adjacent to or immediately below it.

3. **Semantic styling is restrained but unmistakable.** Every tile has a thin neutral border plus a controlled semantic accent; abnormal tiles use the same visible word `Elevated`, and status meaning remains legible without color.

4. **The glucose trace is visually quiet until inspected.** No meal name is permanently printed across the plotting area. Meal markers reveal the full name and relevant details in hover/focus tooltips, leaving the multi-day trace readable at a glance.

5. **The page shows one coherent physiological timeline.** Only the latest recording period appears, and no meal marker falls inside a sleep interval. The timeline does not contain a previous-recording selector or comparison section.

6. **Chat is a summoned overlay, not a dashboard column.** The resting state is one circular fixed launcher button at the bottom right. Opening it produces a professional 380–420 px floating panel with a distinct header, close control, independently scrollable transcript, and fixed composer.

7. **The simulated assistant looks and behaves like a real session.** User and assistant turns are visually distinct; thinking/tool states appear as staged conversation events; the composer accepts the supported scripted prompts; closing restores the launcher; and the patient and practitioner scripts remain visibly different.
