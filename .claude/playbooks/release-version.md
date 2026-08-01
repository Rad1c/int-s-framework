# Release a Framework Version

Use this playbook to publish a framework version that consumer services can pin. Consumers install
from a Git tag, so **the tag is the release** — there is no package registry to correct afterwards.

1. Confirm `main` is clean and up to date, and that the change set is complete.
2. Run `ruff check .` and `pytest`. Both must pass before anything is tagged.
3. Decide the version against the published contract — the handler signature, the envelope shape,
   common setting names, and the audit method signatures. A change to any of them is a minor bump
   and a migration note; everything else is a patch.
4. Confirm the three-part settings contract is consistent: `settings.py`, `.env.example`, and the
   environment table in `README.md`.
5. Update `README.md` and `skills/build-integration-service/SKILL.md` when the consumer-facing
   contract moved.
6. Bump `version` in `pyproject.toml`, then commit and push that change.
7. Create and push `vX.Y.Z` pointing at that commit.
8. Verify the tag installs: `pip install "integration-service-framework @ git+<repo-url>@vX.Y.Z"`
   into a clean environment. VCS installs need `git` present — in Docker that means the builder
   stage.
9. Report the new tag, what changed, and the migration steps a consumer must take.

Never move or delete a published tag: a consumer that already installed it would silently get
different code from the same pin. Ship a new patch version instead.

`git push` is blocked by the PreToolUse hook in `.claude/settings.json`, so steps 6 and 7 end with
the agent staging the commit and naming the exact push and tag commands for the user to run.
