param(
    [string]$Root = "$env:USERPROFILE\Downloads\btpit_stage4_update_bundle",
    [string]$Solver = "$env:USERPROFILE\Downloads\stage6_vbi_v3_fullfield_substep.py"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
    throw "Project root not found: $Root"
}
if (-not (Test-Path -LiteralPath $Solver -PathType Leaf)) {
    throw "Canonical V3 solver not found: $Solver"
}

$required = @(
    "outputs\forecast_benchmark_seed13\vbi_input_C_residual_support_consistency.npz",
    "outputs\forecast_benchmark_seed13\canonical_test600_manifest.csv",
    "outputs\stage6_vbi_seed13_test600_C_support_consistent\stage6_v3_bridge_responses.npz",
    "outputs\stage6_vbi_seed13_test600_C_support_consistent\stage6_v3_config.json"
)
foreach ($rel in $required) {
    $p = Join-Path $Root $rel
    if (-not (Test-Path -LiteralPath $p -PathType Leaf)) {
        throw "Required canonical input missing: $p"
    }
}

$py = "$env:USERPROFILE\Downloads\btpit_gpu_minimal\.venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $py -PathType Leaf)) {
    $py = "py"
}

$script = "$env:USERPROFILE\Downloads\run_structures_revision_experiments.py"
$url = "https://raw.githubusercontent.com/priyankjairaj100/linebyline/main/experiments/run_structures_revision_experiments.py"

Write-Host ""
Write-Host "Downloading current experiment runner..."
Invoke-WebRequest -Uri $url -OutFile $script -UseBasicParsing

Write-Host "Checking Python environment and script syntax..."
& $py -c "import numpy, pandas; print('numpy', numpy.__version__, '| pandas', pandas.__version__)"
if ($LASTEXITCODE -ne 0) {
    throw "Python environment does not have working numpy/pandas."
}
& $py -m py_compile $script $Solver
if ($LASTEXITCODE -ne 0) {
    throw "Python syntax check failed."
}

Write-Host ""
Write-Host "Running Structures revision experiment suite..."
Write-Host "  Phase 0: canonical solver reproduction on 6 fixed windows"
Write-Host "  Phase 1: full 600-window load-matched control"
Write-Host "  Phase 2: Raw Residual vs Support-Consistent vs Load-Matched analysis"
Write-Host "  Phase 3: 37-scenario paired bootstrap"
Write-Host "  Phase 4: forecasting mismatch / future-arrival analysis"
Write-Host "  Phase 5: damping and structural-dt sensitivity (3 windows/scenario)"
Write-Host ""
Write-Host "The existing canonical files are read-only; new results go to outputs\structures_revision_experiments."
Write-Host ""

& $py $script --root "$Root" --solver "$Solver" --sensitivity-per-scenario 3

if ($LASTEXITCODE -ne 0) {
    throw "Experiment suite failed with exit code $LASTEXITCODE"
}

$result = Join-Path $Root "outputs\structures_revision_experiments\STRUCTURES_REVISION_RESULTS.txt"

if (-not (Test-Path -LiteralPath $result -PathType Leaf)) {
    throw "Run exited without producing expected result file: $result"
}

Write-Host ""
Write-Host "SUCCESS"
Write-Host "Upload this result file to ChatGPT:"
Write-Host $result
