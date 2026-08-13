param(
    [switch]$CheckOnly,
    [string]$LanIp = ""
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$backendUrl = "http://127.0.0.1:8000"

function Resolve-LanIPv4 {
    param([string]$Override)
    if ($Override) { return $Override }
    $routes = Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue |
        Sort-Object RouteMetric
    foreach ($route in $routes) {
        $address = Get-NetIPAddress -InterfaceIndex $route.InterfaceIndex -AddressFamily IPv4 -ErrorAction SilentlyContinue |
            Where-Object { $_.AddressState -eq "Preferred" -and $_.IPAddress -notlike "127.*" -and $_.IPAddress -notlike "169.254.*" } |
            Select-Object -First 1
        if ($address) { return $address.IPAddress }
    }
    return "127.0.0.1"
}

$resolvedLanIp = Resolve-LanIPv4 -Override $LanIp
$phoneApiUrl = "http://${resolvedLanIp}:8000"
$python = Get-Command python -ErrorAction SilentlyContinue
$ollama = Get-Command ollama -ErrorAction SilentlyContinue
$databaseState = if ($env:DATABASE_URL) { "SET" } else { "NOT_SET" }
$qwenState = "NOT_FOUND"
if ($ollama) {
    $models = (& ollama list 2>$null | Out-String)
    if ($models -match "qwen2\.5:7b-instruct-q4_K_M") { $qwenState = "AVAILABLE" }
}

Write-Output "Repository: $repoRoot"
Write-Output "Python: $(if ($python) { 'AVAILABLE' } else { 'NOT_FOUND' })"
Write-Output "Ollama Qwen 7B: $qwenState"
Write-Output "DATABASE_URL: $databaseState"
Write-Output "LAN IPv4: $resolvedLanIp"
Write-Output "Phone API URL: $phoneApiUrl"
Write-Output "Frontend env: VITE_API_BASE_URL=$phoneApiUrl"
Write-Output "Firewall: NOT_MODIFIED (allow TCP 8000 manually only if Windows prompts/blocks it)"

if ($CheckOnly) { exit 0 }
if (-not $python) { throw "Python is required." }

Push-Location $repoRoot
try {
    & python -c "import backend.app.main; import uvicorn" | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Backend dependencies are not ready." }

    $logDir = Join-Path $env:TEMP "HarmonyAI-s4-acceptance"
    New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    $stdoutLog = Join-Path $logDir "backend.stdout.log"
    $stderrLog = Join-Path $logDir "backend.stderr.log"
    $env:PYTHONPATH = $repoRoot
    $backend = Start-Process -FilePath $python.Source `
        -ArgumentList @("-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000") `
        -WorkingDirectory $repoRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $stdoutLog -RedirectStandardError $stderrLog

    $healthy = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        Start-Sleep -Milliseconds 500
        try {
            Invoke-RestMethod -Uri "$backendUrl/health" -TimeoutSec 2 | Out-Null
            $healthy = $true
            break
        } catch {
            if ($backend.HasExited) { break }
        }
    }
    if (-not $healthy) {
        throw "Backend did not become healthy. Inspect $stderrLog (credentials are never printed by this script)."
    }
    try {
        Invoke-RestMethod -Uri "$backendUrl/api/v2/providers/health" -TimeoutSec 5 | Out-Null
        Write-Output "Provider health: REACHABLE"
    } catch {
        Write-Output "Provider health: UNREACHABLE (manual gate remains pending)"
    }
    Write-Output "Backend PID: $($backend.Id)"
    Write-Output "Backend health: $backendUrl/health"
    Write-Output "Phone setup: same Wi-Fi, then build/run with VITE_API_BASE_URL=$phoneApiUrl"
    Write-Output "Stop backend: Stop-Process -Id $($backend.Id)"
} finally {
    Pop-Location
}
