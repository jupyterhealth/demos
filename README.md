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

### CGM demo parameters

- `JHE_STUDY_ID`: study ID (default `30014`).
- `JHE_FHIR_SOURCE_ID`: auxiliary-record source ID (default `90009`).
- `JHE_AUXILIARY_SYSTEM`: auxiliary-record coding system (default `urn:jupyterhealth:synthetic:alex-k:2026`).
- `CGM_SESSION_GAP_HOURS`: gap separating CGM recording periods (default `24`).
- `DEMO_PRACTITIONER_LAST_NAME`: clinician greeting (default `Kishore`).
- `SHOW_SCRIPTED_CHAT`: show demo chat (default `true`; set `false` to hide).
- `JHE_VIEW`: `patient` or `practitioner` for local review; the URL's `?view=` takes precedence.

## Researcher views

These open in JupyterLab, so you can read and run the code:

- [researcher view for blood pressure](https://jupyter-health.2i2c.cloud/hub/user-redirect/git-pull?repo=https%3A%2F%2Fgithub.com%2Fjupyterhealth%2Fdemos&urlpath=lab%2Ftree%2Fdemos%2Fdashboards%2Fresearcher-view.ipynb&branch=main)
- [researcher view for cgm](https://jupyter-health.2i2c.cloud/hub/user-redirect/git-pull?repo=https%3A%2F%2Fgithub.com%2Fjupyterhealth%2Fdemos&urlpath=lab%2Ftree%2Fdemos%2Fdashboards%2Fresearcher-view-cgm.ipynb&branch=main)

## SMART app launch

These require medplum access:

- [BP demo via SMART](https://app.medplum.com/Patient/01961612-dbdc-759b-b885-f55117556bb6/apps) (click "JHE BP Demo")
- [CGM demo via SMART](https://app.medplum.com/Patient/019615e3-3c8a-7479-a8b7-823cee2cebfb/apps) (click "JHE CGM Demo")
