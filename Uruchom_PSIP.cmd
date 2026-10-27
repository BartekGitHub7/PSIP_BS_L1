@echo off
setlocal
if exist "%~dp0dist\PSIP_Mapa\PSIP_Mapa.exe" (
    start "" "%~dp0dist\PSIP_Mapa\PSIP_Mapa.exe"
    exit /b 0
)
if exist "%~dp0dist\PSIP_Mapa.exe" (
    start "" "%~dp0dist\PSIP_Mapa.exe"
    exit /b 0
)
if exist "%~dp0.venv-gui\Scripts\pythonw.exe" (
    start "" "%~dp0.venv-gui\Scripts\pythonw.exe" "%~dp0gui\main.py"
    exit /b 0
)
if exist "%~dp0.venv-build\Scripts\pythonw.exe" (
    start "" "%~dp0.venv-build\Scripts\pythonw.exe" "%~dp0gui\main.py"
    exit /b 0
)
echo Brak gotowej aplikacji. Uruchom Zbuduj_EXE.cmd albo przygotuj .venv-gui.
pause
exit /b 1
