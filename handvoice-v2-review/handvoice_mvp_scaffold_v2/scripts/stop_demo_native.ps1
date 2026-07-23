$ErrorActionPreference = "Stop"
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptRoot
$pidPath = Join-Path $projectRoot ".native_demo\server.pid"

if (-not (Test-Path -LiteralPath $pidPath)) {
    Write-Host "No native HandVoice demo PID file was found."
    exit 0
}

$serverPid = [int](Get-Content -LiteralPath $pidPath -Raw).Trim()
$process = Get-Process -Id $serverPid -ErrorAction SilentlyContinue
if ($process -and $process.ProcessName -match '^python') {
    Stop-Process -Id $serverPid
    Write-Host "Stopped HandVoice native demo process $serverPid."
}
else {
    Write-Host "The recorded process is no longer a running Python server."
}
Remove-Item -LiteralPath $pidPath -ErrorAction SilentlyContinue
