#!/bin/bash
# Inicialización del contenedor SQL Server (servicio "init" de docker-compose).
set -e
SQLCMD="/opt/mssql-tools18/bin/sqlcmd -S sqlserver -U sa -P $SA -C -b -I"
BAK=/var/opt/mssql/backup/WideWorldImporters-Standard.bak
mkdir -p /var/opt/mssql/backup
if [ ! -f "$BAK" ]; then
  curl -fsSL -o "$BAK" https://github.com/Microsoft/sql-server-samples/releases/download/wide-world-importers-v1.0/WideWorldImporters-Standard.bak
fi
$SQLCMD -Q "IF DB_ID('WideWorldImporters') IS NULL RESTORE DATABASE WideWorldImporters FROM DISK='$BAK' WITH MOVE 'WWI_Primary' TO '/var/opt/mssql/data/WWI.mdf', MOVE 'WWI_UserData' TO '/var/opt/mssql/data/WWI_UserData.ndf', MOVE 'WWI_Log' TO '/var/opt/mssql/data/WWI.ldf'"
for f in 00_create_databases.sql staging/01_staging_schema.sql data-warehouse/02_dw_schema.sql data-warehouse/03_dw_load_procs.sql; do
  $SQLCMD -i "/scripts/$f"
done
$SQLCMD -i /scripts/security/04_security.sql -v ETL_PASSWORD="$ETL_PASSWORD" API_PASSWORD="$API_PASSWORD"
echo "Inicialización completa"
