# Reinicia el ambiente de prueba: elimina Staging y DW, restaura la fuente original (descarta datos SIMULADOS)
# y vuelve a ejecutar la instalación completa. Úselo para recuperar un estado conocido.
param([string]$Server = ".\SQLEXPRESS")
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$confirm = Read-Host "Esto ELIMINA WWI_Staging y WWI_DW y restaura WideWorldImporters. Escriba SI para continuar"
if ($confirm -ne "SI") { return }
sqlcmd -S $Server -E -C -b -Q "IF DB_ID('WWI_DW') IS NOT NULL BEGIN ALTER DATABASE WWI_DW SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE WWI_DW; END; IF DB_ID('WWI_Staging') IS NOT NULL BEGIN ALTER DATABASE WWI_Staging SET SINGLE_USER WITH ROLLBACK IMMEDIATE; DROP DATABASE WWI_Staging; END"
sqlcmd -S $Server -E -C -b -Q "ALTER DATABASE WideWorldImporters SET SINGLE_USER WITH ROLLBACK IMMEDIATE"
Remove-Item "$root\machine_learning\models\*.joblib" -ErrorAction SilentlyContinue
& "$PSScriptRoot\setup.ps1" -Server $Server
