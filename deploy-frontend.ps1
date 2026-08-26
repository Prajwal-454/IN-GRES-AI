# Deploys the IN-GRES AI frontend to Vercel production.
# Run from anywhere:  powershell -ExecutionPolicy Bypass -File deploy-frontend.ps1
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "== IN-GRES AI frontend deploy ==" -ForegroundColor Cyan

# 1. Login (opens browser on first run)
vercel whoami *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "Not logged in - a browser window will open. Log in and come back here." -ForegroundColor Yellow
    vercel login
    if ($LASTEXITCODE -ne 0) { Write-Host "Login failed or cancelled." -ForegroundColor Red; exit 1 }
}
Write-Host "Logged in as: $(vercel whoami)" -ForegroundColor Gray

# 2. Deploy linked project (ingres-ai) straight to production
Write-Host "Deploying to production..." -ForegroundColor Cyan
vercel deploy --prod --yes
if ($LASTEXITCODE -ne 0) { Write-Host "Deploy failed - scroll up for the build error." -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "DEPLOYED. Open the site and hard-refresh: Ctrl+Shift+R" -ForegroundColor Green
