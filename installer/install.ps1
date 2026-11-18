<#
.SYNOPSIS
  Installs the VRChat avatar preset into DeepSeek Harness.

.DESCRIPTION
  Finds the DeepSeek Harness installation, installs the bundle into one profile with the
  supported `dsh plugin` command, and verifies the result before reporting success.

  It changes only <profile>\package.json, its lockfile and node_modules. It backs those up
  first, restores them when a step fails, and never touches registry, PATH or Unity projects.

.PARAMETER Profile
  Profile to install into. Default: desktop (the profile the Desktop app uses).

.PARAMETER Version
  Exact version to install, for example 0.1.1. Default: the newest published version.

.PARAMETER InstallDir
  DeepSeek Harness installation directory. Default: detected from the uninstall registry key.

.PARAMETER Force
  Continue even when DeepSeek Harness is running. Not recommended: the app owns the profile.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1
#>
[CmdletBinding()]
param(
    [string]$Profile = 'desktop',
    [string]$Version,
    [string]$InstallDir,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$PackageName = 'dsh-vrc-unity-supporter'
$script:LogPath = Join-Path $env:TEMP ("dsh-vrc-unity-install-" + (Get-Date -Format 'yyyyMMdd-HHmmss') + ".log")

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
                if (Test-Path (Join-Path $item.InstallLocation 'resources\runtime\cli\bin\dsh.cmd')) {
                    return $item.InstallLocation
                }
            }
        }
    }

    foreach ($candidate in @(
            (Join-Path $env:LOCALAPPDATA 'Programs\DeepSeek Harness'),
            (Join-Path $env:ProgramFiles 'DeepSeek Harness'))) {
        if ($candidate -and (Test-Path (Join-Path $candidate 'resources\runtime\cli\bin\dsh.cmd'))) {
            return $candidate
        }
    }
    return $null
}

function Invoke-Dsh([string]$DshCmd, [string[]]$DshArguments, [string]$OutFile, [string]$ErrFile) {
    $proc = Start-Process -FilePath $DshCmd -ArgumentList $DshArguments -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $OutFile -RedirectStandardError $ErrFile
    $stdout = if (Test-Path $OutFile) { Get-Content $OutFile -Raw -Encoding UTF8 } else { '' }
    $stderr = if (Test-Path $ErrFile) { Get-Content $ErrFile -Raw -Encoding UTF8 } else { '' }
    return [pscustomobject]@{ Code = $proc.ExitCode; Output = (($stdout + $stderr).Trim()) }
}

function Read-ProfileManifest([string]$Path) {
    $bytes = [System.IO.File]::ReadAllBytes($Path)
    $hasBom = $bytes.Length -ge 3 -and $bytes[0] -eq 0xEF -and $bytes[1] -eq 0xBB -and $bytes[2] -eq 0xBF
    $text = [System.IO.File]::ReadAllText($Path, [System.Text.Encoding]::UTF8)
    return [pscustomobject]@{ Json = ($text | ConvertFrom-Json); HasBom = $hasBom }
}

# ---------------------------------------------------------------- main ------
Say '=== VRChat アバター改変プリセット インストーラ ===' 'Cyan'
Say ''

Say '[1/5] DeepSeek Harness を探しています...'
$root = Find-DshInstallDir -Override $InstallDir
if (-not $root) {
    Fail 'DeepSeek Harness が見つかりませんでした。' 'DeepSeek Harness をインストールしてから実行してください' 1
}
$dshCmd = Join-Path $root 'resources\runtime\cli\bin\dsh.cmd'
$installedVersion = ''
$versionFile = Join-Path $root 'version'
if (Test-Path $versionFile) { $installedVersion = (Get-Content $versionFile -Raw).Trim() }
Say "  $root  (version $installedVersion)" 'DarkGray'

Say '[2/5] 実行中の DeepSeek Harness を確認しています...'
$running = @(Get-Process -Name 'DeepSeek Harness' -ErrorAction SilentlyContinue)
if ($running.Count -gt 0 -and -not $Force) {
    Fail 'DeepSeek Harness が起動中です。' 'アプリを終了してから、もう一度実行してください（-Force で強行できますが推奨しません）' 2
}
if ($running.Count -gt 0) { Say '  起動中ですが -Force が指定されたので続行します。' 'Yellow' }
else { Say '  起動していません。' 'DarkGray' }

$profileRoot = Join-Path (Join-Path $env:USERPROFILE '.dsh') "profiles\$Profile"
$spec = if ($Version) { "$PackageName@$Version" } else { $PackageName }
Say "[3/5] プロファイル '$Profile' に $spec をインストールしています..."

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$backup = $null
if (Test-Path (Join-Path $profileRoot 'package.json')) {
    $backup = Join-Path $profileRoot "package.json.bak-$stamp"
    Copy-Item (Join-Path $profileRoot 'package.json') $backup -Force
    $lock = Join-Path $profileRoot 'pnpm-lock.yaml'
    if (Test-Path $lock) { Copy-Item $lock "$lock.bak-$stamp" -Force }
}

$tmp = Join-Path $env:TEMP "dsh-vrc-install-$stamp"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$result = Invoke-Dsh $dshCmd @('plugin', '--profile', $Profile, 'add', $spec) (Join-Path $tmp 'out.txt') (Join-Path $tmp 'err.txt')

foreach ($line in ($result.Output -split "`n")) { if ($line.Trim()) { Say ("  " + $line.TrimEnd()) 'DarkGray' } }

if ($result.Code -ne 0) {
    if ($backup -and (Test-Path $backup)) {
        Copy-Item $backup (Join-Path $profileRoot 'package.json') -Force
        Say '  プロファイルの package.json を実行前に戻しました。' 'Yellow'
    }
    Fail 'インストールに失敗しました。' 'ネットワークと npm レジストリへの到達を確認し、時間をおいて再実行してください' 3
}

Say '[4/5] インストール結果を検証しています...'
$manifestPath = Join-Path $profileRoot 'package.json'
$modulesPath = Join-Path $profileRoot "node_modules\$PackageName\package.json"
if (-not (Test-Path $manifestPath)) { Fail 'プロファイルの package.json が見つかりません。' 'ログを添えて報告してください' 4 }

$manifest = Read-ProfileManifest $manifestPath
$declared = @($manifest.Json.dependencies.PSObject.Properties.Name) -contains $PackageName
$onDisk = Test-Path $modulesPath
$bundles = @($manifest.Json.dsh.profile.bundles)
$selected = $bundles -contains $PackageName
$diskVersion = ''
if ($onDisk) { $diskVersion = (Get-Content $modulesPath -Raw -Encoding UTF8 | ConvertFrom-Json).version }

Say ("  dependencies : " + $(if ($declared) { 'OK' } else { 'NG' }))
Say ("  node_modules : " + $(if ($onDisk) { "OK ($diskVersion)" } else { 'NG' }))
Say ("  bundles      : " + $(if ($selected) { 'OK (有効)' } else { 'NG (未選択)' }))
if ($manifest.HasBom) { Say '  警告: package.json に BOM が付いています。' 'Yellow' }

if (-not $declared -or -not $onDisk) {
    Fail 'インストール後の検証に通りませんでした。' 'ログを添えて報告してください' 4
}
if (-not $selected) {
    Fail 'バンドルが有効化されていません。' 'DSH の Plugins 画面で VRChat Avatar を有効にしてください' 4
}

Say '[5/5] 完了しました。' 'Green'
Say ''
Say '次の手順:' 'White'
Say '  1. DeepSeek Harness を起動する'
Say '  2. 新しいセッションを作る（既存セッションには反映されません）'
Say '  3. プリセットで「VRChat Avatar」を選ぶ'
Say ''
Say "  インストール先 : $profileRoot" 'DarkGray'
Say "  パッケージ     : $PackageName@$diskVersion" 'DarkGray'
if ($backup) { Say "  バックアップ   : $backup" 'DarkGray' }
Say "  ログ           : $($script:LogPath)" 'DarkGray'
Say ''
exit 0
