@echo off
rem Same as start.bat but with video analysis (MediaPipe) enabled.
rem ASCII only on purpose: cmd garbles UTF-8.
cd /d "%~dp0"

set "PYEXE="
where py >nul 2>&1
if not errorlevel 1 set "PYEXE=py -3"
if defined PYEXE goto :run

where python >nul 2>&1
if not errorlevel 1 set "PYEXE=python"
if defined PYEXE goto :run
goto :nopython

:run
%PYEXE% run_local.py --vision
if errorlevel 1 pause
goto :eof

:nopython
echo.
echo Python not found.
echo Install Python 3.11 or newer: https://www.python.org/downloads/
echo During setup check "Add Python to PATH", then run this file again.
echo.
pause
