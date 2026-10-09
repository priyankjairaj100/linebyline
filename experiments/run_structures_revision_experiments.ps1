param(
    [string]$Root = "$env:USERPROFILE\Downloads\btpit_stage4_update_bundle",
    [string]$Solver = "$env:USERPROFILE\Downloads\stage6_vbi_v3_fullfield_substep.py"
)

$ErrorActionPreference = "Stop"

$py = "$env:USERPROFILE\Downloads\btpit_gpu_minimal\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $py)) {
    $py = "py"
}

$script = "$env:USERPROFILE\Downloads\run_structures_revision_experiments.py"
$url = "https://raw.githubusercontent.com/priyankjairaj100/linebyline/main/experiments/run_structures_revision_experiments.py"

Invoke-WebRequest -Uri $url -OutFile $script -UseBasicParsing

Write-Host ""
Write-Host "Running full Structures revision experiment suite..."
Write-Host "This performs:"
Write-Host "  1) exact solver reproduction check"
Write-Host "  2) full 600-window load-matched control"
Write-Host "  3) raw vs support-consistent ablation"
Write-Host "  4) 37-scenario bootstrap uncertainty"
Write-Host "  5) forecasting-mismatch / future-arrival analysis"
Write-Host "  6) damping and structural-time-step sensitivity on a 3-window-per-scenario subset"
Write-Host ""

& $py $script --root "$Root" --solver "$Solver" --sensitivity-per-scenario 3

if ($LASTEXITCODE -ne 0) {
    throw "Experiment suite failed with exit code $LASTEXITCODE"
}

$result = Join-Path $Root "outputs\structures_revision_experiments\STRUCTURES_REVISION_RESULTS.txt"

Write-Host ""
Write-Host "SUCCESS"
Write-Host "Upload this result file to ChatGPT:"
Write-Host $result
