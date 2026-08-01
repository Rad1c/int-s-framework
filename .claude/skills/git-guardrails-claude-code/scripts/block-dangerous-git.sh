#!/bin/bash
# PreToolUse hook: blocks destructive git commands before they execute.
# Exit 2 blocks the Bash call and shows the message to Claude; exit 0 allows it.

INPUT=$(cat)

# Extract .tool_input.command with whatever parser this machine has. With no
# parser, fall back to scanning the raw JSON: the command text is in there, so
# the guardrail still blocks instead of silently allowing everything.
if command -v jq >/dev/null 2>&1; then
  COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command')
elif command -v python >/dev/null 2>&1; then
  COMMAND=$(echo "$INPUT" | python -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))")
elif command -v python3 >/dev/null 2>&1; then
  COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('command',''))")
else
  COMMAND="$INPUT"
fi

DANGEROUS_PATTERNS=(
  "git push"
  "git reset --hard"
  "git clean -fd"
  "git clean -f"
  "git branch -D"
  "git checkout \."
  "git restore \."
  "push --force"
  "reset --hard"
)

for pattern in "${DANGEROUS_PATTERNS[@]}"; do
  if echo "$COMMAND" | grep -qE "$pattern"; then
    echo "BLOCKED: '$COMMAND' matches dangerous pattern '$pattern'. The user has prevented you from doing this." >&2
    exit 2
  fi
done

exit 0
