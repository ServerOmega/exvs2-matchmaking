@echo off
title EXVS2 - patch game (optional)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\patch-game.ps1" %*
echo.
pause
