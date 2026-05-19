@echo off
setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"

rem Determine runtime: prefer bun, fall back to node >= 22
set "RUNTIME="
where bun >nul 2>&1
if !ERRORLEVEL! EQU 0 (
    set "RUNTIME=bun"
) else (
    where node >nul 2>&1
    if !ERRORLEVEL! EQU 0 (
        for /f "tokens=1 delims=." %%a in ('node -v') do set "NODE_MAJOR=%%a"
        set "NODE_MAJOR=!NODE_MAJOR:v=!"
        if !NODE_MAJOR! GEQ 22 set "RUNTIME=node"
    )
)

if not defined RUNTIME (
    echo {"ok":false,"error":"No compatible runtime found","code":"PREREQ_MISSING","hint":"Install bun (https://bun.sh) or Node.js >= 22 (https://nodejs.org)"}
    exit /b 1
)

rem Auto-install dependencies
if not exist "%SCRIPT_DIR%node_modules" (
    if "!RUNTIME!"=="bun" (
        bun install --cwd "%SCRIPT_DIR%" --silent
    ) else (
        npm install --prefix "%SCRIPT_DIR%" --loglevel=silent 2>nul
    )
)

rem Run CLI
if "!RUNTIME!"=="bun" (
    bun run "%SCRIPT_DIR%src\index.ts" %*
) else (
    node --experimental-strip-types --no-warnings "%SCRIPT_DIR%src\index.ts" %*
)
exit /b !ERRORLEVEL!
