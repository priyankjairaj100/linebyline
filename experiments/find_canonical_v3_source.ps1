param(
    [string[]]$Roots = @(
        "$env:USERPROFILE\Downloads",
        "$env:USERPROFILE\Desktop"
    ),
    [string]$Output = "$env:USERPROFILE\Downloads\BT_PIT_V3_SOURCE_SEARCH.txt"
)

$ErrorActionPreference = "Stop"

# Search scripts, not large NPZ/CSV/ZIP files. Read-only.
$tokens = @(
    "stage6_v3_bridge_responses",
    "stage6_v3_summary_metrics",
    "stage6_v3_per_sample_metrics",
    "stage6_v3_config",
    "vbi_formulation_comparison_responses",
    "min_mass",
    "m_ref",
    "structural_dt"
)

$lines = [System.Collections.Generic.List[string]]::new()
$matchedFiles = [System.Collections.Generic.HashSet[string]]::new()
$scanned = 0
$lines.Add("BT-PIT canonical Stage 6 v3 code search")
$lines.Add("Run date: $(Get-Date -Format o)")
$lines.Add("Only *.py, *.ps1 and *.ipynb files under Downloads/Desktop were searched.")
$lines.Add("")

foreach ($root in $Roots) {
    if (-not (Test-Path -LiteralPath $root -PathType Container)) {
        $lines.Add("MISSING SEARCH ROOT: $root")
        continue
    }

    $lines.Add("SEARCH ROOT: $root")
    $candidates = @(Get-ChildItem -LiteralPath $root -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Extension.ToLowerInvariant() -in @(".py", ".ps1", ".ipynb") -and
            $_.Length -lt 8MB -and
            $_.FullName -notmatch '\\(\.venv|venv|node_modules|__pycache__|\.git)\\'
        })
    foreach ($f in $candidates) {
        $scanned++
        $hits = @(Select-String -LiteralPath $f.FullName -SimpleMatch -Pattern $tokens -ErrorAction SilentlyContinue)
        if ($hits.Count -eq 0) {
            continue
        }
        [void]$matchedFiles.Add($f.FullName)
        $lines.Add("MATCHED FILE: $($f.FullName)")
        foreach ($hit in ($hits | Select-Object -First 25)) {
            $lines.Add("  line $($hit.LineNumber): $($hit.Line.Trim())")
        }
        $lines.Add("")
    }
}
$lines.Add("Scanned script/notebook files: $scanned")
$lines.Add("Files with matching indicators: $($matchedFiles.Count)")
$lines.Add("Next action: If a file contains the actual stage6_v3 response computation,")
$lines.Add("upload that source file to ChatGPT. Do NOT upload private files unrelated to BT-PIT.")

$lines | Set-Content -LiteralPath $Output -Encoding UTF8
Write-Host ""
Write-Host "Search finished. Script files scanned: $scanned"
Write-Host "Possible matches: $($matchedFiles.Count)"
Write-Host "Review and upload if useful: $Output"
