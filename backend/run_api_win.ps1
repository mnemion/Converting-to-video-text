$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$port = $env:UVICORN_PORT
if (-not $port) { $port = 8000 }
uvicorn main:app --reload --port $port

