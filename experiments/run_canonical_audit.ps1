param(
    [string]$Root = "$env:USERPROFILE\Downloads\btpit_stage4_update_bundle",
    [string]$Package = "$env:USERPROFILE\Downloads\BT_PIT_NEXT_AUDIT.zip"
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
    throw "Root project directory not found: $Root"
}

$base = "https://raw.githubusercontent.com/priyankjairaj100/linebyline/main/experiments"
$working = Join-Path $env:TEMP ("btpit_audit_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $working -Force | Out-Null

try {
    Write-Host "Downloading audit scripts (read-only with respect to original project)..."
    $analyze = Join-Path $working "analyze_support_scenarios.py"
    $inspect = Join-Path $working "inspect_canonical_npz.py"
    $finder = Join-Path $working "find_canonical_v3_source.ps1"
    Invoke-WebRequest -Uri "$base/analyze_support_scenarios.py" -OutFile $analyze
    Invoke-WebRequest -Uri "$base/inspect_canonical_npz.py" -OutFile $inspect
    Invoke-WebRequest -Uri "$base/find_canonical_v3_source.ps1" -OutFile $finder

    Write-Host "Analyzing saved 37-scenario support-consistency pairs..."
    & py $analyze --root $Root --out_dir (Join-Path $working "scenario_uncertainty")
    if ($LASTEXITCODE -ne 0) { throw "Scenario analysis failed. Error code: $LASTEXITCODE" }

    Write-Host "Reading keys and shapes from canonical NPZ archives..."
    & py $inspect --root $Root --out (Join-Path $working "CANONICAL_NPZ_SCHEMA.json")
    if ($LASTEXITCODE -ne 0) { throw "NPZ schema inspection failed. Error code: $LASTEXITCODE" }

    Write-Host "Searching Downloads and Desktop for Stage 6 v3 source..."
    & powershell -NoProfile -ExecutionPolicy Bypass -File $finder -Output (Join-Path $working "BT_PIT_V3_SOURCE_SEARCH.txt")
    if ($LASTEXITCODE -ne 0) { throw "Source search failed. Error code: $LASTEXITCODE" }

    $readme = @"
BT-PIT journal revision: canonical audit outputs
Created $(Get-Date -Format o)

- scenario_uncertainty/scenario_cluster_bootstrap.csv:
  paired scenario-cluster bootstrap; positive raw minus masked = improvement.
- scenario_uncertainty/scenario_leave_one_out.csv:
  influence of every scenario, especially S0219.
- CANONICAL_NPZ_SCHEMA.json:
  actual canonical forecast / VBI NPZ keys and shapes; no raw arrays.
- BT_PIT_V3_SOURCE_SEARCH.txt:
  read-only search for actual canonical Stage 6 v3 source.

IMPORTANT: This package does NOT constitute completed load-matched or
damping/time-step numerical experiments. The v3 solver must be recovered
or independently reconstructed/validated before those comparisons.
"@
    $readme | Set-Content (Join-Path $working "README.txt") -Encoding UTF8

    # Only output reports, not scripts or original numerical data.
    $out = Join-Path $env:TEMP ("btpit_output_" + [guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $out -Force | Out-Null
    try {
        Copy-Item -LiteralPath (Join-Path $working "scenario_uncertainty") -Destination $out -Recurse
        foreach ($name in @("CANONICAL_NPZ_SCHEMA.json", "BT_PIT_V3_SOURCE_SEARCH.txt", "README.txt")) {
            Copy-Item -LiteralPath (Join-Path $working $name) -Destination $out
        }
        Compress-Archive -Path (Join-Path $out "*") -DestinationPath $Package -CompressionLevel Optimal -Force
    }
    finally {
        Remove-Item -LiteralPath $out -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Host ""
    Write-Host "SUCCESS. Upload this ZIP to ChatGPT:"
    Write-Host $Package
    Get-Item -LiteralPath $Package | Select-Object Name, @{Name="SizeMB";Expression={[math]::Round($_.Length / 1MB, 3)}} | Format-Table
}
finally {
    Remove-Item -LiteralPath $working -Recurse -Force -ErrorAction SilentlyContinue
}
