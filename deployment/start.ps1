# Inicia backend (FastAPI :8000) y frontend (Vite :5173) en ventanas separadas.
$root = Split-Path $PSScriptRoot -Parent
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root'; .\.venv\Scripts\python.exe -m uvicorn backend.app.main:app --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$root\frontend'; npm run dev"
Start-Sleep -Seconds 4
Start-Process "http://localhost:5173"
Write-Host "Backend: http://localhost:8000/docs   Frontend: http://localhost:5173"
