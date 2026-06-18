@echo off
setlocal EnableExtensions

set "SCRIPT_DIR=%~dp0"
set "LAUNCHER=%SCRIPT_DIR%grok_search_mcp_launcher.py"
set "SELECTED_PYTHON="

call :debug "start script=%~f0 cwd=%CD% codex_home=%CODEX_HOME% plugin_root=%CLAUDE_PLUGIN_ROOT% runtime_config=%PAPER_SOURCE_RUNTIME_CONFIG%"

call :select_python "%PAPER_SOURCE_GROK_SEARCH_MCP_LAUNCHER_PYTHON%"
call :select_python "%PAPER_SOURCE_PAPER_SEARCH_MCP_LAUNCHER_PYTHON%"
call :select_python "%CONDA_PREFIX%\python.exe"
call :select_python "python.exe"
call :select_python "python"

if not defined SELECTED_PYTHON (
  call :debug "no usable python found"
  echo grok-search-rs MCP launcher could not find a usable Python interpreter. 1>&2
  exit /b 1
)

call :debug "selected_python=%SELECTED_PYTHON% launcher=%LAUNCHER%"
"%SELECTED_PYTHON%" "%LAUNCHER%"
set "LAUNCHER_EXIT=%ERRORLEVEL%"
call :debug "exit_code=%LAUNCHER_EXIT%"
exit /b %LAUNCHER_EXIT%

:debug
set "DEBUG_LOG=%PAPER_SOURCE_GROK_SEARCH_MCP_LAUNCHER_DEBUG_LOG%"
if not defined DEBUG_LOG exit /b 0
>> "%DEBUG_LOG%" echo [%DATE% %TIME%] %~1
exit /b 0

:select_python
if defined SELECTED_PYTHON exit /b 0
set "CANDIDATE=%~1"
if not defined CANDIDATE exit /b 0
"%CANDIDATE%" -c "import sys" >nul 2>nul
if errorlevel 1 exit /b 0
set "SELECTED_PYTHON=%CANDIDATE%"
call :debug "candidate_ok=%SELECTED_PYTHON%"
exit /b 0
