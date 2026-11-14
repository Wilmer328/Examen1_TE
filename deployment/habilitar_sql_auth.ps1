# Ejecutar UNA VEZ en PowerShell COMO ADMINISTRADOR.
# Habilita autenticación mixta y TCP 1433 en SQL Server Express, reinicia el servicio y crea las
# cuentas técnicas etl_user / api_user con mínimo privilegio. Luego cambie SQL_AUTH=sql en .env.
param(
    [string]$Instance = "SQLEXPRESS",
    [Parameter(Mandatory = $true)][string]$EtlPassword,
    [Parameter(Mandatory = $true)][string]$ApiPassword
)
$ErrorActionPreference = "Stop"
$root = Split-Path $PSScriptRoot -Parent
$svc = "MSSQL`$$Instance"

# 1) Modo de autenticación mixto (LoginMode = 2)
sqlcmd -S ".\$Instance" -E -C -Q "EXEC xp_instance_regwrite N'HKEY_LOCAL_MACHINE', N'Software\Microsoft\MSSQLServer\MSSQLServer', N'LoginMode', REG_DWORD, 2"

# 2) TCP/IP habilitado en puerto fijo 1433 (necesario para Docker y herramientas externas)
$key = Get-ChildItem "HKLM:\SOFTWARE\Microsoft\Microsoft SQL Server" | Where-Object { $_.PSChildName -like "MSSQL*.$Instance" } | Select-Object -First 1
$tcp = Join-Path $key.PSPath "MSSQLServer\SuperSocketNetLib\Tcp"
Set-ItemProperty -Path $tcp -Name Enabled -Value 1
Set-ItemProperty -Path (Join-Path $tcp "IPAll") -Name TcpPort -Value "1433"
Set-ItemProperty -Path (Join-Path $tcp "IPAll") -Name TcpDynamicPorts -Value ""

# 3) Reinicio del servicio
Restart-Service -Name $svc -Force
Start-Sleep -Seconds 5

# 4) Cuentas técnicas
sqlcmd -S ".\$Instance" -E -C -I -i "$root\database\security\04_security.sql" -v ETL_PASSWORD="$EtlPassword" API_PASSWORD="$ApiPassword"

Write-Host "Listo. Actualice .env: SQL_AUTH=sql, ETL_DB_PASSWORD y API_DB_PASSWORD (y SQL_SERVER=localhost,1433 si usa TCP)." -ForegroundColor Green
