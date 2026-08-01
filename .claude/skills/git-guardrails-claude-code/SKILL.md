---
name: git-guardrails-claude-code
description: Set up a Claude Code PreToolUse hook that blocks dangerous git commands (push, reset --hard, clean, branch -D, checkout ./restore .) before they execute. Use when the user wants a hard technical guardrail on destructive git operations in this repo, not just a written policy.
---

# Setup Git Guardrails

A written policy against destructive git commands is a convention an agent can still slip on. This skill turns it into an enforced PreToolUse hook that blocks the `Bash` call outright before it runs.

Adapted from [mattpocock/skills](https://github.com/mattpocock/skills). The blocking logic is language- and stack-agnostic — it matches on the git command itself.

## What gets blocked

- `git push` (all variants including `--force`)
- `git reset --hard`
- `git clean -f` / `git clean -fd`
- `git branch -D`
- `git checkout .` / `git restore .`

When blocked, Claude sees a stderr message saying it does not have authority to run that command — it does not silently retry or work around it.

## Steps

### 1. Ask scope

Ask the user: install for **this project only** (`.claude/settings.json`) or **all projects on this machine** (`~/.claude/settings.json`)? Project scope is the sane default unless the user wants it everywhere.

### 2. Copy the hook script

Bundled at [scripts/block-dangerous-git.sh](scripts/block-dangerous-git.sh) (bash — works fine under Git Bash on this Windows machine, same shell the `Bash` tool already uses here).

Copy it to:
- **Project**: `.claude/hooks/block-dangerous-git.sh`
- **Global**: `~/.claude/hooks/block-dangerous-git.sh`

No `chmod +x` needed on Windows/Git Bash — the hook is invoked as `bash <path>`, not executed directly; just make sure the settings entry below calls it via `bash`.

### 3. Add the hook to settings

**Project** (`.claude/settings.json`):
```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "bash \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/block-dangerous-git.sh"
          }
        ]
      }
    ]
  }
}
```

**Global** (`~/.claude/settings.json`): same, but `command` is `bash ~/.claude/hooks/block-dangerous-git.sh`.

If the settings file already exists, merge into the existing `hooks.PreToolUse` array — don't overwrite other hooks/settings already there.

### 4. Ask about customization

Ask if the user wants to add/remove patterns. One repo-specific candidate worth raising: blocking pushes to `main` specifically (vs. all pushes) if they'd rather allow pushing feature branches freely and only gate `main`/`release/*`.

### 5. Verify

```bash
echo '{"tool_input":{"command":"git push origin main"}}' | bash .claude/hooks/block-dangerous-git.sh
```
Should exit with code 2 and print a `BLOCKED:` message to stderr.

## Note

This skill only describes how to set the hook up — it does **not** install it automatically just by existing in `.claude/skills/`. Only run these steps when the user explicitly asks to add this guardrail (it edits `settings.json`, a standing config change).
