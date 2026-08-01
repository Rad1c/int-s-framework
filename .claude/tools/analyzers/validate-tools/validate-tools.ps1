param(
    [string]$ToolsRoot = (Join-Path $PSScriptRoot '..\..')
)

$requiredFields = 'id', 'description', 'type', 'runtime', 'entrypoint', 'inputs', 'outputs', 'requirements', 'tags', 'lifecycle'
$errors = [System.Collections.Generic.List[string]]::new()
$manifests = Get-ChildItem -LiteralPath (Resolve-Path -LiteralPath $ToolsRoot) -Filter tool.yaml -File -Recurse

foreach ($manifest in $manifests) {
    $content = Get-Content -LiteralPath $manifest.FullName -Raw

    foreach ($field in $requiredFields) {
        if ($content -notmatch "(?m)^$([regex]::Escape($field)):") {
            $errors.Add("$($manifest.FullName): missing '$field'")
        }
    }

    if ($content -match '(?m)^entrypoint:\s*(.+?)\s*$') {
        $entrypoint = $Matches[1].Trim('''', '"')
        if (-not (Test-Path -LiteralPath (Join-Path $manifest.DirectoryName $entrypoint) -PathType Leaf)) {
            $errors.Add("$($manifest.FullName): entrypoint '$entrypoint' does not exist")
        }
    }

    if (-not (Test-Path -LiteralPath (Join-Path $manifest.DirectoryName 'README.md') -PathType Leaf)) {
        $errors.Add("$($manifest.FullName): no README.md beside the manifest")
    }

    # The registry sorts tools into official/candidate by this field, so a manifest that
    # disagrees with its own location makes the generated index lie.
    if ($content -match '(?m)^lifecycle:\s*(.+?)\s*$') {
        $lifecycle = $Matches[1].Trim('''', '"')
        $inCandidateDir = (Split-Path -Path (Split-Path -Path $manifest.DirectoryName -Parent) -Leaf) -eq 'candidate'

        if ($inCandidateDir -and $lifecycle -ne 'candidate') {
            $errors.Add("$($manifest.FullName): lives under tools/candidate/ but declares lifecycle '$lifecycle'")
        }
        if (-not $inCandidateDir -and $lifecycle -eq 'candidate') {
            $errors.Add("$($manifest.FullName): declares lifecycle 'candidate' but does not live under tools/candidate/")
        }
    }
}

if ($errors.Count -gt 0) {
    $errors | ForEach-Object { Write-Error $_ }
    exit 1
}

Write-Output "Validated $($manifests.Count) tool manifest(s)."
