# Gotchas

Non-obvious failures and the surprise that led to them. Append a new entry at the bottom the
moment you find a root cause — not at the end of the task.

```
### YYYY-MM-DD — one-line title
**Surprise:** what looked wrong, and what you expected instead
**Cause:** the actual mechanism
**Fix:** what resolved it, and how to avoid it next time
```

---

### 2026-07-31 — A BOM makes Codex reject a `SKILL.md`

**Surprise:** Two skills written with PowerShell `Set-Content -Encoding utf8` failed to load in Codex
with `missing YAML frontmatter delimited by ---`, even though the first line of each file was `---`.
**Cause:** Windows PowerShell 5.1 writes UTF-8 **with** a BOM. The parser sees `﻿---` on line one
and does not recognise the frontmatter delimiter. The same files render correctly in every editor,
which is what makes it hard to spot.
**Fix:** Write agent-facing files BOM-free: `[System.IO.File]::WriteAllText($path, $text, (New-Object
System.Text.UTF8Encoding($false)))`. `Set-Content`/`Out-File -Encoding utf8` are not safe for this on
PowerShell 5.1. Check an existing file with `[System.IO.File]::ReadAllBytes($path)[0..2]` — `239,187,191`
is a BOM.

### 2026-07-31 — A hand-maintained registry rots before it is ever used

**Surprise:** `registry.yaml` pointed at `README.md`, `memory/README.md`, and `workspace/README.md`.
None of the three had ever existed, and the scaffold had not yet been used on a project.
**Cause:** The index was written by hand and the only validator in the repo, `validate-tools`,
checks `tool.yaml` manifests — it never looks at the index itself.
**Fix:** `sync-registry` generates `registry.yaml` from the tree, so a path can only appear in it
if the file is really there. Run it after adding, moving, promoting, or removing an asset;
`-Check` fails when the committed index has drifted.

### 2026-07-30 — The test dependency is `httpx2`, not `httpx`

**Surprise:** The dev extra pins `httpx2`, which reads like a typo for `httpx` and invites a
"correction" that breaks the suite.
**Cause:** `fastapi.testclient` comes from Starlette, and Starlette 1.x
(`starlette/testclient.py`) tries `import httpx2 as httpx` first, falling back to `httpx` only if
that fails; it errors with "requires the httpx2 package". `httpx2` is the successor package
published by Pydantic — a different distribution, not an alias, and FastAPI itself pulls in neither
unless the `standard` extra is installed.
**Fix:** Keep `httpx2` in the `dev` extra. If `from fastapi.testclient import TestClient` starts
failing, check what the installed Starlette version imports before changing the dependency.

### 2026-07-30 — A wrong `SERVICE_TYPE` looks perfectly healthy

**Surprise:** A service connects, `/health` reports `ok`, requests are consumed and acknowledged —
and no handler ever runs and no response is ever published.
**Cause:** The request exchange is a fanout, so every service receives a copy of every request.
`route_payload` returns `None` for any message whose `serviceType` is not this service's, and the
consumer acks it without responding. Silently ignoring other services' traffic is the normal path,
so a typo in `SERVICE_TYPE` is indistinguishable from it.
**Fix:** Compare `SERVICE_TYPE` against the `serviceType` the caller actually sends before
investigating anything else. `POST /debug/simulate-request` returns `{"ignored": true}` on a
mismatch, which isolates it in one call without a broker.

### 2026-07-30 — Envelope `success` is inverted against the handler's

**Surprise:** A handler returns `True` and the response envelope reads `"success": 0`.
**Cause:** Two different conventions meet in `envelope()`: the handler returns a Python boolean,
while the published contract uses `0` for success and `1` for failure (`int(not success)`).
**Fix:** Handlers return the boolean and never build the envelope themselves. When reading a
response off the wire, `0` is the good case — assert against `ok()` / `error()` rather than
hand-writing the number.

### 2026-07-30 — A missing `X-Request-Id` silently drops the audit row

**Surprise:** An external call completes, the handler calls both audit methods, and
`integration_request_response` has no row for it.
**Cause:** `create_pending_log` returns `None` when `request_id` is falsy (it logs a warning first),
and `complete_log` is a no-op on a `None` ID. The same shape of silence occurs when the database is
unavailable — both are best-effort by design.
**Fix:** Check the inbound `X-Request-Id` header before suspecting the database. Audit rows exist
only for correlated requests; the debug endpoint supplies `debug-request` as a default, so it will
write rows where a real uncorrelated message would not.

### 2026-08-01 — The git guardrail hook failed open without `jq`

**Surprise:** Installing `git-guardrails-claude-code` produced a hook that blocked nothing. Piping
`git push origin main` through it exited `0`.
**Cause:** The bundled script read the command with `jq -r '.tool_input.command'`. `jq` is not on
this machine, so `COMMAND` was empty, no pattern matched, and the hook allowed everything — a
guardrail that reports success while doing nothing is worse than none, because it is trusted.
**Fix:** The script now tries `jq`, then `python`, then `python3`, and falls back to scanning the
raw JSON payload — a missing parser now over-blocks rather than under-blocks. Both copies (the
installed `.claude/hooks/` one and the bundled `scripts/` one) carry the fix. Verify any hook by
running its blocked case and confirming exit code `2`, never by reading the script.
