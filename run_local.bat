@echo off
setlocal
cd /d "%~dp0"

echo Starting Nexus local AI chatbot...
echo.

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "try { $ollama = Invoke-RestMethod -Uri 'http://127.0.0.1:11434/api/tags' -TimeoutSec 2 -ErrorAction Stop; if ($ollama.models.name -contains 'llama3.2:3b') { Write-Host 'Ollama llama3.2:3b is ready.' -ForegroundColor Green } else { Write-Host 'WARNING: Ollama is running, but llama3.2:3b is not installed.' -ForegroundColor Yellow } } catch { Write-Host 'WARNING: Ollama is not reachable. Start Ollama before chatting with Llama.' -ForegroundColor Yellow }"

echo.
echo Opening backend and frontend in separate windows...

start "Nexus Backend" /D "%~dp0" cmd /k ".\.venv\Scripts\python.exe app.py"
start "Nexus Frontend" /D "%~dp0frontend" cmd /k "npm.cmd run dev -- --host localhost --port 5173"

echo.
echo Wait until Vite says ready, then open:
echo http://localhost:5173
echo.
pause
