# Changelog

## Unreleased

- Link the central current and historical OKF standards register and public bundle catalogue.
- Migrate the generated Hansard Markdown to the pinned OKF 0.3 specification. Keep directory indexes outside the semantic concept graph and retain the Reader’s navigation route.
- Publish Markdown entry points, a machine-readable directory and `llms.txt` for the week and November views. Add a demo prompt and direct links to source evidence, the companion, graph and timeline.
- Lead with the Railways Bill in the AI guide and companion. Label the Microsoft 365 example as a Commons statement about the outage.
- Add the November publication workflow and contribution-level history views to the source repository. The build reuses previously verified archive partitions when their scope is unchanged.
- Allow new November publication attempts to stage on ExtSSD-Data while retaining existing checkpoints and published assets.
- Require the read-only `okf-hansard-ci` check for `main`. It runs locked Python tests and browser-script syntax checks without source acquisition or publication.
