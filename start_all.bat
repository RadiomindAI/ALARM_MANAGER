@echo off
echo ============================================================
echo   MW ALARM MANAGER — Avvio Sistema
echo ============================================================
echo.

set BASE=%~dp0
set DATI=%BASE%DATI
set BACKEND=%BASE%backend
set FRONTEND=%BASE%frontend

REM ── STEP 1: Normalizzazione storico (solo se il Parquet non esiste) ─────────
if not exist "%DATI%\history_db.parquet" (
    echo [1/4] Normalizzazione storico 20 giorni...
    echo       Questa operazione richiede 5-15 minuti la prima volta.
    cd /d "%DATI%"
    call "%BACKEND%\venv\Scripts\python.exe" "%DATI%\build_history_db.py"
    if errorlevel 1 (
        echo ERRORE nella normalizzazione storico. Controlla i log.
        pause
        exit /b 1
    )
    echo.
) else (
    echo [1/4] Storico Parquet gia' presente. Skip normalizzazione.
)

REM ── STEP 2: Genera KB (solo se non esiste o storico aggiornato) ─────────────
if not exist "%BACKEND%\data\alarm_kb.json" (
    echo [2/4] Generazione Knowledge Base...
    cd /d "%DATI%"
    call "%BACKEND%\venv\Scripts\python.exe" "%DATI%\build_kb.py"
    if errorlevel 1 (
        echo ERRORE nella generazione KB. Il sistema avviera' senza KB.
    )
    echo.
) else (
    echo [2/4] Knowledge Base gia' presente. Skip generazione.
)

REM ── STEP 3: Avvia Backend ────────────────────────────────────────────────────
echo [3/4] Avvio Backend FastAPI (porta 8000)...
start "Alarm Manager — Backend" cmd /k "cd /d "%BACKEND%" && venv\Scripts\uvicorn main:app --reload --host 0.0.0.0 --port 8000"
timeout /t 3 /nobreak >nul

REM ── STEP 4: Avvia Frontend ───────────────────────────────────────────────────
echo [4/4] Avvio Frontend React (porta 5173)...
start "Alarm Manager — Frontend" cmd /k "cd /d "%FRONTEND%" && npm run dev"

echo.
echo ============================================================
echo   Sistema avviato!
echo   Backend:  http://localhost:8000
echo   Frontend: http://localhost:5173
echo   API Docs: http://localhost:8000/docs
echo ============================================================
echo.
timeout /t 4 /nobreak >nul
start http://localhost:5173
