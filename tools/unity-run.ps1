<#
.SYNOPSIS
  Runs one Unity Editor method and validates its result for this invocation.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$Project,
    [Parameter(Mandatory)][ValidatePattern('^[\w.]+$')][string]$Method,
    [ValidateRange(1,86400)][int]$TimeoutSec = 1800,
    [switch]$AllowGraphics,
    [ValidatePattern('^[\w.-]+$')][string]$Name = 'unity',
    [ValidatePattern('^[a-f0-9]{32}$')][string]$RunId = [guid]::NewGuid().ToString('N'),
    [string]$RequestFile,
    [string]$ExpectedTask,
    [switch]$AllowMissingResult,
    [switch]$InstallOutfitHelpers
)

$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
. (Join-Path $PSScriptRoot 'unity-environment.ps1')

function Quote-Argument([string]$Value) {
    if ($Value -match '[\s"]') {
        return '"' + (($Value -replace '(\\*)"', '$1$1\"') -replace '(\\+)$', '$1$1') + '"'
    }
    return $Value
}

function Install-OutfitHelpers([string]$ProjectPath, [string]$RequestPath) {
    $request = Get-Content -LiteralPath $RequestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $destDir = Join-Path $ProjectPath 'Assets\DSH\Editor'
    $sourceDir = Join-Path (Split-Path -Parent $PSScriptRoot) 'templates\Editor'
    $copies = foreach ($helper in $request.helpers) {
        if ($helper.file -cnotin @('DshApply.cs', 'DshInspect.cs', 'DshOutfitToggle.cs', 'DshTextureVariant.cs', 'DshCapture.cs', 'DshAvatarTools.cs', 'DshShape.cs', 'DshAccessory.cs', 'DshDynamics.cs', 'DshParameters.cs', 'DshPhysBone.cs', 'DshProportion.cs', 'DshExpression.cs', 'DshMigrate.cs')) {
            throw "Unknown DSH helper: $($helper.file)"
        }
        $dest = Join-Path $destDir $helper.file
        $before = if (Test-Path -LiteralPath $dest -PathType Leaf) {
            $sha = [Security.Cryptography.SHA256]::Create()
            try {
                [BitConverter]::ToString($sha.ComputeHash([IO.File]::ReadAllBytes($dest))).Replace('-', '')
            } finally {
                $sha.Dispose()
            }
        }
        if ($before -ne $helper.before) { throw "Helper changed after preview: $dest" }
        [pscustomobject]@{ Source = (Join-Path $sourceDir $helper.file); Destination = $dest; New = $null -eq $before }
    }
    if ($copies) { New-Item -ItemType Directory -Force -Path $destDir | Out-Null }
    foreach ($copy in $copies) { [IO.File]::Copy($copy.Source, $copy.Destination, -not $copy.New) }
}

$proj = (Resolve-Path -LiteralPath $Project).Path
$version = Get-DshUnityVersion $proj
if (-not $version) { throw "Unity project version could not be read: $proj" }
$editor = Find-DshUnityEditor $version
if (-not $editor) { throw "Unity $version not found. Install it with Unity Hub, or set UNITY_EDITOR_PATH." }
if ((Get-DshUnityLock $proj) -ne 'clear') {
    throw "Unity may have this project open. Close the editor for this project, then retry."
}
if ($RequestFile) { $RequestFile = (Resolve-Path -LiteralPath $RequestFile).Path }

$runRoot = Join-Path $proj '.dsh\runs'
New-Item -ItemType Directory -Force -Path $runRoot | Out-Null
$lockPath = Join-Path $runRoot 'unity.lock'
try {
    $lock = [IO.File]::Open($lockPath, [IO.FileMode]::OpenOrCreate, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
} catch [IO.IOException] {
    throw "Another DSH Unity run may be active for this project. Wait for it and retry."
}
try {
    if ((Get-DshUnityLock $proj) -ne 'clear') {
        throw "Unity may have this project open. Close the editor for this project, then retry."
    }
    if ($InstallOutfitHelpers) { Install-OutfitHelpers $proj $RequestFile }
    $runDir = Join-Path $runRoot $RunId
    New-Item -ItemType Directory -Path $runDir | Out-Null
    $log = Join-Path $runDir "$Name.log"
    $resultPath = Join-Path $runDir 'result.json'

    $arguments = @('-batchmode', '-quit', '-projectPath', $proj,
        '-executeMethod', $Method, '-logFile', $log)
    if (-not $AllowGraphics) { $arguments = @('-nographics') + $arguments }

    Write-Host "project: $proj"
    Write-Host "editor : $editor"
    Write-Host "method : $Method"
    Write-Host "log    : $log"

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $editor
    $psi.Arguments = ($arguments | ForEach-Object { Quote-Argument $_ }) -join ' '
    $psi.UseShellExecute = $false
    $psi.WorkingDirectory = $proj
    $psi.EnvironmentVariables['DSH_UNITY_RESULT_PATH'] = $resultPath
    $psi.EnvironmentVariables.Remove('DSH_UNITY_REQUEST_PATH')
    if ($RequestFile) { $psi.EnvironmentVariables['DSH_UNITY_REQUEST_PATH'] = $RequestFile }

    $proc = [Diagnostics.Process]::Start($psi)
    try {
        if (-not $proc.WaitForExit($TimeoutSec * 1000)) {
            try { $proc.Kill() } catch [InvalidOperationException] { }
            $null = $proc.WaitForExit(5000)
            Write-Host "TIMEOUT after $TimeoutSec s (log: $log)"
            exit 124
        }
        $code = $proc.ExitCode
    } finally {
        $proc.Dispose()
    }

    $hasResult = Test-Path -LiteralPath $resultPath -PathType Leaf
    if ($hasResult) {
        Write-Host "result : $resultPath"
        try {
            $result = Get-Content -LiteralPath $resultPath -Raw -Encoding UTF8 | ConvertFrom-Json
            if ($result -isnot [pscustomobject] -or $result.ok -isnot [bool] -or
                $result.task -isnot [string] -or -not $result.task -or
                ($ExpectedTask -and $result.task -cne $ExpectedTask)) {
                throw 'Unity result has the wrong task or a missing boolean ok field.'
            }
            if (-not $result.ok) {
                Write-Host "Unity task failed: $($result.error)"
                if ($code -eq 0) { $code = 1 }
            }
        } catch {
            Write-Host "Invalid Unity result: $_"
            if ($code -eq 0) { $code = 1 }
        }
    } elseif (-not $AllowMissingResult -and $code -eq 0) {
        Write-Host 'Unity exited without a result for this run. Check the log and install current DSH Editor helpers.'
        $code = 1
    }
    if ($code -ne 0 -and (Test-Path -LiteralPath $log -PathType Leaf)) {
        Select-String -LiteralPath $log -Encoding UTF8 -Pattern 'error CS\d+|Exception:|Aborting batchmode|No valid Unity Editor license|IPC channel to LicensingClient|could not be found' |
            Select-Object -First 15 | ForEach-Object { Write-Host $_.Line.Trim() }
    }
    Write-Host "exit   : $code"
    exit $code
} finally {
    $lock.Dispose()
}
