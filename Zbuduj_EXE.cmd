@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0gui\build_windows.ps1"
if errorlevel 1 (
    echo Budowanie nie powiodlo sie. Sprawdz komunikaty powyzej.
    pause
    exit /b 1
)
echo Gotowa aplikacja: dist\PSIP_Mapa\PSIP_Mapa.exe
pause
