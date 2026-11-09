@echo off
cd /d "%~dp0"
title News Monitor CLI
color 0A
echo =======================================================
echo          NEWS MONITOR - COMMAND LINE MODE
echo =======================================================
echo.
set /p KEYWORDS="Enter word(s) to monitor (comma-separated, e.g. OpenAI, SpaceX, AI): "
set /p INTERVAL="Enter refresh interval in minutes [default 5]: "

if "%INTERVAL%"=="" set INTERVAL=5

echo.
echo Starting CLI News Monitor for: %KEYWORDS%
echo Refresh interval: %INTERVAL% minute(s)
echo.

python cli.py --keywords "%KEYWORDS%" --interval %INTERVAL%

pause
