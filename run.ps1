$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

$pythonExe = 'C:\Users\liqiy\AppData\Local\Python\bin\python.exe'
if (-not (Test-Path $pythonExe)) { $pythonExe = 'python' }

Write-Host "Starting backend (video stream) on http://localhost:8000 ..."
$backend = Start-Process -FilePath $pythonExe -ArgumentList 'server.py' `
    -WorkingDirectory $root -PassThru -NoNewWindow

Write-Host "Starting frontend (Vite dev server) ..."
$frontend = Start-Process -FilePath 'cmd.exe' -ArgumentList '/c', 'npm run dev' `
    -WorkingDirectory (Join-Path $root 'frontend') -PassThru -NoNewWindow

Write-Host ""
Write-Host "Backend:  http://localhost:8000/video_feed"
Write-Host "Frontend: check the Vite output above for the local URL (usually http://localhost:5173/)"
Write-Host "Press Ctrl+C to stop both."

try {
    Wait-Process -Id $backend.Id, $frontend.Id
} finally {
    Write-Host "`nStopping..."
    Stop-Process -Id $backend.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $frontend.Id -Force -ErrorAction SilentlyContinue
}
