/* =====================================================================
   04_security.sql - Cuentas técnicas con MÍNIMO PRIVILEGIO.
   Requiere autenticación mixta habilitada (deployment/habilitar_sql_auth.ps1).
   Ejecutar con variables (las contraseñas NO se guardan en el repositorio):
     sqlcmd -S .\SQLEXPRESS -E -C -I -i database\security\04_security.sql ^
            -v ETL_PASSWORD="..." API_PASSWORD="..."
   ---------------------------------------------------------------------
   etl_user : lee la fuente; escribe staging; carga DW (dw, ops, ml); sin DDL.
   api_user : solo LECTURA del DW (dw, ops, ml) + escritura acotada en
              ops.Alert / ops.NotificationDelivery / ml.Prediction / ai.AssistantLog
              + lectura de la cuarentena. NO accede a la fuente ni a tablas raw/clean.
   ===================================================================== */
USE master;
IF SUSER_ID('etl_user') IS NULL CREATE LOGIN etl_user WITH PASSWORD = '$(ETL_PASSWORD)', CHECK_POLICY = ON;
ELSE ALTER LOGIN etl_user WITH PASSWORD = '$(ETL_PASSWORD)';
IF SUSER_ID('api_user') IS NULL CREATE LOGIN api_user WITH PASSWORD = '$(API_PASSWORD)', CHECK_POLICY = ON;
ELSE ALTER LOGIN api_user WITH PASSWORD = '$(API_PASSWORD)';
GO
/* ---------------- Fuente: solo lectura para el ETL ---------------- */
USE WideWorldImporters;
IF USER_ID('etl_user') IS NULL CREATE USER etl_user FOR LOGIN etl_user;
ALTER ROLE db_datareader ADD MEMBER etl_user;
GO
/* ---------------- Staging ---------------- */
USE WWI_Staging;
IF USER_ID('etl_user') IS NULL CREATE USER etl_user FOR LOGIN etl_user;
ALTER ROLE db_datareader ADD MEMBER etl_user;
ALTER ROLE db_datawriter ADD MEMBER etl_user;
IF USER_ID('api_user') IS NULL CREATE USER api_user FOR LOGIN api_user;
GRANT SELECT ON SCHEMA::quarantine TO api_user;
GO
/* ---------------- Data Warehouse ---------------- */
USE WWI_DW;
IF USER_ID('etl_user') IS NULL CREATE USER etl_user FOR LOGIN etl_user;
ALTER ROLE db_datareader ADD MEMBER etl_user;
ALTER ROLE db_datawriter ADD MEMBER etl_user;
GRANT EXECUTE ON SCHEMA::dw TO etl_user;
GRANT EXECUTE ON SCHEMA::ops TO etl_user;
-- Los procedimientos de dimensiones usan SET IDENTITY_INSERT solo en el script DDL, no en la carga.

IF USER_ID('api_user') IS NULL CREATE USER api_user FOR LOGIN api_user;
GRANT SELECT ON SCHEMA::dw  TO api_user;
GRANT SELECT ON SCHEMA::ops TO api_user;
GRANT SELECT ON SCHEMA::ml  TO api_user;
GRANT SELECT ON SCHEMA::ai  TO api_user;
GRANT INSERT, UPDATE ON ops.Alert TO api_user;
GRANT INSERT, UPDATE ON ops.NotificationDelivery TO api_user;
GRANT INSERT, UPDATE ON ml.Prediction TO api_user;
GRANT INSERT ON ai.AssistantLog TO api_user;
DENY DELETE ON SCHEMA::dw TO api_user;
DENY INSERT, UPDATE, DELETE ON SCHEMA::dw TO api_user;
GO
PRINT 'Cuentas etl_user y api_user configuradas con mínimo privilegio.';
