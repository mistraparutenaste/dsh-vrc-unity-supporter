<#
.SYNOPSIS
  Removes the VRChat avatar preset from DeepSeek Harness.

.DESCRIPTION
  Removes the bundle from one profile with the supported `dsh plugin` command and verifies
  that both the dependency and the bundle selection are gone. Unity projects are not touched.
#>
[CmdletBinding()]
param(
    [string]$Profile = 'desktop',
    [string]$InstallDir,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$PackageName = 'dsh-vrc-unity-supporter'
$script:LogPath = Join-Path $env:TEMP ("dsh-vrc-unity-uninstall-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + ".log")

function Say([string]$text, [string]$color = 'Gray') {
    Write-Host $text -ForegroundColor $color
    try { Add-Content -LiteralPath $script:LogPath -Value $text -Encoding UTF8 } catch { }
}

function Fail([string]$text, [string]$hint, [int]$code) {
    Say ''
    Say "失敗: $text" 'Red'
    if ($hint) { Say "対処: $hint" 'Yellow' }
    Say ''
    Say "ログ: $($script:LogPath)" 'DarkGray'
    exit $code
}

function Find-DshInstallDir {
    param([string]$Override)
    if ($Override) {
        if (Test-Path (Join-Path $Override 'resources\runtime\cli\bin\dsh.cmd')) { return $Override }
        return $null
    }
    foreach ($key in @(
            'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
            'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
            'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*')) {
        foreach ($item in Get-ItemProperty $key -ErrorAction SilentlyContinue) {
            if ($item.DisplayName -like '*DeepSeek Harness*' -and $item.InstallLocation) {
                if (Test-Path (Join-Path $item.InstallLocation 'resources\runtime\cli\bin\dsh.cmd')) { return $item.InstallLocation }
            }
        }
    }
    foreach ($candidate in @(
            (Join-Path $env:LOCALAPPDATA 'Programs\DeepSeek Harness'),
            (Join-Path $env:ProgramFiles 'DeepSeek Harness'))) {
        if ($candidate -and (Test-Path (Join-Path $candidate 'resources\runtime\cli\bin\dsh.cmd'))) { return $candidate }
    }
    return $null
}

Say '=== VRChat アバター改変プリセット アンインストーラ ===' 'Cyan'
Say ''

$root = Find-DshInstallDir -Override $InstallDir
if (-not $root) { Fail 'DeepSeek Harness が見つかりませんでした。' 'インストール先を -InstallDir で指定してください' 1 }
$dshCmd = Join-Path $root 'resources\runtime\cli\bin\dsh.cmd'

$running = @(Get-Process -Name 'DeepSeek Harness' -ErrorAction SilentlyContinue)
if ($running.Count -gt 0 -and -not $Force) {
    Fail 'DeepSeek Harness が起動中です。' 'アプリを終了してから、もう一度実行してください' 2
}

$profileRoot = Join-Path (Join-Path $env:USERPROFILE '.dsh') "profiles\$Profile"
$manifestPath = Join-Path $profileRoot 'package.json'
if (-not (Test-Path $manifestPath)) {
    Say "プロファイル '$Profile' が存在しません。削除するものはありません。" 'Yellow'
    exit 0
}

$manifest = Get-Content $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$declared = @($manifest.dependencies.PSObject.Properties.Name) -contains $PackageName
if (-not $declared) {
    Say "$PackageName はインストールされていません。" 'Yellow'
    exit 0
}

Say "[1/3] プロファイル '$Profile' から削除しています..."
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = Join-Path $profileRoot "package.json.bak-$stamp"
Copy-Item $manifestPath $backup -Force

$tmp = Join-Path $env:TEMP "dsh-vrc-uninstall-$stamp"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$proc = Start-Process -FilePath $dshCmd -ArgumentList @('plugin', '--profile', $Profile, 'remove', $PackageName) `
    -NoNewWindow -Wait -PassThru -RedirectStandardOutput (Join-Path $tmp 'out.txt') -RedirectStandardError (Join-Path $tmp 'err.txt')
$out = (Get-Content (Join-Path $tmp 'out.txt') -Raw -Encoding UTF8) + (Get-Content (Join-Path $tmp 'err.txt') -Raw -Encoding UTF8)
foreach ($line in ($out -split "`n")) { if ($line.Trim()) { Say ("  " + $line.TrimEnd()) 'DarkGray' } }

if ($proc.ExitCode -ne 0) {
    Copy-Item $backup $manifestPath -Force
    Fail '削除に失敗しました。' 'ログを添えて報告してください' 3
}

Say '[2/3] 検証しています...'
$after = Get-Content $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$stillDeclared = @($after.dependencies.PSObject.Properties.Name) -contains $PackageName
$stillSelected = @($after.dsh.profile.bundles) -contains $PackageName
$onDisk = Test-Path (Join-Path $profileRoot "node_modules\$PackageName")
Say ("  dependencies : " + $(if ($stillDeclared) { 'NG (残っています)' } else { 'OK' }))
Say ("  bundles      : " + $(if ($stillSelected) { 'NG (残っています)' } else { 'OK' }))
Say ("  node_modules : " + $(if ($onDisk) { '残っています' } else { 'OK' }))

if ($stillDeclared -or $stillSelected) {
    Fail '削除後の検証に通りませんでした。' 'DSH の Plugins 画面から削除するか、ログを添えて報告してください' 4
}

Say '[3/3] 完了しました。' 'Green'
Say ''
Say "  バックアップ : $backup" 'DarkGray'
Say "  ログ         : $($script:LogPath)" 'DarkGray'
Say ''
exit 0
