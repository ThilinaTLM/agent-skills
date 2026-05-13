# richdoc CLI launcher (PowerShell).
#
# Drives the Python implementation through `uv`. uv handles Python install,
# virtualenv creation, and dependency resolution automatically on first call.

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Output '{"ok":false,"error":"uv is not installed.","code":"PREREQ_MISSING","hint":"Install uv from https://docs.astral.sh/uv/ then retry."}'
    exit 1
}

& uv run --quiet --project $ScriptDir richdoc @args
exit $LASTEXITCODE
