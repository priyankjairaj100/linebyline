$ErrorActionPreference = "Stop"

$zip = Join-Path $env:USERPROFILE "Downloads\BT_PIT_CANONICAL_METADATA.zip"
$unpack = Join-Path $env:USERPROFILE "Downloads\BT_PIT_CANONICAL_METADATA_UNPACKED"
$out = Join-Path $env:USERPROFILE "Downloads\BT_PIT_CANONICAL_REVIEW.txt"

if (-not (Test-Path -LiteralPath $zip -PathType Leaf)) {
    throw "ZIP not found: $zip"
}

New-Item -ItemType Directory -Path $unpack -Force | Out-Null
Expand-Archive -LiteralPath $zip -DestinationPath $unpack -Force
$unpack = (Resolve-Path -LiteralPath $unpack).Path.TrimEnd('\')

$files = @(
    Get-ChildItem -LiteralPath $unpack -Recurse -File |
    Where-Object { $_.Extension.ToLowerInvariant() -in @(".csv",".json",".txt",".md",".ps1") } |
    Sort-Object FullName
)
if ($files.Count -eq 0) {
    throw "No readable metadata files found after extraction."
}

$writer = New-Object System.IO.StreamWriter($out, $false, (New-Object System.Text.UTF8Encoding($false)))
try {
    $writer.WriteLine("# BT-PIT canonical audit metadata")
    $writer.WriteLine("# This is extracted text only; no experiment has been rerun.")
    $writer.WriteLine("FILE_COUNT: $($files.Count)")
    foreach ($file in $files) {
        $relative = $file.FullName.Substring($unpack.Length).TrimStart('\')
        $writer.WriteLine("")
        $writer.WriteLine("===== BEGIN FILE: $relative =====")
        $writer.WriteLine([System.IO.File]::ReadAllText($file.FullName))
        $writer.WriteLine("===== END FILE: $relative =====")
    }
}
finally {
    $writer.Dispose()
}

Write-Host "Review text created: $out"
Write-Host "Text files combined: $($files.Count)"
Get-Item -LiteralPath $out | Select-Object Name, Length
