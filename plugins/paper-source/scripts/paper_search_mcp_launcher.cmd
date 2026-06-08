@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "LAUNCHER=%SCRIPT_DIR%paper_search_mcp_launcher.py"
set "SELECTED_PYTHON="
set "RUNTIME_PYTHON="

call :debug "start script=%~f0 cwd=%CD% codex_home=%CODEX_HOME% plugin_root=%CLAUDE_PLUGIN_ROOT% runtime_config=%EPI_RUNTIME_CONFIG%"

for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$runtime=$env:EPI_RUNTIME_CONFIG; if (-not $runtime) { $codexHome=$env:CODEX_HOME; if (-not $codexHome) { $codexHome=Join-Path $env:USERPROFILE '.codex' }; $runtime=Join-Path $codexHome 'plugins\paperflow\paper-source\runtime.json' }; if (Test-Path -LiteralPath $runtime) { $json=Get-Content -LiteralPath $runtime -Raw | ConvertFrom-Json; $cmd=$json.paper_search_mcp.command; if ($cmd) { [Console]::Out.Write($cmd) } }"`) do set "RUNTIME_PYTHON=%%P"

call :debug "runtime_python=%RUNTIME_PYTHON% launcher=%LAUNCHER%"

call :select_python "%RUNTIME_PYTHON%"
call :select_python "%EPI_PAPER_SEARCH_MCP_LAUNCHER_PYTHON%"
call :select_python "%EPI_PAPER_SEARCH_MCP_COMMAND%"
call :select_python "%CONDA_PREFIX%\python.exe"
call :select_python "python.exe"
call :select_python "python"

if not defined SELECTED_PYTHON (
  call :debug "no usable python found"
  echo paper-search-mcp launcher could not find a usable Python interpreter. 1>&2
  exit /b 1
)

call :debug "selected_python=%SELECTED_PYTHON%"
"%SELECTED_PYTHON%" "%LAUNCHER%"
set "LAUNCHER_EXIT=%ERRORLEVEL%"
call :debug "exit_code=%LAUNCHER_EXIT%"
exit /b %LAUNCHER_EXIT%

:debug
if not defined EPI_PAPER_SEARCH_MCP_LAUNCHER_DEBUG_LOG exit /b 0
>> "%EPI_PAPER_SEARCH_MCP_LAUNCHER_DEBUG_LOG%" echo [%DATE% %TIME%] %~1
exit /b 0

:select_python
if defined SELECTED_PYTHON exit /b 0
set "CANDIDATE=%~1"
if not defined CANDIDATE exit /b 0
"%CANDIDATE%" -c "import paper_search_mcp" >nul 2>nul
if errorlevel 1 exit /b 0
set "SELECTED_PYTHON=%CANDIDATE%"
call :debug "candidate_ok=%SELECTED_PYTHON%"
exit /b 0
