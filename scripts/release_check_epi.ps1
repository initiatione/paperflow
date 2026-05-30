param(
    [string]$PluginRoot = "plugins/epi",
    [string]$PytestTarget = "tests/epi",
    [string]$SkillValidateScript = $env:SKILL_VALIDATE_SCRIPT,
    [string]$PluginValidateScript = $env:PLUGIN_VALIDATE_SCRIPT
)

$ErrorActionPreference = "Stop"

function Invoke-Step {
    param(
        [string]$Name,
        [scriptblock]$Body
    )
    Write-Host "== $Name =="
    & $Body
}

Invoke-Step "forbid local machine paths in plugin package" {
    $matches = rg -n "C:\\Users\\liuchf|D:\\paper-search|D:\\paper-research-wiki|D:\\codex-tmp" $PluginRoot
    if ($LASTEXITCODE -eq 0) {
        Write-Host $matches
        throw "local machine path found in plugin package"
    }
    if ($LASTEXITCODE -gt 1) {
        throw "rg failed while scanning plugin package"
    }
}

Invoke-Step "forbid checked plugin pycache" {
    $pycache = Get-ChildItem -LiteralPath $PluginRoot -Recurse -Directory -Filter "__pycache__"
    if ($pycache) {
        $pycache | ForEach-Object { Write-Host $_.FullName }
        throw "plugin package contains __pycache__ directories"
    }
}

Invoke-Step "pytest EPI suite" {
    python -m pytest $PytestTarget -q --basetemp=.pytest_tmp_epi_release_check
}

Invoke-Step "validate wiki-setup skill when validator is configured" {
    if ($SkillValidateScript) {
        python $SkillValidateScript (Join-Path $PluginRoot "skills/wiki-setup")
    } else {
        Write-Host "SKILL_VALIDATE_SCRIPT not set; skipping skill validator"
    }
}

Invoke-Step "validate EPI plugin when validator is configured" {
    if ($PluginValidateScript) {
        python $PluginValidateScript $PluginRoot
    } else {
        Write-Host "PLUGIN_VALIDATE_SCRIPT not set; skipping plugin validator"
    }
}

Write-Host "EPI release check passed"
