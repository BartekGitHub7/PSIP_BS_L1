# Budowanie natywnej aplikacji Windows. Bez hasła do bazy i bez zmian danych.
[CmdletBinding()]
param([switch]$OneFile, [string]$PythonExecutable = "")
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Ten skrypt uruchom na Windowsie.' }
$projectRoot = Split-Path -Parent $PSScriptRoot
$buildEnvironment = Join-Path $projectRoot '.venv-build'
$python = Join-Path $buildEnvironment 'Scripts\python.exe'
$entryPoint = Join-Path $PSScriptRoot 'main.py'
if (-not (Test-Path -LiteralPath $python)) {
    if ($PythonExecutable) {
        & $PythonExecutable -m venv $buildEnvironment
    } else {
        if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
            throw 'Brak polecenia py. Zainstaluj Python dla Windows z Tkinter i Python Launcher.'
        }
        & py -3 -m venv $buildEnvironment
    }
    if ($LASTEXITCODE -ne 0) { throw 'Nie udało się utworzyć środowiska budowania.' }
}
& $python -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt') -r (Join-Path $PSScriptRoot 'requirements-build.txt')
if ($LASTEXITCODE -ne 0) { throw 'Instalacja zależności nie powiodła się.' }
# Test prawdziwego okna Tkinter; nie łączy się z bazą.
& $python $entryPoint --smoke-test
if ($LASTEXITCODE -ne 0) { throw 'Test uruchomienia GUI nie powiódł się.' }
$buildRoot = Join-Path $projectRoot 'build'
$icon = Join-Path $buildRoot 'psip.ico'
& $python $entryPoint --write-icon $icon
if ($LASTEXITCODE -ne 0) { throw 'Nie udało się przygotować ikony.' }
$mode = if ($OneFile) { '--onefile' } else { '--onedir' }
$arguments = @(
    '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed', $mode,
    '--name', 'PSIP_Mapa', '--icon', $icon,
    '--distpath', (Join-Path $projectRoot 'dist'),
    '--workpath', (Join-Path $buildRoot 'pyinstaller'), '--specpath', $buildRoot,
    '--collect-all', 'psycopg_binary', '--collect-all', 'shapely',
    '--collect-submodules', 'mapbox_vector_tile',
    '--copy-metadata', 'mapbox-vector-tile',
    '--hidden-import', 'matplotlib.backends.backend_agg', $entryPoint
)
& $python @arguments
if ($LASTEXITCODE -ne 0) { throw 'Budowanie EXE nie powiodło się.' }
$output = if ($OneFile) { Join-Path $projectRoot 'dist\PSIP_Mapa.exe' } else { Join-Path $projectRoot 'dist\PSIP_Mapa\PSIP_Mapa.exe' }
if (-not (Test-Path -LiteralPath $output)) { throw 'Nie znaleziono wynikowego EXE.' }
# Test paczki: kontrolowany proces i limit 60 s, bez połączenia z PostGIS.
$testProcess = Start-Process -FilePath $output -ArgumentList '--smoke-test' -PassThru
if (-not $testProcess.WaitForExit(60000)) {
    $testProcess.Kill()
    throw 'EXE nie zakończyło testu w 60 sekund. Sprawdź logi budowania.'
}
$testProcess.WaitForExit()
if ($testProcess.ExitCode -ne 0) { throw "Test EXE zwrócił kod $($testProcess.ExitCode)." }
Write-Host "Gotowe: $output"
if (-not $OneFile) { Write-Host 'Przenoś cały folder dist\PSIP_Mapa, łącznie z _internal.' }
Write-Host 'Aplikacja nie uruchamia Dockera. Baza PostGIS musi działać osobno.'
