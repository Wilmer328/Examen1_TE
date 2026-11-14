# Instalación reproducible del entorno local (Windows). Ejecutar desde la raíz del repositorio:
#   powershell -ExecutionPolicy Bypass -File deployment\setup.ps1
# Pasos: entorno Python -> dependencias frontend -> restaurar WideWorldImporters -> crear Staging/DW ->
#        carga inicial -> entrenamiento ML -> predicción -> alertas.
param(
    [string]$Server = ".\SQLEXPRESS",
    [string]$BackupPath = "C:\Users\Public\SQLBackups\WideWorldImporters-Standard.bak",
    [switch]$SkipRestore
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
Set-Location $root

Write-Host "== 1. Entorno Python" -ForegroundColor Cyan
if (-not (Test-Path .venv)) { py -3.14 -m venv .venv }
.\.venv\Scripts\python.exe -m pip install -q -r requirements.txt

Write-Host "== 2. Dependencias del frontend" -ForegroundColor Cyan
Push-Location frontend; npm install --no-audit --no-fund; Pop-Location

if (-not (Test-Path .env)) { Copy-Item .env.example .env; Write-Warning "Se creó .env desde .env.example: complete JWT_SECRET, APP_USERS y ANTHROPIC_API_KEY." }

if (-not $SkipRestore) {
    Write-Host "== 3. Fuente WideWorldImporters" -ForegroundColor Cyan
    if (-not (Test-Path $BackupPath)) {
        New-Item -ItemType Directory -Force (Split-Path $BackupPath) | Out-Null
        Invoke-WebRequest "https://github.com/Microsoft/sql-server-samples/releases/download/wide-world-importers-v1.0/WideWorldImporters-Standard.bak" -OutFile $BackupPath
    }
    $data = (sqlcmd -S $Server -E -C -h -1 -W -Q "SET NOCOUNT ON; SELECT CAST(SERVERPROPERTY('InstanceDefaultDataPath') AS nvarchar(400))").Trim()
    sqlcmd -S $Server -E -C -b -Q "RESTORE DATABASE WideWorldImporters FROM DISK=N'$BackupPath' WITH MOVE 'WWI_Primary' TO N'${data}WWI.mdf', MOVE 'WWI_UserData' TO N'${data}WWI_UserData.ndf', MOVE 'WWI_Log' TO N'${data}WWI.ldf', REPLACE"
}

Write-Host "== 4. Bases Staging y DW (scripts en orden)" -ForegroundColor Cyan
foreach ($f in "database\00_create_databases.sql", "database\staging\01_staging_schema.sql",
               "database\data-warehouse\02_dw_schema.sql", "database\data-warehouse\03_dw_load_procs.sql") {
    sqlcmd -S $Server -E -C -b -I -i $f
}

Write-Host "== 5. Carga inicial + ML + alertas" -ForegroundColor Cyan
.\.venv\Scripts\python.exe -m etl.pipeline --mode initial --no-post
.\.venv\Scripts\python.exe -m machine_learning.train
.\.venv\Scripts\python.exe -m machine_learning.predict
.\.venv\Scripts\python.exe -m notifications.alerts --no-ai
Write-Host "Instalación completa. Inicie la app con deployment\start.ps1" -ForegroundColor Green
