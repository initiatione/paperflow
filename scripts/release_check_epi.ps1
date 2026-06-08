param(
    [string]$PluginRoot = "plugins/paper-source",
    [string]$PytestTarget = "tests/epi",
    [string]$SkillValidateScript = $env:SKILL_VALIDATE_SCRIPT,
    [string]$PluginValidateScript = $env:PLUGIN_VALIDATE_SCRIPT,
    [string]$PluginEvalScript = $env:PLUGIN_EVAL_SCRIPT,
    [string]$MetricPackManifest = $env:EPI_METRIC_PACK_MANIFEST
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

function Clear-PluginPycache {
    $resolvedRoot = (Resolve-Path -LiteralPath $PluginRoot).Path
    $rootPrefix = $resolvedRoot.TrimEnd("\") + "\"
    $pycacheDirs = Get-ChildItem -LiteralPath $resolvedRoot -Recurse -Directory -Filter "__pycache__"
    foreach ($dir in $pycacheDirs) {
        $resolvedPath = (Resolve-Path -LiteralPath $dir.FullName).Path
        if (-not $resolvedPath.StartsWith($rootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "refusing to remove pycache outside plugin root: $resolvedPath"
        }
        Remove-Item -LiteralPath $resolvedPath -Recurse -Force
    }
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

Invoke-Step "forbid tracked plugin pycache" {
    $tracked = @(git ls-files -- $PluginRoot | Where-Object { $_ -match '(^|/)__pycache__(/|$)|\.pyc$' })
    if ($tracked) {
        $tracked | ForEach-Object { Write-Host $_ }
        throw "plugin package tracks __pycache__ or .pyc files"
    }
}

Invoke-Step "clear generated plugin pycache" {
    Clear-PluginPycache
}

Invoke-Step "pytest EPI suite" {
    python -m pytest $PytestTarget -q --basetemp=.pytest_tmp_epi_release_check
}

Invoke-Step "clear generated plugin pycache after pytest" {
    Clear-PluginPycache
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

Invoke-Step "Plugin Eval with epi-quality-gates when configured" {
    if ($PluginEvalScript) {
        if (-not $MetricPackManifest) {
            $MetricPackManifest = Join-Path $PluginRoot "metric-packs/epi-quality-gates/manifest.json"
        }
        node $PluginEvalScript analyze $PluginRoot --metric-pack $MetricPackManifest --format markdown
    } else {
        Write-Host "PLUGIN_EVAL_SCRIPT not set; skipping Plugin Eval"
    }
}

Write-Host "EPI release check passed"
