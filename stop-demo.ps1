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

Write-Host "Stopped OmniKavach demo services on ports 8000 and 5173." -ForegroundColor Yellow
