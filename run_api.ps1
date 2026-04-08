$env:MOCK_AI = "false"
$env:MOCK_IDENTITY = "false"
$env:MOCK_AUTH = "false"
.\venv\Scripts\uvicorn.exe app.main:app --workers 4 --host 0.0.0.0 --port 8000
