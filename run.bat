@echo off
cd /d "%~dp0"
title News Monitor - Internet Keyword Tracker
color 0B
echo =======================================================
echo          NEWS MONITOR - INTERNET KEYWORD TRACKER
echo =======================================================
echo  Starting local server and background news scanner...
echo  Opening browser at http://127.0.0.1:5000 ...
echo =======================================================
echo.

python app.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Application exited with code %ERRORLEVEL%.
    pause
)
