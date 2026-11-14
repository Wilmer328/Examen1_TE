/* =====================================================================
   00_create_databases.sql
   Crea las bases separadas de la plataforma:
     - WideWorldImporters : fuente operacional (OLTP) - se restaura desde .bak
     - WWI_Staging        : zona intermedia (raw / clean / ready / quarantine)
     - WWI_DW             : Data Warehouse dimensional + operación (ops, ml, ai)
   Idempotente: puede re-ejecutarse.
   ===================================================================== */
IF DB_ID('WWI_Staging') IS NULL
BEGIN
    CREATE DATABASE WWI_Staging;
    ALTER DATABASE WWI_Staging SET RECOVERY SIMPLE;
END
GO
IF DB_ID('WWI_DW') IS NULL
BEGIN
    CREATE DATABASE WWI_DW;
    ALTER DATABASE WWI_DW SET RECOVERY SIMPLE;
END
GO
