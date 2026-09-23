param(
    [string]$IsccPath = "",
    [switch]$SkipPortableBuild,
    [switch]$SkipInstallerSmoke
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root
$python = (Get-Command python -ErrorAction Stop).Source
$identity = @(& $python -c "from app.version import PRODUCT_NAME, EXECUTABLE_NAME, __version__; print(PRODUCT_NAME); print(EXECUTABLE_NAME); print(__version__)")
if ($LASTEXITCODE -ne 0 -or $identity.Count -ne 3 -or
    $identity[0] -ne "AI Video Flow" -or $identity[1] -ne "AIVideoFlow") {
    throw "Unexpected release identity in app/version.py"
}
$version = $identity[2]
if ($version -notmatch '^(\d+)\.(\d+)\.(\d+)-rc\.(\d+)$') {
    throw "Unsupported release version: $version"
}
$numericVersion = "$($Matches[1]).$($Matches[2]).$($Matches[3]).$($Matches[4])"
$dist = Join-Path $root "dist\AIVideoFlow"
$release = Join-Path $root "release\v$version"
$archive = Join-Path $release "AI-Video-Flow-$version-windows-x64.zip"
$installer = Join-Path $release "AI-Video-Flow-$version-windows-x64-setup.exe"
$evidence = Join-Path $root "evidence\V0.1-Windows-Installer"

if (-not $SkipPortableBuild) {
    & (Join-Path $PSScriptRoot "build_windows.ps1")
    if ($LASTEXITCODE -ne 0) { throw "Portable build failed" }
}
if (-not (Test-Path -LiteralPath (Join-Path $dist "AIVideoFlow.exe")) -or
    -not (Test-Path -LiteralPath $archive)) {
    throw "Matching portable folder and ZIP are required before building Installer"
}

$candidates = @(
    $IsccPath,
    $env:AIVIDEO_ISCC,
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 7\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 7\ISCC.exe")
) | Where-Object { $_ }
$compiler = $null
foreach ($candidate in $candidates) {
    if (Test-Path -LiteralPath $candidate -PathType Leaf) {
        $compiler = (Resolve-Path -LiteralPath $candidate).Path
        break
    }
}
if (-not $compiler) {
    $command = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if ($command) { $compiler = $command.Source }
}
if (-not $compiler) { throw "Inno Setup 7.1.0 ISCC.exe not found; set -IsccPath or AIVIDEO_ISCC" }
$compilerVersion = (& $compiler --version).Trim()
if ($LASTEXITCODE -ne 0 -or $compilerVersion -ne "7.1.0") {
    throw "Inno Setup 7.1.0 required; found $compilerVersion"
}

$arguments = @(
    "--define=SourceDir=$dist",
    "--define=OutputDir=$release",
    "--define=ReleaseVersion=$version",
    "--define=NumericVersion=$numericVersion",
    "packaging/windows/AI-Video-Flow.iss"
)
& $compiler @arguments
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $installer)) {
    throw "Installer compilation failed"
}

New-Item -ItemType Directory -Path $evidence -Force | Out-Null
& $python "tools/release_manifest.py" $release (Join-Path $evidence "release-manifest.json")
if ($LASTEXITCODE -ne 0) { throw "Release checksum manifest failed" }
if (-not $SkipInstallerSmoke) {
    & $python "tools/installer_smoke.py" $installer $dist $root (Join-Path $evidence "installer-smoke.json")
    if ($LASTEXITCODE -ne 0) { throw "Installer smoke failed" }
}
Write-Host "AI Video Flow release candidate ready"
Write-Host "Portable: $archive"
Write-Host "Installer: $installer"
Write-Host "Checksums: $(Join-Path $release 'SHA256SUMS.txt')"
