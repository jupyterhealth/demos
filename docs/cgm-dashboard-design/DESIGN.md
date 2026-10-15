# JupyterHealth CGM Dashboard — Design Direction

## Design invocation ledger

- **DESIGN MODE:** clinical operational dashboard
- **LOADED:** `digital-design-director` — hierarchy, compact clinical cards, interaction and accessibility gates
- **LOADED:** `design-loop` — reference teardown, independent rendered critics, iterative pass/fail loop
- **LOADED:** `laude-dashboard-demo` — notebook architecture, one-period role-aware dashboard, scripted-demo constraints
- **LOADED:** `cgm-sandbox-development` — cross-modal data consistency and meal/sleep non-overlap requirements
- **LOADED:** `web-development-browser-qa` — live Voilà rendering and state/role verification
- **CODER CONTEXT:** this document, `bar.md`, the five loaded skill files, current notebook/modules/tests, canonical Alex K. dataset, and supplied reference screenshots
- **CRITIC GATES:** actual practitioner and patient renders; desktop and compact-width views; closed/open chat states; simultaneous Brief/System/Craft pass

## Design read

A clinician/patient CGM review surface for fast interpretation, using a compact, trustworthy healthcare-dashboard language that prioritizes current values, the glucose trace, and a realistic simulated assistant without competing with the clinical evidence.

## Strategy

- Visual variance: **3/10**
- Motion intensity: **2/10**
- Information density: **7/10**
- Asset dependence: **2/10**
- Brand fidelity: **7/10**

**Visual thesis:** A restrained neutral clinical canvas with compact white metric tiles, thin semantic accent borders, tabular numeric values, quiet reference ranges, a clean event-driven glucose trace, and a polished floating assistant that appears only when summoned.

## Scope

One notebook with two verified roles:

- Practitioner: `Hi Dr. Kishore`
- Patient: `Hi Alex`

Both use only the latest CGM recording period. There is no previous-period selector, comparison state, or previous-recording section.

## Required changes

1. Remove the redundant subtitle/eyebrow copy about “continuous glucose monitor · latest recording” and reviewing the latest CGM.
1. Make metric cards smaller, more styled, and easier to scan.
1. Add restrained semantic border color without relying on color alone.
1. Put each small, light-gray clinical reference range on the same reading line, immediately to the right of the primary value, wrapping only when necessary.
1. Standardize abnormal statuses to **Elevated**.
1. Remove meal-name labels from the chart surface; show the full meal name and details in hover tooltips.
1. Enforce and test that no meal event overlaps a sleep interval.
1. Keep the chat as a circular viewport-fixed launcher at the bottom-right; it must not move with the dashboard’s internal scroll container.
1. The floating chat includes an iCKM Advisor header, close control, scrollable message history, centered controls, realistic user/assistant turns, staged thinking/tool states, and — for the patient role only — a persistent composer. No suggested-prompt buttons.
1. Use generic assistant copy rather than pre-prompting sushi. The patient’s record-derived sushi comparison ends naturally with its data visualization; Med-BEAM/appointment/referral input is not routed or advertised in the patient role.
1. Keep the synthetic-record disclosure quiet but truthful. The scripted assistant cannot claim a real API transmission, booking, cancellation, or care-team notification. If two comparable sushi meals are unavailable, show an unavailable result rather than fabricated fallback meals.
1. Recompose the AGP summary so Time in ranges uses its full panel, removes the per-range Goal column, and aligns proportionally with a denser Glucose metrics panel.
1. Verify patient/practitioner role selection from the actual rendered heading, not from URL assumptions.
1. Make supported capabilities visible before the first patient prompt without pre-filling. Describe only deterministic actions the current role can actually complete; the clinician opening bubble shows `A report is ready for you.` followed by the UC HTN Way 3.0 link, with no additional visible caption.
1. The URL query `?view=patient` or `?view=practitioner` controls the same notebook’s `view_name`; a misspelling such as `paitent` fails closed to practitioner. Both the 24-hour percentile profile and the cross-modal glucose trace fill the available section width.
1. Color the 5th–95th percentile envelope by **actual glucose value**, not percentile rank: dark red below 54, red from 54 to below 70, green at 70–180, yellow above 180 to 250, and orange above 250 mg/dL. Clip at exact crossings; never force warm tails into an in-range record. Keep the green median and the 70/180 green and 54 red guides, but omit 5th/95th and 25th/75th boundary strokes and their legend items. Use a taller profile plot and a horizontal legend below it for the median and only glucose ranges present in the data.
1. Remove family history from the dashboard and notebook entirely: no auxiliary family-history code request, `valueString` parser, dashboard view key, UI panel, or CSS style. The canonical synthetic dataset and hosted Exchange may still contain the record; this demo simply does not request or render it.
1. Keep every Exchange retrieval, decode, pandas normalization, CGM period selection, glucose metric, and numeric meal-trace calculation in the notebook. The package owns chat presentation, wording, and interactive widgets, so the notebook only prepares numeric meal traces and hands the finished `analysis` to the package.
1. After processing, print bounded researcher-readable previews for the selected CGM recording and each available optional frame (`shape`, column names, and a small `head`) behind the existing `VOILA_REQUEST_URL` guard. Previews must not emit thousands of rows or any patient-sensitive token.
1. Handle missing optional data without invented values: CGM is required, while empty meals produce no meal overlay or meal-specific trace claim, missing labs/vitals do not render an empty card list, and empty steps/sleep/heart-rate frames simply have no bars. The patient meal comparison returns its honest unavailable answer when required data are missing; the chat flag remains the only control over whether the launcher is rendered.
1. Show compact top-right source badges in the section header for the Glucose summary and Glucose profile, and per-layer modality + source badges in the Glucose trace header. Each labs/vitals card shows its selected record's source in the card header right. The name(s) come from the selected record's own source/device values (trimmed, de-duplicated, blanks dropped), never a hardcoded brand, the FHIR Source ID, the local fallback `patient_source`, or an invented EHR provenance. When several distinct names exist, list them all; omit a badge entirely when none remain. Medication cards stay source-free because they are a hardcoded empty demo state. All values are escaped and wrap cleanly at narrow widths.

## Interaction model

### Floating chat

- Closed by default with a circular bottom-right Tabler chat icon button fixed to the viewport.
- Opens a roughly 620 px desktop panel above the launcher on the right (the two-meal comparison visualization needs the wider bubble).
- Header identifies the iCKM Advisor without “simulation” labels; includes close/minimize control.
- Conversation area scrolls independently.
- Composer remains fixed at the bottom of the panel and all button labels/icons are optically centered.
- Opening copy and placeholder are generic and do not mention sushi. A compact patient capability panel states what the current deterministic role can do, without suggested-prompt buttons.
- Supported input is matched to deterministic scripted branches. Unsupported input receives a concise capability-limitation response rather than pretending a live model answered.
- The sushi branch compares two meals from the selected synthetic CGM record (name, study-local timestamp, glucose trace with step activity, peak rise, and iAUC) and ends there; no referral or appointment follows. The clinician feed has no composer and no algorithm-reference caption: the opening bubble is the report-ready sentence followed by the UC HTN Way 3.0 link. A hidden double-click on the chat header appends the synthetic Med-BEAM report takeaways directly as a new assistant message once, without a second button or any claim of a real clinical action.
- Thinking states enumerate concrete work: locating meals, isolating glucose windows, checking activity, comparing responses, and preparing the result.
- On compact widths, the panel becomes a safe inset sheet without horizontal overflow.

### CGM trace

- No permanent meal text over the plot.
- Meal markers remain visually discoverable and keyboard/hover accessible.
- Tooltip includes complete meal name, timestamp, macros if available, and associated activity context.
- Sleep and meal events are data-consistent before rendering; visual overlap is not merely hidden.

## Accessibility and QA

- Text/icon/status cues accompany semantic colors.
- Reference ranges remain readable at normal zoom and meet contrast requirements for secondary text.
- Launcher and chat controls have accessible names, visible focus, and at least 40×40 px targets.
- Keyboard users can open, use, and close chat; focus returns to the launcher.
- Verify desktop and compact widths, chat closed/open/thinking/result states, both roles, plot hover content, document overflow, and first-party console errors.
