@echo off
setlocal EnableExtensions EnableDelayedExpansion

mode con cols=100 lines=31 >nul

set "SCRIPT_DIR=%~dp0"
set "PYTHON_EXE=C:\Users\michsmit\AppData\Local\miniconda3\envs\geomet-ua\python.exe"
set "SCRIPT_PATH=%SCRIPT_DIR%metar-cli.py"
set "DEFAULT_CONFIG=%SCRIPT_DIR%stations.txt"
set "FALLBACK_CONFIG=%SCRIPT_DIR%stations.example.txt"

if not exist "%PYTHON_EXE%" (
	echo Python interpreter not found:
	echo   %PYTHON_EXE%
	echo.
	pause
	exit /b 1
)

if exist "%DEFAULT_CONFIG%" (
	set DEFAULT_ARGS=--config "%DEFAULT_CONFIG%"
) else (
	set DEFAULT_ARGS=--config "%FALLBACK_CONFIG%"
)

set "CURRENT_ARGS=%DEFAULT_ARGS%"

:run_loop
cls
echo metar-display launcher
echo ---------------------
echo Script : %SCRIPT_PATH%
echo Python : %PYTHON_EXE%
echo Default: %DEFAULT_ARGS%
echo Running: %CURRENT_ARGS%
echo.

"%PYTHON_EXE%" "%SCRIPT_PATH%" %CURRENT_ARGS%

echo.
echo Enter new options to run again.
echo Commands:
echo   [Enter] exit
echo   run      rerun remembered options
Echo   default  switch back to default options
echo   q        exit
echo.
set /p "NEXT_ARGS=Options> "
if errorlevel 1 exit /b 0

if /i "%NEXT_ARGS%"=="q" exit /b 0
if /i "%NEXT_ARGS%"=="quit" exit /b 0
if /i "%NEXT_ARGS%"=="exit" exit /b 0
if /i "%NEXT_ARGS%"=="run" goto run_loop
if /i "%NEXT_ARGS%"=="default" (
	set "CURRENT_ARGS=%DEFAULT_ARGS%"
	goto run_loop
)
if not defined NEXT_ARGS exit /b 0

set "CURRENT_ARGS=%NEXT_ARGS%"
goto run_loop