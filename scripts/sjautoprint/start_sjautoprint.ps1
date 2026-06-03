$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $PSCommandPath
$ServiceName = "sjAutoPrint"
$ConfigPath = Join-Path $ScriptRoot "config.json"

function Test-IsAdmin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Wait-BeforeExit {
    Write-Host ""
    Read-Host "Press Enter to close"
}

if (-not (Test-IsAdmin)) {
    Start-Process powershell.exe -Verb RunAs -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        "`"$PSCommandPath`""
    )
    exit
}

try {
    Write-Host "sjAutoPrint local print service" -ForegroundColor Cyan
    Write-Host "--------------------------------"

    $service = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if (-not $service) {
        Write-Host "Service not found: $ServiceName" -ForegroundColor Red
        Write-Host "Run the sjAutoPrint installer first."
        Wait-BeforeExit
        exit 1
    }

    if ($service.Status -eq "Running") {
        Write-Host "Service is running. Restarting to reload the latest print script ..."
        Restart-Service -Name $ServiceName -Force
        $service = Get-Service -Name $ServiceName
        $service.WaitForStatus("Running", [TimeSpan]::FromSeconds(30))
        Write-Host "Service restarted." -ForegroundColor Green
    } else {
        Write-Host "Current status: $($service.Status)"
        Write-Host "Starting $ServiceName ..."
        Start-Service -Name $ServiceName
        $service.WaitForStatus("Running", [TimeSpan]::FromSeconds(20))
        Write-Host "Service started." -ForegroundColor Green
    }

    $service = Get-Service -Name $ServiceName
    $serviceInfo = Get-CimInstance Win32_Service -Filter "Name='$ServiceName'"
    Write-Host ""
    Write-Host "Name      : $($service.Name)"
    Write-Host "Status    : $($service.Status)"
    Write-Host "StartType : $($serviceInfo.StartMode)"

    if (Test-Path -LiteralPath $ConfigPath) {
        try {
            $config = Get-Content -LiteralPath $ConfigPath -Raw -Encoding UTF8 | ConvertFrom-Json
            Write-Host "Printer   : $($config.printer_name)"
            Write-Host "Server    : $($config.base_url)"
        } catch {
            Write-Host "Config    : $ConfigPath"
        }
    }

    Write-Host ""
    Write-Host "If printing still does not work, check $ScriptRoot\logs\sjAutoPrint.out.log" -ForegroundColor Yellow
    Wait-BeforeExit
} catch {
    Write-Host ""
    Write-Host "Failed: $($_.Exception.Message)" -ForegroundColor Red
    Wait-BeforeExit
    exit 1
}
