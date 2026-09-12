@echo off
title VW Builder - Generador de Ejecutable

:: Detectar si existe un entorno virtual creado en la raiz del proyecto
set "PYTHON_EXE=python"
if exist "%~dp0..\venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0..\venv\Scripts\python.exe"
    echo [*] Entorno virtual detectado en venv\
) else if exist "%~dp0..\.venv\Scripts\python.exe" (
    set "PYTHON_EXE=%~dp0..\.venv\Scripts\python.exe"
    echo [*] Entorno virtual detectado en .venv\
)

"%PYTHON_EXE%" "%~dp0build.py" %*
echo.
echo Proceso finalizado.
pause
