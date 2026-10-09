param(
    [string]$Root = "$env:USERPROFILE\Downloads\btpit_stage4_update_bundle",
    [string]$DestinationZip = "$env:USERPROFILE\Downloads\BT_PIT_CANONICAL_METADATA.zip"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
    throw "Project directory not found: $Root"
}

$Root = (Resolve-Path -LiteralPath $Root).Path.TrimEnd('\')
$stage = Join-Path $env:TEMP ("btpit_review_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $stage -Force | Out-Null

# Canonical run diagnostics only: small configurations, manifests and metrics.
# This script never modifies your original project.
$relativeFiles = @(
    "outputs\forecast_benchmark_seed13\canonical_seed13_split_and_test600.npz",
    "outputs\forecast_benchmark_seed13\canonical_test600_manifest.csv",
    "outputs\forecast_benchmark_seed13\forecast_metrics_seed13_test600.csv",
    "outputs\forecast_benchmark_seed13\stage5_seed13_clean_residual\stage5_config.json",
    "outputs\forecast_benchmark_seed13\stage5_seed13_clean_residual\stage5_calibrated_thresholds.csv",
    "outputs\forecast_benchmark_seed13\stage5_seed13_clean_residual\stage5_threshold_sweep_val.csv",
    "outputs\stage6_vbi_seed13_test600_A\stage6_v3_config.json",
    "outputs\stage6_vbi_seed13_test600_A\stage6_v3_per_sample_metrics.csv",
    "outputs\stage6_vbi_seed13_test600_A\stage6_v3_summary_metrics.csv",
    "outputs\stage6_vbi_seed13_test600_B\stage6_v3_config.json",
    "outputs\stage6_vbi_seed13_test600_B\stage6_v3_per_sample_metrics.csv",
    "outputs\stage6_vbi_seed13_test600_B\stage6_v3_summary_metrics.csv",
    "outputs\stage6_vbi_seed13_test600_C_support_consistent\stage6_v3_config.json",
    "outputs\stage6_vbi_seed13_test600_C_support_consistent\stage6_v3_per_sample_metrics.csv",
    "outputs\stage6_vbi_seed13_test600_C_support_consistent\stage6_v3_summary_metrics.csv",
    "outputs\paper_figures_vbi\forecast_metrics_table.csv",
    "outputs\paper_figures_vbi\vbi_response_metrics_table.csv",
    "outputs\paper_additional_clusters_only\R2_bridge_error_distributions\window_metrics.csv",
    "outputs\paper_additional_clusters_only\R4_support_consistency\paired_scenario_errors.csv",
    "outputs\paper_additional_clusters_only\R4_support_consistency\removed_load_by_horizon.csv",
    "outputs\paper_additional_clusters_only\R4_support_consistency\window_peak_acceleration.csv"
)

$copied = [System.Collections.Generic.List[string]]::new()
$missing = [System.Collections.Generic.List[string]]::new()

try {
    foreach ($relative in $relativeFiles) {
        $source = Join-Path $Root $relative
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
            [void]$missing.Add($relative)
            continue
        }
        $relativeDir = Split-Path $relative -Parent
        $destDir = Join-Path $stage $relativeDir
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        Copy-Item -LiteralPath $source -Destination (Join-Path $destDir (Split-Path $relative -Leaf)) -Force
        [void]$copied.Add($relative)
    }

    $allFiles = @(Get-ChildItem -LiteralPath $Root -Recurse -File)
    $candidateScripts = @(
        $allFiles |
        Where-Object {
            $_.Extension -in @(".py", ".ps1") -and
            $_.Name -match "vbi|coupl|stage6|newmark|solver|response|canonical|forecast"
        } |
        Select-Object @{N="RelativePath";E={$_.FullName.Substring($Root.Length + 1)}},
                      @{N="SizeKB";E={[math]::Round($_.Length / 1KB,2)}}
    )

    $npzIndex = @(
        $allFiles |
        Where-Object { $_.Extension -eq ".npz" } |
        Select-Object @{N="RelativePath";E={$_.FullName.Substring($Root.Length + 1)}},
                      @{N="SizeMB";E={[math]::Round($_.Length / 1MB,2)}}
    )

    $candidateScripts | Export-Csv (Join-Path $stage "SCRIPT_CANDIDATES.csv") -NoTypeInformation
    $npzIndex | Export-Csv (Join-Path $stage "NPZ_FILE_INDEX.csv") -NoTypeInformation
    $copied | Set-Content (Join-Path $stage "COPIED_FILES.txt") -Encoding UTF8
    $missing | Set-Content (Join-Path $stage "MISSING_FILES.txt") -Encoding UTF8

    if ($copied.Count -lt 5) {
        throw "Only $($copied.Count) canonical metadata files found. Check Root and your project version."
    }

    Compress-Archive -Path (Join-Path $stage "*") -DestinationPath $DestinationZip -CompressionLevel Optimal -Force

    Write-Host ""
    Write-Host "Created: $DestinationZip"
    Write-Host "Canonical files copied: $($copied.Count)"
    Write-Host "Missing optional files: $($missing.Count)"
    Write-Host ""
    Write-Host "Possible VBI solver scripts:"
    $candidateScripts | Format-Table -AutoSize
    Write-Host ""
    Get-Item -LiteralPath $DestinationZip | Select-Object Name, @{N="SizeMB";E={[math]::Round($_.Length/1MB,2)}} | Format-Table
}
finally {
    Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
}
