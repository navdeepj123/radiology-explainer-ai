Write-Host "Flushing DNS to avoid stale connection issues..." -ForegroundColor Yellow
ipconfig /flushdns | Out-Null
Write-Host "Starting ClearScan server..." -ForegroundColor Green
python app.py