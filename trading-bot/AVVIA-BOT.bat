@echo off
REM Doppio clic su questo file per avviare il bot (Windows).
REM Sostituisce il comando da digitare nel terminale: apre la finestra,
REM lancia lo scheduler e la tiene aperta anche in caso di errore, cosi'
REM il messaggio resta leggibile invece di sparire.
title Trading Bot - lascia questa finestra aperta
cd /d "%~dp0"

echo ============================================================
echo  TRADING BOT - paper trading (denaro simulato)
echo ============================================================
echo.
echo  Il bot parte adesso con un ciclo, poi si rimette in attesa
echo  e riparte da solo ogni giorno feriale alle 22:15 italiane.
echo.
echo  Se lo avvii a mercato APERTO (15:30-22:00) sistema solo le
echo  posizioni gia' aperte: la candela di oggi non e' ancora
echo  chiusa e analizzarla darebbe risultati che cambiano di
echo  minuto in minuto. La ricerca di nuove occasioni la fa da
echo  sola alle 22:15, a mercato chiuso.
echo.
echo  LASCIA QUESTA FINESTRA APERTA. Per fermarlo: chiudila,
echo  oppure premi Ctrl+C.
echo.
echo  Le posizioni gia' aperte restano protette anche a bot
echo  spento: stop-loss e prese di profitto sono ordini
echo  depositati presso Alpaca.
echo.
echo ============================================================
echo.

.venv\Scripts\python.exe bot.py schedule

echo.
echo ============================================================
echo  Il bot si e' fermato. Se sopra vedi un errore, copialo.
echo ============================================================
pause
