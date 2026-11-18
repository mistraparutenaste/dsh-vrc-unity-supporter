<#
.SYNOPSIS
  Publishes this bundle to npm and pushes it to GitHub.

.DESCRIPTION
  Runs the pre-flight checks, then publishes and pushes. It stops before doing anything
  irreversible when a prerequisite is missing, so it is safe to run at any time.

  Requires an authenticated npm session (`npm login`) and GitHub CLI (`gh auth login`).

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File publish.ps1 -DryRun
  powershell -NoProfile -ExecutionPolicy Bypass -File publish.ps1 -Owner your-github-name
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [string]$Owner,
    [string]$PackageName = 'dsh-vrc-unity-supporter',
    [string]$Token,
    [string]$Otp
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

# A token (granular access token with 2FA bypass) makes publishing non-interactive.
# It is only set for this process and never printed.
if ($Token) { $env:NODE_AUTH_TOKEN = $Token }
$usingToken = [bool]($Token -or $env:NODE_AUTH_TOKEN -or $env:NPM_TOKEN)
if (-not $env:NODE_AUTH_TOKEN -and $env:NPM_TOKEN) { $env:NODE_AUTH_TOKEN = $env:NPM_TOKEN }

function Step([string]$text) { Write-Host "== $text" -ForegroundColor Cyan }

function Stop-WithHelp([string]$text, [string]$command) {
    Write-Host "STOP: $text" -ForegroundColor Red
    Write-Host "      実行してください: $command" -ForegroundColor Yellow
    exit 2
}

# Native tools write progress and notices to stderr; under `Stop` PowerShell turns that into
# a terminating error. Run them through cmd so only the exit code matters.
function Invoke-Native([string]$commandLine) {
    $previous = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    $output = & cmd /c "$commandLine 2>&1"
    $code = $LASTEXITCODE
    $ErrorActionPreference = $previous
    return [pscustomobject]@{ Output = (($output | Out-String).Trim()); Code = $code }
}

# --- 1. pre-flight -----------------------------------------------------------
Step 'verify-package'
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot 'verify-package.ps1')
if ($LASTEXITCODE -ne 0) { Stop-WithHelp 'パッケージ検査に失敗しました' 'verify-package.ps1 の出力を確認' }

$manifest = Get-Content (Join-Path $root 'package.json') -Raw -Encoding UTF8 | ConvertFrom-Json
$version = $manifest.version
Write-Host "   package: $PackageName@$version"

Step 'pack contents'
$pack = Invoke-Native 'npm pack --dry-run'
if ($pack.Code -ne 0) { Stop-WithHelp 'npm pack に失敗しました' 'npm pack --dry-run' }
$fileLine = ($pack.Output -split "`n" | Where-Object { $_ -match 'total files' } | Select-Object -First 1)
Write-Host ("   " + ($fileLine -replace '\s+', ' ').Trim())

# --- 2. credentials ----------------------------------------------------------
Step 'credentials'
$who = Invoke-Native 'npm whoami'
if ($who.Code -ne 0 -or -not $who.Output) {
    if ($usingToken) {
        Write-Host '   npm: トークンで認証（whoami はスキップ）' -ForegroundColor DarkGray
    } else {
        Stop-WithHelp 'npm にログインしていません' 'npm login（または -Token でトークンを渡す）'
    }
} else {
    Write-Host "   npm user: $($who.Output)"
}

$ghStatus = Invoke-Native 'gh auth status'
if ($ghStatus.Code -ne 0) { Stop-WithHelp 'GitHub CLI が未ログインです' 'gh auth login' }
$ghUser = (Invoke-Native 'gh api user --jq .login').Output
Write-Host "   gh user : $ghUser"

if (-not $Owner) { $Owner = $ghUser }
if (-not $Owner) { Stop-WithHelp 'GitHub の owner が決まりません' 'publish.ps1 -Owner <name>' }

# --- 3. publish to npm -------------------------------------------------------
Step 'npm publish'
$view = Invoke-Native "npm view $PackageName@$version version"
if ($view.Code -eq 0 -and $view.Output) {
    Write-Host "   既に公開済み: $PackageName@$($view.Output) (skip)" -ForegroundColor DarkGray
} elseif ($DryRun) {
    Write-Host '   [dry-run] npm publish --access public'
} else {
    # A token must be passed as the registry auth flag; NODE_AUTH_TOKEN alone is not used by
    # `npm publish` on this npm version, even though `npm whoami` honours it.
    $publishCommand = 'npm publish --access public'
    if ($env:NODE_AUTH_TOKEN) { $publishCommand += " --//registry.npmjs.org/:_authToken=$($env:NODE_AUTH_TOKEN)" }
    if ($Otp) { $publishCommand += " --otp=$Otp" }
    $pub = Invoke-Native $publishCommand
    $shown = $pub.Output -replace 'npm_[A-Za-z0-9]+', 'npm_***'
    Write-Host $shown
    if ($pub.Code -ne 0) { Stop-WithHelp 'npm publish に失敗しました' 'npm publish --access public（トークンは --//registry.npmjs.org/:_authToken= で渡す）' }
}

# --- 4. push to GitHub -------------------------------------------------------
Step 'git remote'
$remote = Invoke-Native 'git remote get-url origin'
if ($remote.Code -eq 0 -and $remote.Output) {
    Write-Host "   既存の remote: $($remote.Output)"
} elseif ($DryRun) {
    Write-Host "   [dry-run] gh repo create $PackageName --public --source=. --remote=origin --push"
} else {
    $create = Invoke-Native "gh repo create $PackageName --public --source=. --remote=origin --push"
    Write-Host $create.Output
    if ($create.Code -ne 0) { Stop-WithHelp 'リポジトリ作成に失敗しました' "gh repo create $PackageName --public --source=. --remote=origin --push" }
}

Step 'push + tag'
if ($DryRun) {
    Write-Host '   [dry-run] git push -u origin HEAD'
    Write-Host "   [dry-run] git tag v$version && git push origin v$version"
} else {
    if ((-Invoke-Native 'git remote get-url origin').Code -eq 0) {
        $push = Invoke-Native 'git push -u origin HEAD'
        if ($push.Code -ne 0) { Stop-WithHelp 'push に失敗しました' 'git push -u origin HEAD' }
    }
    if (-not (& git tag -l "v$version")) { & git tag "v$version" }
    $tagPush = Invoke-Native "git push origin v$version"
    if ($tagPush.Code -ne 0) { Write-Host '   タグは既に push 済みかもしれません' -ForegroundColor Yellow }
}

Write-Host ''
Write-Host "完了: https://github.com/$Owner/$PackageName" -ForegroundColor Green
Write-Host "npm : https://www.npmjs.com/package/$PackageName" -ForegroundColor Green
