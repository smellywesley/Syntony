[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [switch]$NoBuild
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptRoot
Set-Location -LiteralPath $projectRoot

function New-RandomSecret {
    $bytes = [byte[]]::new(32)
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try { $generator.GetBytes($bytes) }
    finally { $generator.Dispose() }
    return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function Test-Endpoint {
    param([string]$Uri)
    try {
        $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 3
        return $response.StatusCode -eq 200
    }
    catch { return $false }
}

foreach ($command in @("python", "npm")) {
    if (-not (Get-Command $command -ErrorAction SilentlyContinue)) {
        throw "$command is required for the native demo."
    }
}
$pythonPath = (Get-Command python).Source

python -c "import fastapi, sqlalchemy, uvicorn" 2>$null
if ($LASTEXITCODE -ne 0) {
    throw 'Python dependencies are missing. Run: python -m pip install -e ".[dev]"'
}

$stateRoot = Join-Path $projectRoot ".native_demo"
$keyPath = Join-Path $stateRoot "operator-key.txt"
$pidPath = Join-Path $stateRoot "server.pid"
$stdoutPath = Join-Path $stateRoot "server.out.log"
$stderrPath = Join-Path $stateRoot "server.err.log"
New-Item -ItemType Directory -Force -Path $stateRoot | Out-Null

if (-not (Test-Path -LiteralPath $keyPath)) {
    [System.IO.File]::WriteAllText($keyPath, (New-RandomSecret), [System.Text.UTF8Encoding]::new($false))
}
$operatorKey = (Get-Content -LiteralPath $keyPath -Raw).Trim()

if (-not $NoBuild) {
    Push-Location (Join-Path $projectRoot "apps\capture-web")
    try {
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend build failed." }
    }
    finally { Pop-Location }
}

$captureUrl = "http://127.0.0.1:8000/capture/?demo=1"
if (-not (Test-Endpoint -Uri "http://127.0.0.1:8000/health")) {
    $listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    if ($listener) {
        throw "Port 8000 is already in use by process $($listener.OwningProcess)."
    }

    # Some managed Windows shells inject both `Path` and `PATH`. Start-Process
    # treats those as the same dictionary key, so normalize them before spawn.
    $cleanProcessPath = (cmd /c echo %PATH%).Trim()
    Remove-Item Env:Path -ErrorAction SilentlyContinue
    $env:Path = $cleanProcessPath
    $server = Start-Process -FilePath $pythonPath `
        -ArgumentList (Join-Path $projectRoot "scripts\run_native_demo.py") `
        -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput $stdoutPath -RedirectStandardError $stderrPath
    [System.IO.File]::WriteAllText($pidPath, [string]$server.Id, [System.Text.UTF8Encoding]::new($false))

    $deadline = (Get-Date).AddSeconds(30)
    do {
        if (Test-Endpoint -Uri "http://127.0.0.1:8000/health") { break }
        if ($server.HasExited) {
            $details = if (Test-Path -LiteralPath $stderrPath) { Get-Content -LiteralPath $stderrPath -Raw } else { "No error log." }
            throw "Native API exited during startup.`n$details"
        }
        Start-Sleep -Milliseconds 500
    } while ((Get-Date) -lt $deadline)
}

if (-not (Test-Endpoint -Uri "http://127.0.0.1:8000/health") -or -not (Test-Endpoint -Uri $captureUrl)) {
    throw "The API started, but the health or capture endpoint did not become ready."
}

Write-Host "`nHandVoice native demo is ready." -ForegroundColor Green
Write-Host "Capture URL: $captureUrl"
try {
    $readiness = Invoke-RestMethod -Uri "http://127.0.0.1:8000/ready" -TimeoutSec 3
}
catch {
    $readiness = $_.ErrorDetails.Message | ConvertFrom-Json
}
if (-not $readiness.components.ffmpeg -or -not $readiness.components.ffprobe) {
    Write-Host "FFmpeg is unavailable to the API: recorded-media validation and reporting are blocked." -ForegroundColor Yellow
}
Write-Host "Use synthetic/demo identifiers only. Stop with: .\scripts\stop_demo_native.ps1" -ForegroundColor Yellow

if (-not $NoBrowser) { Start-Process $captureUrl }
