[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [switch]$NoBuild,
    [switch]$RevealKey
)

$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptRoot
Set-Location -LiteralPath $projectRoot

function New-RandomSecret {
    param([int]$ByteCount = 32)
    $bytes = [byte[]]::new($ByteCount)
    $generator = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    try {
        $generator.GetBytes($bytes)
    }
    finally {
        $generator.Dispose()
    }
    return [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')
}

function Read-EnvValue {
    param([string]$Path, [string]$Name)
    $match = Get-Content -LiteralPath $Path | Where-Object { $_ -match "^$([Regex]::Escape($Name))=(.*)$" } | Select-Object -Last 1
    if (-not $match) { return $null }
    return ($match -split '=', 2)[1].Trim()
}

function Test-HttpEndpoint {
    param([string]$Uri)
    try {
        $response = Invoke-WebRequest -Uri $Uri -UseBasicParsing -TimeoutSec 5
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw "Docker was not found. Install and start Docker Desktop, then rerun this script."
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    throw "Docker Desktop is installed but not reachable. Start Docker Desktop and wait until it reports that the engine is running."
}

$composeCheck = docker compose version 2>&1
if ($LASTEXITCODE -ne 0) {
    throw "Docker Compose v2 is required. Update Docker Desktop, then rerun this script. Details: $composeCheck"
}

$envPath = Join-Path $projectRoot ".env"
$knownPlaceholders = @(
    "change-this-api-key",
    "replace-with-a-long-random-value",
    "local-development-only-change-me"
)

if (-not (Test-Path -LiteralPath $envPath)) {
    $bootstrapKey = New-RandomSecret
    $postgresPassword = New-RandomSecret
    $envLines = @(
        "HANDVOICE_BOOTSTRAP_KEY=$bootstrapKey",
        "HANDVOICE_MAXIMUM_MEDIA_BYTES=67108864",
        "POSTGRES_DB=handvoice",
        "POSTGRES_USER=handvoice",
        "POSTGRES_PASSWORD=$postgresPassword"
    )
    $utf8WithoutBom = [System.Text.UTF8Encoding]::new($false)
    [System.IO.File]::WriteAllLines($envPath, $envLines, $utf8WithoutBom)
    Write-Host "Created .env with generated local-demo secrets."
}

$bootstrapKey = Read-EnvValue -Path $envPath -Name "HANDVOICE_BOOTSTRAP_KEY"
$postgresPassword = Read-EnvValue -Path $envPath -Name "POSTGRES_PASSWORD"
if ([string]::IsNullOrWhiteSpace($bootstrapKey) -or $bootstrapKey -in $knownPlaceholders) {
    throw ".env contains a missing or placeholder HANDVOICE_BOOTSTRAP_KEY. Delete .env and rerun this script, or replace the value with a unique secret."
}
if ([string]::IsNullOrWhiteSpace($postgresPassword) -or $postgresPassword -match '^replace-|^change-') {
    throw ".env contains a missing or placeholder POSTGRES_PASSWORD. Delete .env and rerun this script, or replace the value with a unique secret."
}

New-Item -ItemType Directory -Force -Path (Join-Path $projectRoot "local_media") | Out-Null

$existingApi = docker compose ps -q api 2>$null
if (-not $existingApi) {
    $listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
    if ($listener) {
        throw "Port 8000 is already in use by process $($listener.OwningProcess). Stop that process or change the HandVoice port before retrying."
    }
}

try {
    if ($NoBuild) {
        docker compose up -d
    }
    else {
        docker compose up --build -d
    }
    if ($LASTEXITCODE -ne 0) { throw "docker compose up failed" }

    $deadline = (Get-Date).AddSeconds(120)
    do {
        if (Test-HttpEndpoint -Uri "http://127.0.0.1:8000/health") { break }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)

    if (-not (Test-HttpEndpoint -Uri "http://127.0.0.1:8000/health")) {
        throw "The API did not become healthy within 120 seconds."
    }
    if (-not (Test-HttpEndpoint -Uri "http://127.0.0.1:8000/capture/")) {
        throw "The API is healthy but the capture interface is unavailable. Rebuild without -NoBuild."
    }
}
catch {
    Write-Host "`nHandVoice failed to start: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "`nRecent API logs:" -ForegroundColor Yellow
    docker compose logs --tail 80 api
    throw
}

$captureUrl = "http://127.0.0.1:8000/capture/"
Write-Host "`nHandVoice demo is ready." -ForegroundColor Green
Write-Host "Capture URL: $captureUrl"
if ($RevealKey) {
    Write-Host "Operator key: $bootstrapKey"
}
else {
    Write-Host "Operator key: hidden to protect screen-shared or recorded terminals."
    Write-Host "Rerun with -NoBuild -RevealKey in private when you need to enter it."
}
Write-Host "`nUse synthetic/demo identifiers only. Do not enter real health or personal data." -ForegroundColor Yellow
Write-Host "Stop later with: docker compose down"

if (-not $NoBrowser) {
    Start-Process $captureUrl
}
