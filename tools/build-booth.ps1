<#
.SYNOPSIS
  Builds the ZIP that is distributed on BOOTH.

.DESCRIPTION
  Copies the files a user needs (the plugin for DSH, Claude Code and Codex, its docs and
  the DSH installer) into one folder named dsh-vrc-unity-supporter, adds 00_README_JA.txt
  from booth/ with the version filled in, and zips it as
  dist/booth/dsh-vrc-unity-supporter-<version>.zip.

  The folder name carries no version, so a user who replaces the folder in place keeps
  the same marketplace path in Claude Code and Codex.

  Refuses to build when the shipped files have uncommitted changes, so the ZIP matches a
  commit. Pass -AllowDirty to build a preview from the working tree.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File tools\build-booth.ps1
#>
[CmdletBinding()]
param(
    [string]$OutDir,
    [switch]$AllowDirty
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not $OutDir) { $OutDir = Join-Path $root 'dist\booth' }

# What a user needs. Tests, CI, maintainer notes and the BOOTH listing stay out.
$include = @(
    '.claude-plugin', '.codex-plugin', '.agents', 'claude', 'codex',
    'skills', 'tools', 'templates', 'installer', 'docs', 'locale',
    'README.md', 'LICENSE', 'THIRD-PARTY.md', 'package.json',
    'cordis.patch.yml', 'icon.svg', 'install.cmd'
)
$exclude = @('tools/publish.ps1', 'tools/build-booth.ps1', 'tools/verify-package.ps1')

function Invoke-Git {
    param([string[]]$Arguments)
    $output = & git -C $root @Arguments
    if ($LASTEXITCODE -ne 0) { throw "git $($Arguments -join ' ') failed ($LASTEXITCODE)" }
    return $output
}

# 1. The package must pass its own checks.
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'verify-package.ps1')
if ($LASTEXITCODE -ne 0) { throw 'verify-package failed; fix it before building the BOOTH ZIP' }

# 2. The shipped files match a commit, unless this is a preview.
$dirty = @(Invoke-Git (@('status', '--porcelain', '--') + $include + @('booth/00_README_JA.txt')))
if ($dirty.Count -gt 0 -and -not $AllowDirty) {
    $dirty | ForEach-Object { Write-Host "  $_" }
    throw 'uncommitted changes in shipped files; commit them or pass -AllowDirty for a preview'
}

$pkg = Get-Content (Join-Path $root 'package.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$version = $pkg.version
$name = $pkg.name

# 3. Stage the files: tracked ones plus new, not-ignored ones (so a -AllowDirty preview
#    includes files that are not committed yet).
$files = @(Invoke-Git (@('ls-files', '-co', '--exclude-standard', '--') + $include)) |
    Where-Object { $exclude -notcontains $_ } | Sort-Object -Unique
$stage = Join-Path $env:TEMP ("dsh-booth-" + [guid]::NewGuid().ToString('N'))
$top = Join-Path $stage $name
try {
    foreach ($rel in $files) {
        $source = Join-Path $root $rel
        if (-not (Test-Path -LiteralPath $source -PathType Leaf)) { continue }  # deleted in the working tree
        $target = Join-Path $top $rel
        $null = New-Item -ItemType Directory -Force -Path (Split-Path -Parent $target)
        Copy-Item -LiteralPath $source -Destination $target
    }

    # 4. The README for BOOTH users: version filled in, CRLF and a BOM so Notepad shows it right.
    $readme = Get-Content (Join-Path $root 'booth\00_README_JA.txt') -Raw -Encoding UTF8
    $readme = ($readme -replace '\{\{VERSION\}\}', $version) -replace "\r?\n", "`r`n"
    [IO.File]::WriteAllText((Join-Path $top '00_README_JA.txt'), $readme, (New-Object Text.UTF8Encoding $true))

    # 5. Zip with forward-slash entry names (Windows and other unzip tools both read them).
    $null = New-Item -ItemType Directory -Force -Path $OutDir
    $zipPath = Join-Path $OutDir "$name-$version.zip"
    if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
    Add-Type -AssemblyName System.IO.Compression, System.IO.Compression.FileSystem
    $zip = [IO.Compression.ZipFile]::Open($zipPath, [IO.Compression.ZipArchiveMode]::Create)
    try {
        foreach ($file in Get-ChildItem -LiteralPath $stage -Recurse -File -Force) {
            $entry = $file.FullName.Substring($stage.Length + 1).Replace('\', '/')
            $null = [IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $zip, $file.FullName, $entry, [IO.Compression.CompressionLevel]::Optimal)
        }
    } finally { $zip.Dispose() }
} finally {
    if (Test-Path -LiteralPath $stage) { Remove-Item -LiteralPath $stage -Recurse -Force }
}

$hash = (Get-FileHash -LiteralPath $zipPath -Algorithm SHA256).Hash.ToLowerInvariant()
$size = [math]::Round((Get-Item -LiteralPath $zipPath).Length / 1KB)
if ($dirty.Count -gt 0) { Write-Host 'build-booth: PREVIEW built from uncommitted changes' -ForegroundColor Yellow }
Write-Host "build-booth: $zipPath ($size KB, $($files.Count + 1) files)" -ForegroundColor Green
Write-Host "sha256: $hash"
