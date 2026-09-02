@echo off
REM Doppio clic per far girare UN ciclo adesso e poi fermarsi.
REM Utile per vedere cosa fa il bot senza lasciarlo in esecuzione.
title Trading Bot - un ciclo singolo
cd /d "%~dp0"

echo ============================================================
echo  UN CICLO SINGOLO - paper trading (denaro simulato)
echo ============================================================
echo.
echo  Gestisce le posizioni aperte, poi cerca nuove occasioni su
echo  tutto il mercato USA e piazza gli ordini.
echo.
echo  Richiede 20-40 minuti: la finestra sembrera' ferma a lungo,
echo  e' normale, sta analizzando centinaia di titoli.
echo.
echo ============================================================
echo.

.venv\Scripts\python.exe bot.py short-term-once --execute

echo.
echo ============================================================
echo  Ciclo terminato.
echo ============================================================
pause
