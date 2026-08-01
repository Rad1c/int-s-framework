# Validate Tools

## Purpose

Checks every `tool.yaml` under a tools directory for:

- the required fields;
- an entrypoint that exists;
- a `README.md` beside the manifest;
- a `lifecycle` that matches the tool's location — `candidate` exactly when the tool sits under `tools/candidate/`. `sync-registry` sorts the index by this field, so a manifest that disagrees with its own location makes the index lie.

## Requirements

Windows PowerShell 5.1 or newer. No external dependencies.

## Usage

```powershell
.\tools\analyzers\validate-tools\validate-tools.ps1
```

Optionally pass another tools directory with `-ToolsRoot`.

## Output and Exit Codes

- `0` — all discovered manifests are valid.
- `1` — a manifest is incomplete, malformed, or points to a missing entrypoint.
