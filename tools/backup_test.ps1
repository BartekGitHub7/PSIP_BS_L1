# Uruchom z katalogu repo. Nie zapisuje hasła i nie zmienia danych bazy.
# Binarny dump kopiujemy przez docker cp, bez przekierowania > w PowerShell.
[CmdletBinding()]
param(
    [string]$Container = 'remote-db-env-test-postgis-1',
    [string]$Database = 'psip',
    [string]$DatabaseUser = 'psip'
)
$ErrorActionPreference = 'Stop'
$backupDirectory = Join-Path (Get-Location) 'backups'
New-Item -ItemType Directory -Force -Path $backupDirectory | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$archiveName = "env-test_$stamp.dump"
$archiveInContainer = "/tmp/$archiveName"
$destination = Join-Path $backupDirectory $archiveName
if (Test-Path -LiteralPath $destination) {
    throw "Kopia o tej nazwie już istnieje: $destination"
}
& docker exec $Container pg_dump -U $DatabaseUser -d $Database -Fc -f $archiveInContainer
if ($LASTEXITCODE -ne 0) { throw 'pg_dump nie wykonał kopii.' }
& docker exec $Container pg_restore --list $archiveInContainer | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Nie można odczytać struktury archiwum.' }
$copySource = "${Container}:$archiveInContainer"
& docker cp $copySource $destination
if ($LASTEXITCODE -ne 0) { throw 'Nie udało się skopiować archiwum na Windows.' }
$info = Get-Item -LiteralPath $destination
if ($info.Length -eq 0) { throw 'Plik kopii jest pusty.' }
$hash = Get-FileHash -Algorithm SHA256 -LiteralPath $destination
$hashLine = "$($hash.Hash)  $archiveName"
Set-Content -LiteralPath "$destination.sha256" -Value $hashLine -Encoding Ascii
Write-Host "Zapisano: $destination"
Write-Host "Rozmiar: $($info.Length) bajtów"
Write-Host "SHA256: $($hash.Hash)"
Write-Host 'Archiwum jest czytelne; pełne odtworzenie należy sprawdzić w osobnej bazie.'
Write-Host 'Nie dodawaj folderu backups do Git. Skopiuj backup też poza ten dysk.'
