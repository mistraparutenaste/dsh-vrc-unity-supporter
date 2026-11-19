<#
.SYNOPSIS
  Checks the package before publishing. Run this instead of trusting a green build.

.DESCRIPTION
  Verifies the things that silently break this package:
  - every .ps1 is UTF-8 with BOM (Windows PowerShell 5.1 misreads BOM-less Japanese)
  - each skills/<dir>/SKILL.md declares the same name as its directory
  - required runtime files exist
  - package.json and locale files parse
  - the plan-mode plugin declares non-empty guidance

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File verify-package.ps1
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$problems = [System.Collections.Generic.List[string]]::new()

$required = @(
    'package.json', 'cordis.patch.yml', 'icon.svg', 'README.md', 'LICENSE',
    'locale/en.json', 'locale/ja.json',
    'docs/DETAIL.md', 'docs/DETAIL.ja.md', 'docs/preview.svg',
    'templates/Editor/DshApply.cs', 'templates/Editor/DshInspect.cs',
    'templates/Editor/DshOutfitToggle.cs', 'skills/vrc-first-run/SKILL.md',
    'templates/AGENTS.template.md', 'templates/gitignore.template',
    'tools/doctor.ps1', 'tools/unity-run.ps1', 'tools/unity_inspect.py',
    'tools/unity-environment.ps1', 'tools/unity_toggle.py',
    'install.cmd',
    'installer/install.cmd', 'installer/install.ps1',
    'installer/uninstall.cmd', 'installer/uninstall.ps1',
    'installer/README.md'
)
foreach ($rel in $required) {
    if (-not (Test-Path (Join-Path $root $rel))) { $problems.Add("missing: $rel") }
}

# 1. UTF-8 BOM on every .ps1
foreach ($ps1 in Get-ChildItem $root -Filter *.ps1 -Recurse) {
    $bytes = [System.IO.File]::ReadAllBytes($ps1.FullName)
    $hasBom = $bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF
    if (-not $hasBom) {
        $problems.Add("no UTF-8 BOM (Windows PowerShell will misparse Japanese): $($ps1.Name)")
    }
}

# 2. skill directory names must match the SKILL.md name
$skillsDir = Join-Path $root 'skills'
foreach ($dir in Get-ChildItem $skillsDir -Directory) {
    $skill = Join-Path $dir.FullName 'SKILL.md'
    if (-not (Test-Path $skill)) { $problems.Add("missing SKILL.md in $($dir.Name)"); continue }
    $head = (Get-Content $skill -TotalCount 6 -Encoding UTF8) -join "`n"
    if ($head -notmatch "(?m)^name:\s*$([regex]::Escape($dir.Name))\s*$") {
        $problems.Add("SKILL.md name does not match directory: $($dir.Name)")
    }
}

# 3. JSON parses, and carries no UTF-8 BOM (a BOM breaks JSON.parse in the Host)
$jsonFiles = Get-ChildItem $root -Recurse -Include *.json -File |
    Where-Object { $_.FullName -notmatch '\\(node_modules|\.git)\\' }
foreach ($jsonFile in $jsonFiles) {
    $bytes = [System.IO.File]::ReadAllBytes($jsonFile.FullName)
    $rel = $jsonFile.FullName.Replace($root, '').TrimStart('\')
    if ($bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF) {
        $problems.Add("JSON has a UTF-8 BOM (the Host cannot parse it): $rel")
        continue
    }
    try { $null = Get-Content $jsonFile.FullName -Raw -Encoding UTF8 | ConvertFrom-Json }
    catch { $problems.Add("invalid JSON: $rel") }
}

# 4. the bundle declares a patch and an icon export
$pkgJson = Get-Content (Join-Path $root 'package.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if (-not $pkgJson.dsh.bundle.patch) { $problems.Add('package.json: dsh.bundle.patch is missing') }
if (-not $pkgJson.exports.'./package.json') { $problems.Add('package.json: exports["./package.json"] is required for the skills path') }

# 5. no Python bytecode or editor junk gets packed
$junk = @()
$junk += Get-ChildItem $root -Recurse -Force -Filter *.pyc -ErrorAction SilentlyContinue
$junk += Get-ChildItem $root -Recurse -Force -Directory -Filter __pycache__ -ErrorAction SilentlyContinue
$junk += Get-ChildItem $root -Recurse -Force -Filter .DS_Store -ErrorAction SilentlyContinue
foreach ($item in $junk) {
    $problems.Add("stray build artifact: $($item.FullName.Replace($root, '').TrimStart('\'))")
}

# 6. .cmd files must be ASCII-only: cmd.exe decodes a batch file with the active code page,
#    so a UTF-8 Japanese line can be split into broken commands.
foreach ($cmd in Get-ChildItem $root -Recurse -Filter *.cmd -File | Where-Object { $_.FullName -notmatch '\\node_modules\\' }) {
    $bytes = [System.IO.File]::ReadAllBytes($cmd.FullName)
    if (@($bytes | Where-Object { $_ -gt 0x7F }).Count -gt 0) {
        $problems.Add("non-ASCII bytes in a .cmd (cmd.exe will misparse it): $($cmd.Name)")
    }
}

# 7. DSH rejects the preset if plan-mode has no guidance text in config.section.
$patchPath = Join-Path $root 'cordis.patch.yml'
if (Test-Path $patchPath -PathType Leaf) {
    $patch = Get-Content $patchPath -Raw -Encoding UTF8
    $planSection = '(?m)^(?<indent> *)name: ''@deepseek-ai/dsh-plan-mode''[ \t]*\r?\n' +
        '\k<indent>config:[ \t]*\r?\n' +
        '\k<indent>  section: \|[ \t]*\r?\n' +
        '(?:[ \t]*\r?\n)*\k<indent>    [ \t]*\S'
    if ($patch -cnotmatch $planSection) {
        $problems.Add('cordis.patch.yml: plan-mode requires a non-empty config.section block')
    }
}

if ($problems.Count -eq 0) {
    Write-Host 'verify-package: OK' -ForegroundColor Green
    exit 0
}
Write-Host "verify-package: $($problems.Count) problem(s)" -ForegroundColor Red
$problems | ForEach-Object { Write-Host "  - $_" }
exit 1
