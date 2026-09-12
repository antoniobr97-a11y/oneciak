@echo off
REM Rendiconto del bot: quanto c'e' sul conto, come vanno le posizioni,
REM quali ordini sono in attesa. NON invia nessun ordine, guarda soltanto.
REM Si puo' lanciare in qualsiasi momento, anche col bot acceso.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo.
    echo  ERRORE: ambiente Python non trovato in .venv
    echo  Serve aver fatto l'installazione una volta ^(vedi README^).
    echo.
    pause
    exit /b 1
)
cls
".venv\Scripts\python.exe" bot.py status
if errorlevel 1 (
    echo.
    echo  Qualcosa non ha funzionato. Il messaggio d'errore e' qui sopra.
)
echo.
pause
