# Start AI QA Portal backend for IDE Feature Memory pilot (AUTH_DISABLED).
# Usage (from repo root):
#   .\scripts\feature_memory\start-backend.ps1
#   .\scripts\feature_memory\start-backend.ps1 -Port 8000

param(
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Set-Location $RepoRoot

$env:AUTH_DISABLED = "true"
Write-Host "AUTH_DISABLED=$($env:AUTH_DISABLED)  port=$Port  cwd=$RepoRoot"
Write-Host "Health: http://127.0.0.1:$Port/health"

py -3 -m uvicorn ai_qa_portal.backend.main:app --reload --host 127.0.0.1 --port $Port
