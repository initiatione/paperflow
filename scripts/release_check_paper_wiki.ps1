param(
    [string]$PluginRoot = "plugins/paper-wiki",
    [string]$PytestTarget = "tests/paper_research_wiki",
    [string]$SkillValidateScript = $env:SKILL_VALIDATE_SCRIPT,
    [string]$PluginValidateScript = $env:PLUGIN_VALIDATE_SCRIPT,
    [string]$PluginEvalScript = $env:PLUGIN_EVAL_SCRIPT,
    [string]$CoverageSource = "plugins/paper-wiki/scripts",
    [string]$CoverageDataFile = ".coverage.paper_wiki_release_check",
    [string]$RunStamp = $env:PAPERFLOW_RELEASE_RUN_ID
)

$ErrorActionPreference = "Stop"
$env:PYTHONDONTWRITEBYTECODE = "1"
if (-not $RunStamp) {
    $RunStamp = "$PID-$([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())"
}

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

function Clear-PluginGeneratedArtifacts {
    python scripts\paperflow_audit.py package-hygiene $PluginRoot --clean --json
    if ($LASTEXITCODE -ne 0) {
        throw "generated plugin package artifact cleanup failed with exit code $LASTEXITCODE"
    }
}

function New-PluginEvalCoverageArtifact {
    $evalDir = Join-Path $PluginRoot ".plugin-eval"
    $coveragePath = Join-Path $evalDir "coverage.xml"
    if (Test-Path -LiteralPath $CoverageDataFile) {
        Remove-Item -LiteralPath $CoverageDataFile -Force
    }
    New-Item -ItemType Directory -Force -Path $evalDir | Out-Null
    $coverageBaseTemp = ".pytest_tmp_paper_wiki_release_coverage_$RunStamp"
    python -m coverage run --data-file=$CoverageDataFile --source=$CoverageSource -m pytest $PytestTarget -q --basetemp=$coverageBaseTemp
    if ($LASTEXITCODE -ne 0) {
        throw "coverage pytest Paper Wiki suite failed with exit code $LASTEXITCODE"
    }
    python -m coverage xml --data-file=$CoverageDataFile -o $coveragePath
    if ($LASTEXITCODE -ne 0) {
        throw "coverage XML generation failed with exit code $LASTEXITCODE"
    }
    if (Test-Path -LiteralPath $CoverageDataFile) {
        Remove-Item -LiteralPath $CoverageDataFile -Force
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

Invoke-Step "pytest Paper Wiki suite" {
    $baseTemp = ".pytest_tmp_paper_wiki_release_check_$RunStamp"
    python -m pytest $PytestTarget -q --basetemp=$baseTemp
    if ($LASTEXITCODE -ne 0) {
        throw "pytest Paper Wiki suite failed with exit code $LASTEXITCODE"
    }
}

Invoke-Step "clear generated plugin pycache after pytest" {
    Clear-PluginPycache
}

Invoke-Step "forbid generated plugin package artifacts after cleanup" {
    python scripts\paperflow_audit.py package-hygiene $PluginRoot --json
    if ($LASTEXITCODE -ne 0) {
        throw "generated plugin package artifact check failed with exit code $LASTEXITCODE"
    }
}

Invoke-Step "validate paper-research-wiki skill when validator is configured" {
    if ($SkillValidateScript) {
        python $SkillValidateScript (Join-Path $PluginRoot "skills/paper-research-wiki")
        if ($LASTEXITCODE -ne 0) {
            throw "skill validator failed with exit code $LASTEXITCODE"
        }
    } else {
        Write-Host "SKILL_VALIDATE_SCRIPT not set; skipping skill validator"
    }
}

Invoke-Step "validate Paper Wiki plugin when validator is configured" {
    if ($PluginValidateScript) {
        python $PluginValidateScript $PluginRoot
        if ($LASTEXITCODE -ne 0) {
            throw "plugin validator failed with exit code $LASTEXITCODE"
        }
    } else {
        Write-Host "PLUGIN_VALIDATE_SCRIPT not set; skipping plugin validator"
    }
}

Invoke-Step "Plugin Eval baseline when configured" {
    if ($PluginEvalScript) {
        try {
            New-PluginEvalCoverageArtifact
            node $PluginEvalScript analyze $PluginRoot --format markdown
            if ($LASTEXITCODE -ne 0) {
                throw "Plugin Eval failed with exit code $LASTEXITCODE"
            }
        } finally {
            Clear-PluginGeneratedArtifacts
        }
    } else {
        Write-Host "PLUGIN_EVAL_SCRIPT not set; skipping Plugin Eval"
    }
}

Write-Host "Paper Wiki release check passed"
