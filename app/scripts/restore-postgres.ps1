$ErrorActionPreference = "Stop"

if (-not $env:HAJIRIFLOW_RESTORE_TARGET_URL) {
    throw "Set HAJIRIFLOW_RESTORE_TARGET_URL to the target PostgreSQL URL."
}
if (-not $env:HAJIRIFLOW_RESTORE_BACKUP_PATH) {
    throw "Set HAJIRIFLOW_RESTORE_BACKUP_PATH to a .dump backup."
}
if ($env:HAJIRIFLOW_RESTORE_CONFIRM -ne "I_UNDERSTAND_THIS_REPLACES_THE_TARGET") {
    throw "Restore confirmation phrase is invalid."
}
if (-not (Test-Path $env:HAJIRIFLOW_RESTORE_BACKUP_PATH)) {
    throw "Backup file does not exist."
}
if ((Get-Item $env:HAJIRIFLOW_RESTORE_BACKUP_PATH).Length -eq 0) {
    throw "Backup file is empty."
}
if ($env:HAJIRIFLOW_ENVIRONMENT -eq "production" -and $env:HAJIRIFLOW_ALLOW_PRODUCTION_RESTORE -ne "yes") {
    throw "Production restore is blocked unless HAJIRIFLOW_ALLOW_PRODUCTION_RESTORE=yes."
}

$checksum = "$($env:HAJIRIFLOW_RESTORE_BACKUP_PATH).sha256"
if (Test-Path $checksum) {
    $expected = ((Get-Content $checksum -Raw).Trim() -split "\s+")[0].ToLowerInvariant()
    $actual = (Get-FileHash -Algorithm SHA256 $env:HAJIRIFLOW_RESTORE_BACKUP_PATH).Hash.ToLowerInvariant()
    if ($actual -ne $expected) { throw "Backup checksum verification failed." }
}

Get-Content -AsByteStream -Raw $env:HAJIRIFLOW_RESTORE_BACKUP_PATH | & pg_restore --dbname=$env:HAJIRIFLOW_RESTORE_TARGET_URL --clean --if-exists --no-owner --no-acl
if ($LASTEXITCODE -ne 0) { throw "pg_restore failed." }
Write-Output "HajiriFlow PostgreSQL restore completed into the explicitly configured target."
