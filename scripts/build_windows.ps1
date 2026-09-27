param(
    [switch]$SkipSmoke,
    [string]$FFmpegDir = ""
)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Set-Location $root

function Assert-BuildPath([string]$PathValue) {
    $full = [System.IO.Path]::GetFullPath($PathValue)
    $safeRoot = $root.TrimEnd('\') + '\'
    if (-not $full.StartsWith($safeRoot, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean outside repository: $full"
    }
    return $full
}

$pythonExe = (Get-Command python -ErrorAction Stop).Source
$pythonDirectory = Split-Path $pythonExe -Parent
$expectedPackager = "6.22.3"
$actualPackager = & $pythonExe -c "import PyInstaller; print(PyInstaller.__version__)"
if ($LASTEXITCODE -ne 0 -or $actualPackager.Trim() -ne $expectedPackager) {
    throw "Install build dependencies first: python -m pip install -r requirements-build.txt"
}
$version = (& $pythonExe -c "from app.version import __version__; print(__version__)").Trim()
if ($LASTEXITCODE -ne 0 -or $version -notmatch '^\d+\.\d+\.\d+-rc\.\d+$') {
    throw "Unsupported release version: $version"
}

# The bundled media tools are pinned by third_party/ffmpeg/FFMPEG_PIN.json and
# staged in .tools/ffmpeg; PATH discovery is deliberately not used so a release
# build cannot silently pick up an unpinned FFmpeg.
if (-not $FFmpegDir) {
    $FFmpegDir = Join-Path $root ".tools\ffmpeg"
}
$FFmpegDir = Assert-BuildPath $FFmpegDir
$ffmpeg = Join-Path $FFmpegDir "bin\ffmpeg.exe"
$ffprobe = Join-Path $FFmpegDir "bin\ffprobe.exe"
$license = Join-Path $FFmpegDir "LICENSE.txt"
foreach ($required in @($ffmpeg, $ffprobe, $license)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Missing pinned FFmpeg input: $required"
    }
}
& $pythonExe "tools/ffmpeg_provenance.py" verify $ffmpeg $ffprobe
if ($LASTEXITCODE -ne 0) {
    throw "Staged FFmpeg does not match third_party/ffmpeg/FFMPEG_PIN.json."
}

$work = Assert-BuildPath (Join-Path $root "build\windows")
$dist = Assert-BuildPath (Join-Path $root "dist\AIVideoFlow")
$release = Assert-BuildPath (Join-Path $root "release\v$version")
foreach ($target in @($work, $dist)) {
    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }
}
New-Item -ItemType Directory -Path $work,$release -Force | Out-Null

$versionFile = Join-Path $work "version_info.txt"
& $pythonExe "tools/write_windows_version.py" $versionFile
if ($LASTEXITCODE -ne 0) { throw "Version metadata generation failed." }

$env:AIGCFLOW_FFMPEG = $ffmpeg
$env:AIGCFLOW_FFPROBE = $ffprobe
$env:AIGCFLOW_FFMPEG_LICENSE = $license
$env:AIGCFLOW_VERSION_FILE = $versionFile

$pyInstallerArgs = @(
    "-m", "PyInstaller", "packaging/windows/AIGCFlow.spec",
    "--noconfirm", "--clean",
    "--distpath", (Join-Path $root "dist"),
    "--workpath", $work,
    "--log-level", "WARN"
)
$originalPath = $env:PATH
$env:PATH = $pythonDirectory + [System.IO.Path]::PathSeparator + (Join-Path $env:WINDIR "System32") + [System.IO.Path]::PathSeparator + $env:WINDIR
try {
    & $pythonExe @pyInstallerArgs
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }
} finally {
    $env:PATH = $originalPath
}

$toc = Join-Path $work "AIGCFlow\Analysis-00.toc"
if (Select-String -LiteralPath $toc -Pattern '\.codex\\|codex-runtimes' -Quiet) {
    throw "Build contamination detected in PyInstaller analysis."
}

$evidence = Join-Path $root "evidence\V0.1-Windows-Installer\portable"
& $pythonExe "tools/package_report.py" $dist (Join-Path $evidence "build-report.json") (Join-Path $evidence "build-report.md")
if ($LASTEXITCODE -ne 0) { throw "Package report failed." }

if (-not $SkipSmoke) {
    & $pythonExe "tools/clean_env_smoke.py" $dist $root $evidence
    if ($LASTEXITCODE -ne 0) { throw "Clean-environment smoke failed." }
}

$archive = Join-Path $release "AI-Video-Flow-$version-windows-x64.zip"
if (Test-Path -LiteralPath $archive) { Remove-Item -LiteralPath $archive -Force }
Compress-Archive -Path (Join-Path $dist "*") -DestinationPath $archive -CompressionLevel Optimal
$archiveItem = Get-Item -LiteralPath $archive
& $pythonExe "tools/archive_smoke.py" $archive $root (Join-Path $evidence "archive-smoke.json")
if ($LASTEXITCODE -ne 0) { throw "Archive smoke failed." }
& $pythonExe "tools/finalize_release.py" $archive (Join-Path $evidence "release-summary.json")
if ($LASTEXITCODE -ne 0) { throw "Release summary failed." }
Write-Host ""
Write-Host "Windows portable candidate ready"
Write-Host "Folder: $dist"
Write-Host "Archive: $archive"
Write-Host ("Archive size: {0:N1} MB" -f ($archiveItem.Length / 1MB))
