$ErrorActionPreference = "Stop"

$AppDir = "C:\Users\chuji\Downloads\sjagent\sjagent"
$Python = Join-Path $AppDir ".venv\Scripts\python.exe"
$OutLog = Join-Path $AppDir "logs\webui_manual.out.log"
$ErrLog = Join-Path $AppDir "logs\webui_manual.err.log"

Set-Location -LiteralPath $AppDir
if (-not (Test-Path -LiteralPath "logs")) {
    New-Item -ItemType Directory -Path "logs" | Out-Null
}

$env:PYTHONIOENCODING = "utf-8"
$MachinePath = [Environment]::GetEnvironmentVariable("Path", "Machine")
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
[Environment]::SetEnvironmentVariable("PATH", $null, "Process")
[Environment]::SetEnvironmentVariable("Path", (($MachinePath, $UserPath) -ne "" -join ";"), "Process")

Start-Process `
    -FilePath $Python `
    -ArgumentList @("main.py", "--mode", "http", "--http-port", "8080") `
    -WorkingDirectory $AppDir `
    -RedirectStandardOutput $OutLog `
    -RedirectStandardError $ErrLog `
    -WindowStyle Minimized
