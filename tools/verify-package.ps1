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
    'tools/unity-environment.ps1', 'tools/unity_toggle.py', 'tools/unity_texture.py',
    'templates/Editor/DshTextureVariant.cs', 'templates/Editor/DshCapture.cs',
    'templates/Editor/DshAvatarTools.cs', 'templates/Editor/DshShape.cs', 'tools/unity_shape.py',
    'skills/vrc-texture-variant/SKILL.md', 'skills/vrc-material-adjust/SKILL.md', 'skills/vrc-shape-adjust/SKILL.md', 'docs/PHOTOCRAFT.md',
    'templates/Editor/DshAccessory.cs', 'tools/unity_accessory.py', 'skills/vrc-accessory/SKILL.md',
    'templates/Editor/DshDynamics.cs', 'templates/Editor/DshParameters.cs', 'templates/Editor/DshPhysBone.cs',
    'templates/Editor/DshProportion.cs', 'tools/dsh_recipe.py', 'tools/unity_params.py', 'tools/unity_physbone.py',
    'tools/unity_proportion.py', 'skills/vrc-physbone/SKILL.md', 'skills/vrc-proportion/SKILL.md',
    'templates/Editor/DshExpression.cs', 'tools/unity_expression.py', 'skills/vrc-expression/SKILL.md',
    'templates/Editor/DshMigrate.cs', 'tools/unity_migrate.py', 'skills/vrc-avatar-update/SKILL.md',
    'templates/Editor/DshPlayback.cs', 'tools/unity_playback.py', 'templates/Editor/DshPhysBoneSim.cs', 'skills/vrc-auto-adjust/SKILL.md',
    'templates/Blender/dsh_blender.py', 'tools/blender_model.py', 'skills/vrc-blender-model/SKILL.md', 'skills/vrc-outfit-fit/SKILL.md',
    'templates/Editor/DshMenu.cs', 'tools/unity_menu.py', 'skills/vrc-menu/SKILL.md',
    'templates/Editor/DshPolygon.cs', 'tools/unity_polygon.py', 'skills/vrc-polygon/SKILL.md',
    'templates/Editor/DshQuest.cs', 'tools/unity_quest.py', 'skills/vrc-quest/SKILL.md',
    'install.cmd',
    'installer/install.cmd', 'installer/install.ps1',
    'installer/uninstall.cmd', 'installer/uninstall.ps1',
    'installer/README.md',
    'booth/00_README_JA.txt', 'tools/build-booth.ps1'
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
#    (skills/ is shared by DSH, Claude Code and Codex; claude/skills/ is Claude Code only,
#    codex/skills/ is Codex only)
$skillDirs = @(Get-ChildItem (Join-Path $root 'skills') -Directory)
foreach ($agentSkills in @('claude/skills', 'codex/skills')) {
    $agentSkillPath = Join-Path $root $agentSkills
    if (Test-Path $agentSkillPath) { $skillDirs += Get-ChildItem $agentSkillPath -Directory }
}
foreach ($dir in $skillDirs) {
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

# 8. the Claude Code plugin manifest matches package.json and its marketplace entry.
$pluginPath = Join-Path $root '.claude-plugin/plugin.json'
$marketPath = Join-Path $root '.claude-plugin/marketplace.json'
if (-not (Test-Path $pluginPath) -or -not (Test-Path $marketPath)) {
    $problems.Add('missing: .claude-plugin/plugin.json or .claude-plugin/marketplace.json')
} else {
    try {
        $plugin = Get-Content $pluginPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $market = Get-Content $marketPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($plugin.name -ne $pkgJson.name) { $problems.Add('plugin.json: name differs from package.json') }
        if ($plugin.version -ne $pkgJson.version) { $problems.Add("plugin.json: version $($plugin.version) differs from package.json $($pkgJson.version)") }
        $entry = @($market.plugins | Where-Object { $_.name -eq $plugin.name })
        if ($entry.Count -ne 1) { $problems.Add('marketplace.json: no single plugins[] entry named like plugin.json') }
        elseif ($entry[0].source -notmatch '^\./?$') { $problems.Add('marketplace.json: plugin source must be "./"') }
        foreach ($p in @($plugin.skills)) {
            if ($p -and -not (Test-Path (Join-Path $root $p))) { $problems.Add("plugin.json: skills path not found: $p") }
        }
    } catch { }  # invalid JSON is already reported by check 3
}

# 8b. the Codex plugin manifest matches package.json, declares its skills and interface,
#     and the Codex marketplace points at the repository root.
$codexPluginPath = Join-Path $root '.codex-plugin/plugin.json'
$codexMarketPath = Join-Path $root '.agents/plugins/marketplace.json'
if (-not (Test-Path $codexPluginPath) -or -not (Test-Path $codexMarketPath)) {
    $problems.Add('missing: .codex-plugin/plugin.json or .agents/plugins/marketplace.json')
} else {
    try {
        $codexPlugin = Get-Content $codexPluginPath -Raw -Encoding UTF8 | ConvertFrom-Json
        $codexMarket = Get-Content $codexMarketPath -Raw -Encoding UTF8 | ConvertFrom-Json
        if ($codexPlugin.name -ne $pkgJson.name) { $problems.Add('.codex-plugin/plugin.json: name differs from package.json') }
        if ($codexPlugin.version -ne $pkgJson.version) { $problems.Add(".codex-plugin/plugin.json: version $($codexPlugin.version) differs from package.json $($pkgJson.version)") }
        if (-not $codexPlugin.description) { $problems.Add('.codex-plugin/plugin.json: description is missing') }
        if (-not $codexPlugin.author.name) { $problems.Add('.codex-plugin/plugin.json: author.name is missing') }
        if (-not $codexPlugin.interface.displayName) { $problems.Add('.codex-plugin/plugin.json: interface.displayName is missing') }
        if ($codexPlugin.PSObject.Properties.Name -contains '$schema') { $problems.Add('.codex-plugin/plugin.json: must not declare $schema') }
        # A root plugin.json would make Codex ignore the skills field (and drop codex/skills).
        if (Test-Path (Join-Path $root 'plugin.json')) { $problems.Add('plugin.json at the root makes Codex ignore .codex-plugin skills') }
        $codexSkillPaths = @($codexPlugin.skills)
        foreach ($p in @('./skills/', './codex/skills/')) {
            if ($codexSkillPaths -notcontains $p) { $problems.Add(".codex-plugin/plugin.json: skills must list $p") }
        }
        foreach ($p in $codexSkillPaths) {
            if ($p -and -not (Test-Path (Join-Path $root $p))) { $problems.Add(".codex-plugin/plugin.json: skills path not found: $p") }
        }
        $codexEntry = @($codexMarket.plugins | Where-Object { $_.name -eq $codexPlugin.name })
        if ($codexEntry.Count -ne 1) { $problems.Add('.agents/plugins/marketplace.json: no single plugins[] entry named like the Codex plugin') }
        else {
            if ($codexEntry[0].source.source -ne 'local' -or $codexEntry[0].source.path -notmatch '^\./?$') {
                $problems.Add('.agents/plugins/marketplace.json: plugin source must be {"source":"local","path":"./"}')
            }
            if (-not $codexEntry[0].policy.installation -or -not $codexEntry[0].policy.authentication -or -not $codexEntry[0].category) {
                $problems.Add('.agents/plugins/marketplace.json: entry needs policy.installation, policy.authentication and category')
            }
        }
    } catch { }  # invalid JSON is already reported by check 3
}

# 9. skill routing stays in step: each agent's entry skill names every shared skill,
#    every skill the DSH persona tells the agent to load exists, and descriptions stay short
#    (long descriptions crowd the Claude Code skill listing).
$sharedSkills = @(Get-ChildItem (Join-Path $root 'skills') -Directory | ForEach-Object Name)
foreach ($entryRel in @('claude/skills/vrc-avatar/SKILL.md', 'codex/skills/vrc-avatar/SKILL.md')) {
    $entryPath = Join-Path $root $entryRel
    if (-not (Test-Path $entryPath)) { $problems.Add("missing: $entryRel"); continue }
    $entry = Get-Content $entryPath -Raw -Encoding UTF8
    foreach ($name in $sharedSkills) {
        if ($entry -cnotmatch ('`' + [regex]::Escape($name) + '`')) {
            $problems.Add("$entryRel does not route to skill: $name")
        }
    }
}
if (Test-Path $patchPath -PathType Leaf) {
    foreach ($m in [regex]::Matches($patch, 'load the (?<name>[a-z0-9-]+) skill')) {
        if ($sharedSkills -notcontains $m.Groups['name'].Value) {
            $problems.Add("cordis.patch.yml: persona loads a skill that does not exist: $($m.Groups['name'].Value)")
        }
    }
}
foreach ($dir in $skillDirs) {
    $skill = Join-Path $dir.FullName 'SKILL.md'
    if (-not (Test-Path $skill)) { continue }
    $line = Get-Content $skill -TotalCount 6 -Encoding UTF8 | Where-Object { $_ -match '^description:' } | Select-Object -First 1
    if (-not $line) { $problems.Add("SKILL.md has no description: $($dir.Name)"); continue }
    $length = ($line -replace '^description:\s*', '').Length
    if ($length -gt 130) { $problems.Add("SKILL.md description is $length characters (keep it to 130): $($dir.Name)") }
}

if ($problems.Count -eq 0) {
    Write-Host 'verify-package: OK' -ForegroundColor Green
    exit 0
}
Write-Host "verify-package: $($problems.Count) problem(s)" -ForegroundColor Red
$problems | ForEach-Object { Write-Host "  - $_" }
exit 1
