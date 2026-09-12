# share.ps1 - Give a friend a temporary public link to IN-GRES AI
# ------------------------------------------------------------------
# Uses a free localhost.run reverse SSH tunnel (no account needed). The
# link stays live for as long as this script's ssh window stays open.
#
# Usage:  powershell -ExecutionPolicy Bypass -File share.ps1
# ------------------------------------------------------------------

param(
    [int]$Port = 5173,
    [int]$BackendPort = 8000
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "================================================================"
Write-Host "  IN-GRES AI - Share via localhost.run tunnel"
Write-Host "================================================================"
Write-Host ""

# ---- 1. Make sure the backend is running ----------------------------------
if (-not (Get-NetTCPConnection -State Listen -LocalPort $BackendPort -ErrorAction SilentlyContinue)) {
    Write-Host "[backend] not running - starting uvicorn on 127.0.0.1:$BackendPort ..."
    $backendDir = Join-Path $PSScriptRoot "backend"
    Start-Process -FilePath (Join-Path $backendDir ".venv\Scripts\python.exe") `
        -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "$BackendPort" `
        -WorkingDirectory $backendDir -WindowStyle Hidden
    Start-Sleep -Seconds 4
} else {
    Write-Host "[backend] already running on port $BackendPort"
}

# ---- 2. Make sure the frontend dev server is running -----------------------
if (-not (Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue)) {
    Write-Host "[frontend] not running - starting npm run dev on port $Port ..."
    $frontendDir = Join-Path $PSScriptRoot "frontend"
    Start-Process -FilePath "npm.cmd" -ArgumentList "run", "dev" `
        -WorkingDirectory $frontendDir -WindowStyle Hidden
    Start-Sleep -Seconds 6
} else {
    Write-Host "[frontend] already running on port $Port"
}

# ---- 3. Sanity-check the app responds ---------------------------------------
try {
    $local = Invoke-WebRequest -Uri "http://localhost:$Port" -UseBasicParsing -TimeoutSec 10
    Write-Host ("[app]    local check OK (HTTP {0})" -f $local.StatusCode)
} catch {
    Write-Warning "[app]    could not reach http://localhost:$Port - the friend link may not work yet."
}

# ---- 4. OpenSSH - required for the reverse tunnel -----------------------------
if (-not (Get-Command ssh -ErrorAction SilentlyContinue)) {
    Write-Error "OpenSSH client is not installed. Enable it via Settings > Apps > Optional features, then re-run."
}

# ---- 5. Start the tunnel in its own window -----------------------------------
# localhost.run: `ssh -R 80:localhost:<port> nokey@localhost.run` returns a
# free https://<random>.lhr.life URL. No account, no installation.
# (Cloudflare quick tunnels are avoided: cloudflared's embedded DNS resolver
#  fails on some networks with "lookup region1.v2.argotunnel.com: i/o timeout",
#  dropping the connection right after it registers.)
Write-Host ""
Write-Host "Starting tunnel ... the public link appears in the new window."
Write-Host "(Keep that window open; close it to revoke the link.)"
Write-Host ""
Start-Process -FilePath "ssh.exe" `
    -ArgumentList @(
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=NUL",
        "-o", "ServerAliveInterval=30",
        "-o", "ServerAliveCountMax=2",
        "-o", "ExitOnForwardFailure=yes",
        "-R", "80:localhost:$Port",
        "nokey@localhost.run"
    ) -WindowStyle Normal

Write-Host "================================================================"
Write-Host "  Done. Wait ~10 seconds, then open the https://*.lhr.life"
Write-Host "  URL from the ssh window and send it to your friend."
Write-Host ""
Write-Host "  Tips:"
Write-Host "    - Login with your SEED_USER_EMAIL / SEED_USER_PASSWORD from .env   (dev credentials)"
Write-Host "    - The app is a PWA - friends can 'Install' it from the browser."
Write-Host "    - HTTPS works out of the box (microphone/voice need it)."
Write-Host "    - For a permanent URL, see DEPLOYING.md (Docker host)."
Write-Host "================================================================"