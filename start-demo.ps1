$ErrorActionPreference = "SilentlyContinue"

function Stop-PortProcess {
  param([int]$Port)

  $pids = netstat -ano | Select-String ":$Port" | ForEach-Object {
    $parts = ($_ -split '\s+') | Where-Object { $_ -ne "" }
    $parts[-1]
  } | Where-Object { $_ -match '^\d+$' } | Select-Object -Unique

  foreach ($pid in $pids) {
    taskkill /PID $pid /F | Out-Null
  }
}

Stop-PortProcess -Port 8000
Stop-PortProcess -Port 5173

Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location 'c:\projects\OmniKavach\Backend'; & 'c:\projects\OmniKavach\.venv\Scripts\python.exe' -m uvicorn main:app --host 0.0.0.0 --port 8000"
Start-Sleep -Seconds 2
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location 'c:\projects\OmniKavach\frontend'; npm run dev -- --host 0.0.0.0 --port 5173"

$backendReady = $false
for ($attempt = 0; $attempt -lt 10; $attempt++) {
  try {
    $response = Invoke-WebRequest -UseBasicParsing "http://127.0.0.1:8000/health" -TimeoutSec 2
    if ($response.StatusCode -eq 200) {
      $backendReady = $true
      break
    }
  } catch {
    Start-Sleep -Milliseconds 800
  }
}

Write-Host ""
Write-Host "OmniKavach demo is launching..." -ForegroundColor Cyan
Write-Host "Backend:  http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Frontend: http://127.0.0.1:5173/login" -ForegroundColor Green
Write-Host "Network:  use your machine IP with ports 8000 and 5173 if testing from another device" -ForegroundColor Green
if (-not $backendReady) {
  Write-Host "Warning: backend health check did not respond. Check the backend PowerShell window for startup errors." -ForegroundColor Yellow
}
Write-Host ""
Write-Host "Demo login:" -ForegroundColor Yellow
Write-Host "  admin@omnikavach.local / Admin@123"
Write-Host "  doctor@omnikavach.local / Doctor@123"
