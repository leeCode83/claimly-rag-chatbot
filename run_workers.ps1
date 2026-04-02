$env:MOCK_AI = "true"
$env:MOCK_IDENTITY = "true"
$env:MOCK_AUTH = "true"

# Menjalankan 4 instance worker secara paralel di window baru
for ($i=1; $i -le 4; $i++) {
    Write-Host "Starting Worker Instance #$i..."
    Start-Process powershell -ArgumentList "-NoExit -Command `"cd '$PWD'; .\venv\Scripts\Activate.ps1; arq app.workers.rag_worker.WorkerSettings`""
}
