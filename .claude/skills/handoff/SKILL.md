---
name: handoff
description: Compact the current conversation into a handoff document for another agent or session to pick up.
argument-hint: "What will the next session be used for?"
disable-model-invocation: true
---

Write a handoff document summarising the current conversation so a fresh agent can continue the
work. Save it to the session scratchpad if one is available, otherwise the OS temp directory —
never into the repository.

Cover: what was asked for, what is done, what is in flight, what is blocked, and the next concrete
step. Include a "suggested skills" section naming which `.claude/skills/*` entries the next session
should reach for, based on what is still open.

Reference by path instead of re-pasting: touched files, the relevant knowledge entries under
`.claude/knowledge/`, and any skill that already covers the pattern involved. A handoff that
duplicates a file goes stale the moment that file changes.

Redact credentials, connection strings, tokens, and any real personal or production data that came
up during the session. Where an example is needed, use obviously fake values.

Before writing, check the capture triggers in `CLAUDE.md`: a gotcha or decision that belongs in
`.claude/knowledge/` should be recorded there, not buried in a temporary handoff.

If the user passed arguments, treat them as a description of what the next session will focus on
and tailor the document accordingly.
