$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (Test-Path '.env') {
    Get-Content '.env' | ForEach-Object {
        if ($_ -match '^\s*([^#][^=]*)=(.*)$') {
            [Environment]::SetEnvironmentVariable($matches[1].Trim(), $matches[2].Trim(), 'Process')
        }
    }
}
$port = if ($env:PORT) { $env:PORT } else { '8010' }
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port $port --proxy-headers --forwarded-allow-ips=127.0.0.1
