# Decisions

Choices between real alternatives, and what was rejected. Append a new entry at the bottom before
moving on from the decision — a rationale reconstructed later is a guess.

```
### YYYY-MM-DD — the decision, stated as an action
**Why:** what made this the better option here
**Rejected:** the alternatives, and what ruled each out
```

---

### 2026-07-31 — Move the whole scaffold under `.claude/`, with only `CLAUDE.md` and `README.md` at the root

**Why:** Claude Code loads `CLAUDE.md` every turn and discovers `.claude/skills/` and
`.claude/agents/` on its own. Before this, `skills/` and `agents/` sat at the repo root where
nothing loaded them — the catalogue existed but no agent could reach it. Keeping everything under
`.claude/` also means dropping the scaffold into a real project adds two root-level files instead
of seven directories.
**Rejected:** Root `skills/` plus a symlink into `.claude/` — needs developer mode or admin on
Windows. Leaving the catalogue as documentation the agent reads only when told — that is the state
that made it inert in the first place.

### 2026-07-31 — Merge `AGENTS.md` into `CLAUDE.md` and delete it

**Why:** The two would have held the same working rules, and Claude Code only auto-loads
`CLAUDE.md`. One file, one source of truth, no import indirection.
**Rejected:** Keeping `AGENTS.md` with `CLAUDE.md` importing it via `@` — two files to keep in
step for no gain while Claude Code is the only tool in use. A root `AGENTS.md` pointing at
`CLAUDE.md` is a two-line addition if Codex or Cursor is ever added.

### 2026-07-31 — Keep three subagents (reviewer, security, tester), drop the other seven

**Why:** A subagent earns its permanent context cost only when it needs isolated context or an
adversarial lens. Review, security, and verification qualify — each is a fresh pair of eyes on work
already done. `orchestrator`, `business-analyst`, `backend`, `frontend`, `devops`, and `database`
described what the main loop and `general-purpose` already do, and `architect` overlapped the
built-in `Plan` agent.
**Rejected:** Converting all ten — ten descriptions in the context window every turn, most of them
restating default behavior.

### 2026-07-31 — Delete `code-review`, `diagnosing-bugs`, and `resolving-merge-conflicts`

**Why:** All three were copied from a specific .NET codebase and were built around its specifics
(NHibernate mappings, `.csproj` registration, Azure DevOps PR history) while referencing four
skills that do not exist here. In a scaffold that must stay technology-agnostic, they would have
sent the agent looking for `.csproj` files in projects that have none.
**Rejected:** Genericizing them — with the domain specifics removed, `code-review` and
`resolving-merge-conflicts` reduce to process the model already follows. Rewrite from scratch if a
project turns out to need one.

### 2026-07-31 — Do not add a `Stop` hook reminding the agent to capture knowledge

**Why:** It was planned, then dropped once the mechanics were checked. A `Stop` hook that exits 0
writes to the transcript, which nobody reads mid-session; one that returns `decision: block` forces
the agent to keep going and risks a loop. Either way it would repeat the capture triggers that
`CLAUDE.md` already puts in context on every turn — the "no-op" failure mode from
`writing-great-skills`, paid for with a hook.
**Rejected:** A blocking `Stop` hook guarded by a once-per-session marker file — a script plus
state on disk to restate a rule the agent is already reading. Revisit only if capture is observed
to fail in practice, and then fix the trigger wording in `CLAUDE.md` first.

### 2026-07-31 — Drop the `metrics` block from the tool manifest

**Why:** `times_used`, `success_rate`, `average_duration_seconds`, and `last_used` were required by
`validate-tools`, and nothing ever wrote them — every manifest carried four permanently null
fields. `tools/README.md` already states that metrics must describe observed use, not guesses.
**Rejected:** Keeping them for a future telemetry hook. Add the fields back with the hook that
populates them.

### 2026-07-30 — Accept both `RABBITMQ_USER` and `RABBITMQ_USERNAME`

**Why:** The services being consolidated onto the framework already disagreed: Betbox deployments
set `RABBITMQ_USERNAME`, internal backoffice deployments set `RABBITMQ_USER`. `AliasChoices` on one
field lets both fleets adopt the framework without an environment migration
([settings.py](../../src/integration_framework/settings.py)).
**Rejected:** Picking one name and rewriting the other fleet's deployment configuration — a change
outside this repository, on machines the framework release cannot reach.

### 2026-07-30 — Ship audit logging with no enable/disable flag

**Why:** The repository is best-effort end to end — no request ID, no database, or a failed write
all degrade to a no-op that logs. A flag would only add a second way to express "no audit rows",
and a service that silently stops auditing because of a stale environment variable is worse than
one that logs a connection failure every `DB_RECONNECT_INTERVAL`.
**Rejected:** An `AUDIT_ENABLED` variable defaulting to true — one more line in every consumer's
`.env` for a state the code already reaches on its own.

### 2026-07-30 — Drop and rebuild the whole pool when a connection goes bad

**Why:** After a PostgreSQL restart or network drop, every pooled connection is dead, so returning
one to the pool hands the next caller a guaranteed failure. `InterfaceError`, `OperationalError`,
and a rollback that itself raises `psycopg2.Error` all mark the pool unusable; it is closed and not
rebuilt until `DB_RECONNECT_INTERVAL` has passed, which also caps reconnect attempts while the
database is down.
**Rejected:** Returning the connection and letting the next call fail — the failure repeats per
message. Catching bare `Exception` around the rollback, which was the state before commit
`49efda6`: it swallowed programming errors as if they were connection failures.

### 2026-08-01 — Adapt the scaffold's root `CLAUDE.md` into a project one rather than layering a second file

**Why:** The scaffold shipped with a generic `CLAUDE.md` whose own instructions say to merge it
into a project's file. Claude Code auto-loads exactly one root `CLAUDE.md`, and the project rules
that matter most here — the ownership boundary, the three-places-per-setting rule, what ripples
into consumers — belong in front of the agent every turn, not behind a pointer.
**Rejected:** Keeping the scaffold text untouched and adding project rules to
`.claude/knowledge/` only — knowledge is read on demand, so the boundary rule would be consulted
after the wrong code was already written.
