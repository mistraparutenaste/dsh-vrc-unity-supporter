<#
.SYNOPSIS
  Checks the prerequisites this preset assumes. Reports PASS / WARN / FAIL and never changes anything.

.EXAMPLE
  ./doctor.ps1 -Project "C:\Users\me\ALCOM\Projects\myAvatar"
#>
[CmdletBinding()]
param(
    [string]$Project
)

$ErrorActionPreference = 'Stop'
$results = [System.Collections.Generic.List[object]]::new()

function Add-Check {
    param([string]$Name, [string]$Status, [string]$Detail)
    $results.Add([pscustomobject]@{ Name = $Name; Status = $Status; Detail = $Detail })
}

$pkgRoot = Split-Path -Parent $PSScriptRoot
Add-Check 'package' 'PASS' $pkgRoot

# --- DSH presence -----------------------------------------------------------
if ($env:DSH_PROFILE) {
    Add-Check 'dsh profile' 'PASS' "$env:DSH_PROFILE  ($env:DSH_PROFILE_DIR)"
} else {
    Add-Check 'dsh profile' 'WARN' 'DSH_PROFILE is not set (running outside a dsh-launched shell?)'
}

# --- Unity Hub / editors ----------------------------------------------------
$hub = Join-Path $env:ProgramFiles 'Unity Hub\Unity Hub.exe'
if (Test-Path $hub) {
    Add-Check 'unity hub' 'PASS' $hub
} else {
    Add-Check 'unity hub' 'FAIL' 'Unity Hub が見つかりません'
}

$editors = @()
$editorBases = @()
$editorBases += (Join-Path $env:ProgramFiles 'Unity\Hub\Editor')
$editorBases += 'D:\Unity\Hub\Editor'
$editorBases += 'E:\Unity\Hub\Editor'
foreach ($base in $editorBases) {
    if ($base -and (Test-Path $base)) {
        $editors += Get-ChildItem $base -Directory -ErrorAction SilentlyContinue
    }
}
if ($editors.Count -gt 0) {
    Add-Check 'unity editors' 'PASS' (($editors | ForEach-Object { $_.Name }) -join ', ')
} else {
    Add-Check 'unity editors' 'FAIL' 'Unity Editor が見つかりません'
}

# --- licence ----------------------------------------------------------------
$lic = Join-Path $env:LOCALAPPDATA 'Unity\licenses'
if (Test-Path $lic) {
    Add-Check 'unity licence' 'PASS' $lic
} else {
    Add-Check 'unity licence' 'FAIL' 'ライセンスが未認証です。Unity Hub でサインインしてください（バッチモードが動きません）'
}

# --- VCC / ALCOM ------------------------------------------------------------
$vcc = Join-Path $env:LOCALAPPDATA 'VRChatCreatorCompanion'
$alcom = Join-Path $env:LOCALAPPDATA 'Programs\ALCOM'
$hasVcc = Test-Path $vcc
$hasAlcom = Test-Path $alcom
if ($hasVcc -or $hasAlcom) {
    $clients = @()
    if ($hasVcc) { $clients += 'VCC' }
    if ($hasAlcom) { $clients += 'ALCOM' }
    Add-Check 'vpm client' 'PASS' ($clients -join ' + ')
} else {
    Add-Check 'vpm client' 'FAIL' 'VCC も ALCOM も見つかりません'
}

# --- vrc-get (optional) -----------------------------------------------------
$vrcGet = Get-Command vrc-get -ErrorAction SilentlyContinue
if ($vrcGet) {
    $ver = (& vrc-get --version 2>$null | Select-Object -First 1)
    Add-Check 'vrc-get' 'PASS' "$($vrcGet.Source)  $ver"
} else {
    Add-Check 'vrc-get' 'WARN' '未導入（任意）。パッケージ操作は GUI 手順になります'
}

# --- project checks ---------------------------------------------------------
if ($Project) {
    if (-not (Test-Path $Project)) {
        Add-Check 'project' 'FAIL' "パスが存在しません: $Project"
    } else {
        $proj = (Resolve-Path $Project).Path
        Add-Check 'project' 'PASS' $proj

        $versionFile = Join-Path $proj 'ProjectSettings\ProjectVersion.txt'
        if (Test-Path $versionFile) {
            $line = (Get-Content $versionFile | Where-Object { $_ -match '^m_EditorVersion:' } | Select-Object -First 1)
            $ver = ($line -split ':', 2)[1].Trim()
            Add-Check 'project unity' 'PASS' $ver
            if ($ver -ne '2022.3.22f1') {
                Add-Check 'project unity' 'WARN' "VRChat の現在の対応版は 2022.3.22f1 です（検出: $ver）"
            }
            $exe = $null
            foreach ($e in $editors) {
                if ($e.Name -eq $ver) {
                    $candidate = Join-Path $e.FullName 'Editor\Unity.exe'
                    if (Test-Path $candidate) { $exe = $candidate }
                }
            }
            if ($exe) {
                Add-Check 'editor for project' 'PASS' $exe
            } else {
                Add-Check 'editor for project' 'FAIL' "$ver の Editor が見つかりません（Unity Hub で追加してください）"
            }
        } else {
            Add-Check 'project unity' 'FAIL' 'ProjectVersion.txt がありません'
        }

        # VPM packages can live in manifest.json (VCC/ALCOM), vpm-manifest.json (legacy
        # vrc-get) or as packages embedded under Packages/<id>/package.json.
        $vpmPkgs = [ordered]@{}
        foreach ($mf in @('manifest.json', 'vpm-manifest.json')) {
            $mp = Join-Path $proj "Packages\$mf"
            if (Test-Path $mp) {
                try {
                    $json = Get-Content $mp -Raw -Encoding UTF8 | ConvertFrom-Json
                    foreach ($prop in $json.dependencies.PSObject.Properties) {
                        if ($prop.Name -like 'com.unity.*') { continue }
                        $val = $prop.Value
                        $ver = if ($val -is [string]) { $val } elseif ($val.version) { [string]$val.version } else { '' }
                        $vpmPkgs[$prop.Name] = $ver
                    }
                } catch { }
            }
        }
        foreach ($dir in @(Get-ChildItem (Join-Path $proj 'Packages') -Directory -ErrorAction SilentlyContinue)) {
            $pkgJson = Join-Path $dir.FullName 'package.json'
            if (Test-Path $pkgJson) {
                try {
                    $meta = Get-Content $pkgJson -Raw -Encoding UTF8 | ConvertFrom-Json
                    if ($meta.name -and $meta.name -notlike 'com.unity.*' -and -not $vpmPkgs.Contains($meta.name)) {
                        $vpmPkgs[$meta.name] = [string]$meta.version
                    }
                } catch { }
            }
        }
        $vpmList = @($vpmPkgs.Keys | ForEach-Object { "$_@$($vpmPkgs[$_])" })
        if ($vpmList.Count -gt 0) {
            Add-Check 'project vpm packages' 'PASS' (($vpmList | Select-Object -First 6) -join ', ')
        } else {
            Add-Check 'project vpm packages' 'FAIL' 'VPM パッケージがありません（このプリセットは既存の VRChat プロジェクトを前提にしています）'
        }

        $lockNames = @('vpm-lock.json', 'vpm-manifest.json')
        $foundLock = $null
        foreach ($ln in $lockNames) {
            if (Test-Path (Join-Path $proj "Packages\$ln")) { $foundLock = $ln }
        }
        if ($foundLock) {
            Add-Check 'project vpm lock' 'PASS' $foundLock
        } else {
            Add-Check 'project vpm lock' 'WARN' 'vpm-lock.json がありません（ALCOM/VCC で一度 resolve してください）'
        }

        if (Test-Path (Join-Path $proj '.git')) {
            Add-Check 'project git' 'PASS' 'git 管理されています'
        } else {
            Add-Check 'project git' 'WARN' 'git 管理外です。改変前に git init を提案してください（自動では行いません）'
        }

        $apply = Join-Path $proj 'Assets\DSH\Editor\DshApply.cs'
        if (Test-Path $apply) {
            Add-Check 'project dsh editor scripts' 'PASS' 'Assets/DSH/Editor 配置済み'
        } else {
            Add-Check 'project dsh editor scripts' 'WARN' "templates/Editor/ の 2 ファイルを Assets/DSH/Editor/ にコピーしてください"
        }

        $lockFile = Join-Path $proj 'Temp\UnityLockfile'
        $lockAlive = $false
        if (Test-Path $lockFile) {
            $instance = Join-Path $proj 'Library\EditorInstance.json'
            if (Test-Path $instance) {
                try {
                    $info = Get-Content $instance -Raw -Encoding UTF8 | ConvertFrom-Json
                    $editorPid = [int]$info.process_id
                    $lockAlive = ($editorPid -gt 0) -and ($null -ne (Get-Process -Id $editorPid -ErrorAction SilentlyContinue))
                } catch {
                    $lockAlive = $true
                }
            }
        }
        if ($lockAlive) {
            Add-Check 'project lock' 'WARN' 'Unity が起動中です。バッチモードを実行する前に閉じてください'
        } else {
            Add-Check 'project lock' 'PASS' 'バッチモードを実行できます'
        }
    }
}

$results | Format-Table -AutoSize -Wrap | Out-String | Write-Host
$fails = @($results | Where-Object { $_.Status -eq 'FAIL' })
$warns = @($results | Where-Object { $_.Status -eq 'WARN' })
Write-Host ("{0} PASS / {1} WARN / {2} FAIL" -f @($results | Where-Object { $_.Status -eq 'PASS' }).Count, $warns.Count, $fails.Count)
exit ([int]($fails.Count -gt 0))
