@echo off
echo Avvio backend...
cd /d %~dp0backend
start cmd /k ".venv\Scripts\activate && uvicorn app.main:app --reload --port 8000"

REM attesa 5 secondi per dare tempo al backend di avviarsi
timeout /t 5 /nobreak >nul

echo Avvio frontend...
cd /d %~dp0frontend
start cmd /k "npm run dev"

REM attesa 3 secondi per far partire il frontend
timeout /t 3 /nobreak >nul

echo Apro il browser...
start http://localhost:5173

echo Tutto avviato. Puoi chiudere questa finestra.
pause
