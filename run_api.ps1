$env:MOCK_AI = "true"
$env:MOCK_IDENTITY = "true"
$env:MOCK_AUTH = "true"
.\venv\Scripts\uvicorn.exe app.main:app --workers 4 --host 0.0.0.0 --port 8000
