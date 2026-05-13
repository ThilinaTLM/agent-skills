$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Determine runtime: prefer bun, fall back to node >= 22
$Runtime = $null
if (Get-Command bun -ErrorAction SilentlyContinue) {
    $Runtime = "bun"
} elseif (Get-Command node -ErrorAction SilentlyContinue) {
    $NodeMajor = [int]((node -v) -replace 'v(\d+).*', '$1')
    if ($NodeMajor -ge 22) {
        $Runtime = "node"
    }
}

if (-not $Runtime) {
    Write-Output '{"ok":false,"error":"No compatible runtime found","code":"PREREQ_MISSING","hint":"Install bun (https://bun.sh) or Node.js >= 22 (https://nodejs.org)"}'
    exit 1
}

# Auto-install dependencies
if (-not (Test-Path "$ScriptDir\node_modules")) {
    if ($Runtime -eq "bun") {
        bun install --cwd $ScriptDir --silent
    } else {
        npm install --prefix $ScriptDir --loglevel=silent 2>$null
    }
}

# Run CLI
if ($Runtime -eq "bun") {
    & bun run "$ScriptDir\src\index.ts" @args
} else {
    & node --experimental-strip-types --no-warnings "$ScriptDir\src\index.ts" @args
}
