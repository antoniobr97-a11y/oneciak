@echo off
REM Doppio clic per vedere come sta andando DAVVERO: le operazioni gia'
REM chiuse, quante vinte, quante perse, quanto rende in media.
title Trading Bot - rendiconto delle operazioni chiuse
cd /d "%~dp0"

echo ============================================================
echo  COME STA ANDANDO - operazioni gia' chiuse
echo ============================================================
echo.
echo  Conta solo i giri completi (comprato E rivenduto). Le
echo  posizioni ancora aperte non hanno un risultato: quelle
echo  si guardano con RENDICONTO.
echo.
echo ============================================================
echo.

".venv\Scripts\python.exe" bot.py rendiconto

echo.
echo ============================================================
pause
