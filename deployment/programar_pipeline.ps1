# Programa el pipeline incremental cada 15 minutos con el Programador de tareas de Windows
# (orquestación ligera; Airflow no se justifica para un único DAG lineal - ver documentation/02_arquitectura.md).
#   powershell -ExecutionPolicy Bypass -File deployment\programar_pipeline.ps1            # crear
#   powershell -ExecutionPolicy Bypass -File deployment\programar_pipeline.ps1 -Remove    # eliminar
param([int]$Minutes = 15, [switch]$Remove)
$name = "WWI_Pipeline_Incremental"
if ($Remove) { Unregister-ScheduledTask -TaskName $name -Confirm:$false; return }
$root = Split-Path $PSScriptRoot -Parent
$action = New-ScheduledTaskAction -Execute "$root\.venv\Scripts\python.exe" -Argument "-m etl.pipeline --triggered-by scheduler" -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $Minutes)
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 5)
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings -Description "ETL incremental WWI -> Staging -> DW + ML + alertas" -Force
Write-Host "Tarea '$name' programada cada $Minutes minutos (sin ejecuciones simultáneas, 2 reintentos)."
