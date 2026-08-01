# Sync Registry

## Purpose

Regenerates `.claude/registry.yaml` from the directory tree. A hand-maintained index drifts from
reality without anyone noticing; a generated one can only list files that are actually there.

Tool lifecycle (`official` or `candidate`) is read from each `tool.yaml`, so the index can never
disagree with the manifest.

## Requirements

Windows PowerShell 5.1 or newer. No external dependencies.

## Usage

```powershell
.\.claude\tools\registry\sync-registry\sync-registry.ps1
.\.claude\tools\registry\sync-registry\sync-registry.ps1 -Check
```

Run it after adding, moving, promoting, or removing a registered asset. Use `-Check` to detect
drift without writing.

## Inputs and Outputs

- `-ClaudeRoot <path>` — the `.claude` directory to index. Defaults to the one containing this tool.
- `-Check` — compare instead of write.
- Writes `registry.yaml` to the root of that directory.

## Exit Codes

- `0` — the index was written, or `-Check` found it current.
- `1` — `-Check` found the committed index out of date.
