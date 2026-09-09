$ErrorActionPreference = "Stop"

if (-not $env:HAJIRIFLOW_BACKUP_DATABASE_URL) {
    throw "Set HAJIRIFLOW_BACKUP_DATABASE_URL to a PostgreSQL URL."
}
if (-not $env:HAJIRIFLOW_BACKUP_PATH) {
    throw "Set HAJIRIFLOW_BACKUP_PATH to the destination .dump file."
}
if (-not $env:HAJIRIFLOW_BACKUP_PATH.EndsWith(".dump")) {
    throw "Backup path must end in .dump."
}

$destination = [System.IO.Path]::GetFullPath($env:HAJIRIFLOW_BACKUP_PATH)
$directory = [System.IO.Path]::GetDirectoryName($destination)
if (-not [System.IO.Directory]::Exists($directory)) {
    [System.IO.Directory]::CreateDirectory($directory) | Out-Null
}
$temporary = "$destination.tmp.$PID"
try {
    & pg_dump --dbname=$env:HAJIRIFLOW_BACKUP_DATABASE_URL --format=custom --no-owner --no-acl --file=$temporary
    if ($LASTEXITCODE -ne 0) { throw "pg_dump failed." }
    if (-not (Test-Path $temporary) -or (Get-Item $temporary).Length -eq 0) {
        throw "Backup output is empty."
    }
    Move-Item -Force $temporary $destination
    $hash = (Get-FileHash -Algorithm SHA256 $destination).Hash.ToLowerInvariant()
    $name = [System.IO.Path]::GetFileName($destination)
    Set-Content -NoNewline -Encoding ASCII -Path "$destination.sha256" -Value "$hash  $name`n"
    Write-Output "HajiriFlow PostgreSQL backup completed: $destination"
}
finally {
    if (Test-Path $temporary) { Remove-Item -Force $temporary }
}
