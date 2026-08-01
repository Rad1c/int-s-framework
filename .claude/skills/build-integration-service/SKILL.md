---
name: build-integration-service
description: Build or migrate a Python consumer service onto integration-service-framework. Use when creating a new RabbitMQ integration service, adding service-specific handlers or clients, replacing duplicated RabbitMQ/FastAPI/logging/audit infrastructure, standardizing a service's environment variables, or pinning a consumer repository to a released framework tag.
---

# Build Integration Service

The process lives in [`skills/build-integration-service/SKILL.md`](../../../skills/build-integration-service/SKILL.md)
at the repository root — read it now and follow it. That copy is the canonical one because it is
also the Codex skill shipped with the framework; this file exists only so Claude Code can reach it,
since the root `skills/` folder is not auto-discovered.

Before applying it, read the ownership boundary in [`CLAUDE.md`](../../../CLAUDE.md) and the
pipeline facts in [`.claude/knowledge/architecture.md`](../knowledge/architecture.md) and
[`integration-audit.md`](../knowledge/integration-audit.md) — the consumer-side mistakes that
recur are all boundary mistakes.

When the framework's published contract changes, update the root file, not this one.
