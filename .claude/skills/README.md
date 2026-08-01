# Skills

Skills contain reusable instructions for performing a specific kind of work.

Each skill uses `.claude/skills/<name>/SKILL.md` as its canonical entry point. Supporting scripts
and references stay inside the same skill folder. Claude Code discovers them automatically.

A skill explains how to do something; it is not an executable tool, a project fact, or an
end-to-end playbook.

Add one only when the user agrees to it — see the capture triggers in `CLAUDE.md` — and write it
following `writing-great-skills`.
