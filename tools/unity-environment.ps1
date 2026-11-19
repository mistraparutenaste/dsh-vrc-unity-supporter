function Get-DshUnityVersion([string]$Project) {
    $versionFile = Join-Path $Project 'ProjectSettings\ProjectVersion.txt'
    if (-not (Test-Path -LiteralPath $versionFile -PathType Leaf)) { return }
    $match = Select-String -LiteralPath $versionFile -Pattern '^m_EditorVersion:\s*(\S+)' | Select-Object -First 1
    if ($match) { $match.Matches[0].Groups[1].Value }
}

function Find-DshUnityEditor([string]$Version) {
    if ($env:UNITY_EDITOR_PATH -and (Test-Path -LiteralPath $env:UNITY_EDITOR_PATH -PathType Leaf)) {
        return (Resolve-Path -LiteralPath $env:UNITY_EDITOR_PATH).Path
    }
    foreach ($base in @((Join-Path $env:ProgramFiles 'Unity\Hub\Editor'), 'D:\Unity\Hub\Editor', 'E:\Unity\Hub\Editor')) {
        if (-not (Test-Path -LiteralPath $base -PathType Container -ErrorAction SilentlyContinue)) { continue }
        $candidate = Join-Path $base "$Version\Editor\Unity.exe"
        if (Test-Path -LiteralPath $candidate -PathType Leaf) { return $candidate }
    }
}

function Get-DshUnityLock([string]$Project) {
    $instance = Join-Path $Project 'Library\EditorInstance.json'
    $lock = Join-Path $Project 'Temp\UnityLockfile'
    if (Test-Path -LiteralPath $instance -PathType Leaf) {
        try {
            $data = Get-Content -LiteralPath $instance -Raw -Encoding UTF8 | ConvertFrom-Json
            $editorPid = [int]$data.process_id
            $process = if ($editorPid -gt 0) { Get-Process -Id $editorPid -ErrorAction SilentlyContinue }
            if ($process -and $process.ProcessName -eq 'Unity') { return 'open' }
            if ($editorPid -gt 0) { return 'clear' }
        } catch { }
    }
    if ((Test-Path -LiteralPath $lock) -and (Get-Process -Name Unity -ErrorAction SilentlyContinue)) {
        return 'unknown'
    }
    'clear'
}
