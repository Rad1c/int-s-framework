# Playbooks

Playbooks define repeatable workflows for common outcomes. They coordinate steps and may reference agents, skills, templates, or tools.

Use the narrowest matching playbook:

- `implement-feature.md` — deliver a feature;
- `debug.md` — investigate and fix unexpected behavior;
- `investigate-api-failure.md` — diagnose an API returning `5xx`;
- `pr-review.md` — review a pull request;
- `local-smoke-test.md` — exercise a framework change end to end, with or without a broker;
- `release-version.md` — publish a version tag consumers can pin.

Run `sync-registry` after adding or removing a playbook.
