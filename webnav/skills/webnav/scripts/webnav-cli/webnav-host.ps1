$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
& bun run "$ScriptDir\src\index.ts" native-host
