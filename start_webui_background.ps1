$ErrorActionPreference = "Stop"

$AppDir = "Z:\sjagent"
$VenvPython = Join-Path $AppDir ".venv\Scripts\python.exe"
$Python = if (Test-Path -LiteralPath $VenvPython) { $VenvPython } else { "python" }
$OutLog = Join-Path $AppDir "logs\webui-8081.out.log"
$ErrLog = Join-Path $AppDir "logs\webui-8081.err.log"

Set-Location -LiteralPath $AppDir
if (-not (Test-Path -LiteralPath "logs")) {
    New-Item -ItemType Directory -Path "logs" | Out-Null
}

$env:PYTHONIOENCODING = "utf-8"
$env:SJAGENT_CORE_DB_HOST = "114.132.197.246"
$env:SJAGENT_CORE_DB_PORT = "3306"
$env:SJAGENT_CORE_DB_NAME = "sjagent_core"
$MachinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
[Environment]::SetEnvironmentVariable("PATH", $null, "Process")
[Environment]::SetEnvironmentVariable("Path", (($MachinePath, $UserPath) -ne "" -join ";"), "Process")

Start-Process `
    -FilePath $Python `
    -ArgumentList @("main.py", "--mode", "http", "--http-port", "8081") `
    -WorkingDirectory $AppDir `
    -RedirectStandardOutput $OutLog `
    -RedirectStandardError $ErrLog `
    -WindowStyle Hidden
