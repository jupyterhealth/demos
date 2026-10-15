# JupyterHealth demos

Demo notebooks to be run on the Berkeley Demo JupyterHealth deployment.
These notebooks are for running on our demonstration deployment, and contain code specific to our deployment.
They are publicly available for reference, but are not meant to be functional outside our own demo environment.

The tutorial, dashboard and researcher view links below are [nbgitpuller](https://nbgitpuller.readthedocs.io/en/latest/link.html) links:
clicking one takes you to the Berkeley Demo Hub, copies this repo into your home directory, and opens the notebook.

## Tutorial

New to JupyterHealth? Start with the step-by-step tutorial:

- [Tutorial: plot a patient's blood pressure](https://jupyter-health.2i2c.cloud/hub/user-redirect/git-pull?repo=https%3A%2F%2Fgithub.com%2Fjupyterhealth%2Fdemos&urlpath=lab%2Ftree%2Fdemos%2Ftutorials%2Fgetting-started-blood-pressure.ipynb&branch=main)

You'll need an account on the Berkeley Demo JupyterHealth Exchange. If you don't have one yet, see [Sign up for the Exchange](https://docs.jupyterhealth.org/hub/sign-up/).

## Dashboards

These open in Voilà, which shows the dashboard without the code:

- [sample charts (BP demo)](https://jupyter-health.2i2c.cloud/hub/user-redirect/git-pull?repo=https%3A%2F%2Fgithub.com%2Fjupyterhealth%2Fdemos&urlpath=voila%2Frender%2Fdemos%2Fdashboards%2Fsample-charts.ipynb&branch=main)

- [CGM Demo](https://jupyter-health.2i2c.cloud/hub/user-redirect/git-pull?repo=https%3A%2F%2Fgithub.com%2Fjupyterhealth%2Fdemos&urlpath=voila%2Frender%2Fdemos%2Fdashboards%2Fcgm-demo.ipynb&branch=main)

- [CGM Demo (patient view)](https://jupyter-health.2i2c.cloud/hub/user-redirect/git-pull?repo=https%3A%2F%2Fgithub.com%2Fjupyterhealth%2Fdemos&urlpath=voila%2Frender%2Fdemos%2Fdashboards%2Fcgm-demo.ipynb%3Fview%3Dpatient&branch=main)

### CGM Demo configuration

The CGM demo shows one full, automatically detected CGM recording period rather
than a previous/follow-up comparison. Add `?view=patient` to show the
patient-oriented greeting (and, when enabled, the patient chat script); omit it
(or use `?view=practitioner`) for the default clinician view.

- `JHE_STUDY_ID` overrides the local `30014` demo-study fallback.
- `CGM_SESSION_GAP_HOURS` sets the gap that separates contiguous CGM periods
  (default `24`).
- `JHE_FHIR_SOURCE_ID` sets the source id used for auxiliary records (default
  `90009`).
- `JHE_AUXILIARY_SYSTEM` sets the coding system used for auxiliary records (default
  `urn:jupyterhealth:synthetic:alex-k:2026`).
- `DEMO_PRACTITIONER_LAST_NAME` overrides the scripted practitioner greeting
  (default `Kishore`; the greeting is intentionally not tied to the
  authenticated user's surname).
- `JHE_VIEW` forces `patient` or `practitioner` for deterministic local review
  when no `?view=` query is present; the query remains authoritative on the
  Berkeley deployment.
- `SHOW_SCRIPTED_CHAT` enables the deterministic demo chat (default `false`).
  When enabled it appears as a closed-by-default floating launcher that opens a
  bounded scripted panel. There is no LLM, API key, or network dependency in
  that chat. The patient role exposes a typed composer; the practitioner role
  is a report-delivery feed with no composer.

Family history is intentionally not requested or rendered in the CGM demo; the
dashboard keeps only the bounded researcher previews behind the standard Voilà
guard when it is opened in JupyterLab.

The dashboard intentionally has no blood-pressure chart. The medication panel
shows the current honest state (“No active medications” and “Treatment options
under review”) while leaving room for future structured medication records.
Official MIT-licensed Tabler SVGs are vendored locally under
`dashboards/jupyterhealth_dashboard/icons/`. The practitioner view is a
report-delivery feed (no free-text composer): its opening message shows “A
report is ready for you.” followed by the "UC HTN Way 3.0 Report" link to the
locally served generic hypertension algorithm reference at
`dashboards/jupyterhealth_dashboard/assets/uc-way-htn-algorithm.png`. That PNG
is served by Voilà's default `file_allowlist`, never from a remote URL, and is
not presented as a patient-specific clinical result or given any additional
subtitle. The patient chat keeps the sushi comparison, HbA1c, biomarker, and
reference-range scripts and has no Med-BEAM referral or appointment flow.

## Researcher views

These open in JupyterLab, so you can read and run the code:

- [researcher view for blood pressure](https://jupyter-health.2i2c.cloud/hub/user-redirect/git-pull?repo=https%3A%2F%2Fgithub.com%2Fjupyterhealth%2Fdemos&urlpath=lab%2Ftree%2Fdemos%2Fdashboards%2Fresearcher-view.ipynb&branch=main)
- [researcher view for cgm](https://jupyter-health.2i2c.cloud/hub/user-redirect/git-pull?repo=https%3A%2F%2Fgithub.com%2Fjupyterhealth%2Fdemos&urlpath=lab%2Ftree%2Fdemos%2Fdashboards%2Fresearcher-view-cgm.ipynb&branch=main)

## SMART app launch

These require medplum access:

- [BP demo via SMART](https://app.medplum.com/Patient/01961612-dbdc-759b-b885-f55117556bb6/apps) (click "JHE BP Demo")
- [CGM demo via SMART](https://app.medplum.com/Patient/019615e3-3c8a-7479-a8b7-823cee2cebfb/apps) (click "JHE CGM Demo")
