<#
.SYNOPSIS
  Runs one Unity Editor method in batch mode against a project.

.DESCRIPTION
  Resolves the editor from ProjectSettings/ProjectVersion.txt, refuses to run while the Unity
  editor has the project open, runs -executeMethod, and summarises compiler errors from the log.

.EXAMPLE
  powershell -NoProfile -ExecutionPolicy Bypass -File unity-run.ps1 -Project "C:\proj" -Method "DSH.Editor.DshInspect.CompileCheck"
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Project,
    [Parameter(Mandatory)][string]$Method,
    [int]$TimeoutSec = 1800,
    [switch]$AllowGraphics,
    [string]$Name = 'unity'
)

$ErrorActionPreference = 'Stop'

function Find-Editor([string]$version) {
    if ($env:UNITY_EDITOR_PATH -and (Test-Path $env:UNITY_EDITOR_PATH)) {
        return (Resolve-Path $env:UNITY_EDITOR_PATH).Path
    }
    $bases = @()
    $bases += (Join-Path $env:ProgramFiles 'Unity\Hub\Editor')
    $bases += 'D:\Unity\Hub\Editor'
    $bases += 'E:\Unity\Hub\Editor'
    foreach ($base in $bases) {
        if (-not $base) { continue }
        $candidate = Join-Path $base "$version\Editor\Unity.exe"
        if (Test-Path $candidate) { return $candidate }
    }
    return $null
}

function Quote-Argument([string]$value) {
    if ($value -match '[\s"]') { return '"' + ($value -replace '"', '\"') + '"' }
    return $value
}

if (-not (Test-Path $Project)) { throw "project not found: $Project" }
$proj = (Resolve-Path $Project).Path

$versionFile = Join-Path $proj 'ProjectSettings\ProjectVersion.txt'
if (-not (Test-Path $versionFile)) { throw "not a Unity project (no ProjectVersion.txt): $proj" }
$version = ((Get-Content $versionFile | Where-Object { $_ -match '^m_EditorVersion:' } | Select-Object -First 1) -split ':', 2)[1].Trim()

$editor = Find-Editor $version
if (-not $editor) {
    throw "Unity $version not found. Install it with Unity Hub, or set UNITY_EDITOR_PATH."
}

$lockFile = Join-Path $proj 'Temp\UnityLockfile'
if (Test-Path $lockFile) {
    # A batchmode run can leave the lockfile behind; only a live pid blocks us.
    $instance = Join-Path $proj 'Library\EditorInstance.json'
    $alive = $false
    if (Test-Path $instance) {
        try {
            $info = Get-Content $instance -Raw -Encoding UTF8 | ConvertFrom-Json
            $editorPid = [int]$info.process_id
            if ($editorPid -gt 0) {
                $alive = $null -ne (Get-Process -Id $editorPid -ErrorAction SilentlyContinue)
            }
        } catch {
            $alive = $true   # unreadable instance file: be conservative
        }
    }
    if ($alive) {
        throw "Unity is holding this project open (pid $editorPid). Close the editor and retry."
    }
    Write-Host 'note   : stale Temp/UnityLockfile found; continuing' -ForegroundColor Yellow
}

$logDir = Join-Path $proj '.dsh\logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$log = Join-Path $logDir "$Name-$stamp.log"

$arguments = @('-nographics', '-batchmode', '-quit',
    '-projectPath', $proj,
    '-executeMethod', $Method,
    '-logFile', $log)
if ($AllowGraphics) { $arguments = $arguments | Where-Object { $_ -ne '-nographics' } }

Write-Host "editor : $editor" -ForegroundColor DarkGray
Write-Host "project: $proj" -ForegroundColor DarkGray
Write-Host "method : $Method" -ForegroundColor DarkGray
Write-Host "log    : $log" -ForegroundColor DarkGray

$started = Get-Date
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $editor
$psi.Arguments = ($arguments | ForEach-Object { Quote-Argument $_ }) -join ' '
$psi.UseShellExecute = $false
$psi.WorkingDirectory = $proj

$proc = New-Object System.Diagnostics.Process
$proc.StartInfo = $psi
$null = $proc.Start()

$sw = [System.Diagnostics.Stopwatch]::StartNew()
if (-not $proc.WaitForExit($TimeoutSec * 1000)) {
    try { $proc.Kill() } catch { }
    Write-Host "TIMEOUT after $TimeoutSec s (log: $log)" -ForegroundColor Red
    exit 124
}
$proc.WaitForExit()
$sw.Stop()
$code = [int]$proc.ExitCode

$text = ''
if (Test-Path $log) { $text = Get-Content $log -Raw -Encoding UTF8 }
$errors = @()
if ($text) {
    $errors = @([regex]::Matches($text, '(?m)^.*(error CS\d+|Exception:|Aborting batchmode|No valid Unity Editor license|could not be found).*$') |
        ForEach-Object { $_.Value.Trim() } | Select-Object -Unique)
}

# Show the result JSON only when this run produced it.
$resultsDir = Join-Path $proj 'Assets\DSH\Results'
if (Test-Path $resultsDir) {
    $latest = Get-ChildItem $resultsDir -Filter *.json -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($latest -and $latest.LastWriteTime -ge $started) {
        Write-Host ("result : " + $latest.FullName) -ForegroundColor DarkGray
        Get-Content $latest.FullName -Raw -Encoding UTF8 | Write-Host
    }
}

Write-Host ("exit   : {0}  ({1:N1}s)" -f $code, $sw.Elapsed.TotalSeconds) -ForegroundColor $(if ($code -eq 0) { 'Green' } else { 'Red' })
if ($code -ne 0 -and $errors.Count -gt 0) {
    Write-Host '--- errors ---' -ForegroundColor Yellow
    $errors | Select-Object -First 15 | ForEach-Object { Write-Host $_ }
} elseif ($errors.Count -gt 0) {
    Write-Host ("note   : log had {0} recoverable compile message(s) from a previous import" -f $errors.Count) -ForegroundColor DarkGray
}
exit $code
