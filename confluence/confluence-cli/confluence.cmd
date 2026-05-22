@echo off
where uv >nul 2>&1
if errorlevel 1 (
    echo {"ok":false,"error":"uv is not installed.","code":"PREREQ_MISSING","hint":"Install uv from https://docs.astral.sh/uv/ then retry."}
    exit /b 1
)
uv run --quiet --project "%~dp0." confluence %*
exit /b %ERRORLEVEL%
