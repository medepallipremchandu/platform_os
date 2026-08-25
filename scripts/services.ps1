<#
.SYNOPSIS
    Start, stop and inspect every TalentOS service - backends and frontends - from one place.

.DESCRIPTION
    One table for the whole platform, and one command to bring it up or down in dependency
    order. Each service starts in its own PowerShell window titled with its name, so logs stay
    readable per service instead of interleaving into one stream.

    Dependency order matters and is baked in: iam-service issues the tokens every other backend
    validates, so it starts first and stops last. Frontends are pure relying parties and come
    up last.

    Phantom listeners: this repo has repeatedly hit a Windows condition where a killed uvicorn
    leaves a socket in LISTEN with no surviving process record - it ignores Stop-Process and
    taskkill, keeps serving stale code, and refuses new binds. Ports 8002, 8003 and 8103 have
    all been lost to it. `stop` detects the condition and says so explicitly rather than letting
    you spend an hour wondering why your changes have no effect. The accepted remedy is to move
    the service to a new port and repoint every consuming .env.

.PARAMETER Action
    status  (default) - show what is running
    start   - start everything not already running
    stop    - stop everything
    restart - stop everything, then start it again

.PARAMETER Only
    Limit the action to named services, e.g. -Only iam-service,iam-console

.PARAMETER Backend
    Limit the action to backend services.

.PARAMETER Frontend
    Limit the action to frontends.

.EXAMPLE
    .\services.ps1
    .\services.ps1 restart
    .\services.ps1 restart -Only iam-service,portal
    .\services.ps1 start -Backend
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('status', 'start', 'stop', 'restart')]
    [string]$Action = 'status',

    [string[]]$Only,
    [switch]$Backend,
    [switch]$Frontend
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot

# --- The platform, in start order -------------------------------------------------------------
#
# Port is $null for a process that listens on nothing (the Celery worker); those are tracked by
# a command-line signature instead. `Wait` is how long to give a service to claim its port
# before the next one starts - only iam-service really needs it, because everything else
# validates tokens against its JWKS on first request.

$Services = @(
    @{ Name = 'iam-service';             Kind = 'backend';  Port = 8113; Dir = 'backend\iam-service';           Exe = '.venv\Scripts\python.exe'; Args = 'main.py';       Wait = 12 }
    @{ Name = 'notification-service';    Kind = 'backend';  Port = 8104; Dir = 'backend\notification-service';  Exe = '.venv\Scripts\python.exe'; Args = 'main.py';       Wait = 0 }
    @{ Name = 'notification-worker';     Kind = 'backend';  Port = $null; Dir = 'backend\notification-service'; Exe = '.venv\Scripts\python.exe'; Args = 'run_worker.py'; Wait = 0; Match = 'run_worker.py' }
    @{ Name = 'agent-builder-service';   Kind = 'backend';  Port = 8102; Dir = 'backend\agent-builder-service'; Exe = '.venv\Scripts\python.exe'; Args = 'main.py';       Wait = 0 }
    @{ Name = 'voice-agent-service';     Kind = 'backend';  Port = 8004; Dir = 'backend\voice-agent-service';   Exe = '.venv\Scripts\python.exe'; Args = 'main.py';       Wait = 0 }
    @{ Name = 'talentos-app-api';        Kind = 'backend';  Port = 8000; Dir = 'backend\talentos-app';          Exe = '.venv\Scripts\python.exe'; Args = 'main.py';       Wait = 0 }
    @{ Name = 'talentos-app';            Kind = 'frontend'; Port = 5173; Dir = 'frontend\talentos-app';         Exe = 'npm.cmd'; Args = 'run dev'; Wait = 0 }
    @{ Name = 'iam-console';             Kind = 'frontend'; Port = 5174; Dir = 'frontend\iam-console';          Exe = 'npm.cmd'; Args = 'run dev'; Wait = 0 }
    @{ Name = 'portal';                  Kind = 'frontend'; Port = 5175; Dir = 'frontend\portal';               Exe = 'npm.cmd'; Args = 'run dev'; Wait = 0 }
    @{ Name = 'agent-builder-console';   Kind = 'frontend'; Port = 5176; Dir = 'frontend\agent-builder-console'; Exe = 'npm.cmd'; Args = 'run dev'; Wait = 0 }
    @{ Name = 'voice-agent-console';     Kind = 'frontend'; Port = 5177; Dir = 'frontend\voice-agent-console';  Exe = 'npm.cmd'; Args = 'run dev'; Wait = 0 }
)

function Select-Targets {
    $selected = $Services
    if ($Backend)  { $selected = $selected | Where-Object { $_.Kind -eq 'backend' } }
    if ($Frontend) { $selected = $selected | Where-Object { $_.Kind -eq 'frontend' } }
    if ($Only)     { $selected = $selected | Where-Object { $Only -contains $_.Name } }
    if (-not $selected) { throw "No services matched. Known names: $(($Services.Name) -join ', ')" }
    return $selected
}

function Get-PortOwner([int]$Port) {
    $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $conn) { return $null }
    return $conn.OwningProcess
}

function Get-WorkerPids($svc) {
    # No port to look for, so match on the command line. Filtered to this repo's own path so a
    # worker from another checkout on the same machine is left alone.
    $needle = Join-Path $Root $svc.Dir
    Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and $_.CommandLine -like "*$($svc.Match)*" -and $_.CommandLine -like "*$needle*" } |
        Select-Object -ExpandProperty ProcessId
}

function Get-ServiceState($svc) {
    if ($null -eq $svc.Port) {
        $procIds = @(Get-WorkerPids $svc)
        if ($procIds.Count -gt 0) { return @{ Up = $true; Pid = $procIds[0]; Phantom = $false } }
        return @{ Up = $false; Pid = $null; Phantom = $false }
    }

    $owner = Get-PortOwner $svc.Port
    if (-not $owner) { return @{ Up = $false; Pid = $null; Phantom = $false } }

    $proc = Get-CimInstance Win32_Process -Filter "ProcessId = $owner" -ErrorAction SilentlyContinue
    # A socket in LISTEN whose owning process no longer exists: the phantom this repo keeps
    # hitting. It answers requests with stale code and blocks any new bind.
    return @{ Up = $true; Pid = $owner; Phantom = ($null -eq $proc) }
}

function Show-Status {
    $rows = foreach ($svc in $Services) {
        $state = Get-ServiceState $svc
        $status = if ($state.Phantom) { 'PHANTOM' } elseif ($state.Up) { 'running' } else { 'stopped' }
        [pscustomobject]@{
            Service = $svc.Name
            Kind    = $svc.Kind
            Port    = if ($null -eq $svc.Port) { '-' } else { $svc.Port }
            Status  = $status
            PID     = if ($state.Pid) { $state.Pid } else { '' }
            URL     = if ($null -eq $svc.Port) { '' } else { "http://localhost:$($svc.Port)" }
        }
    }
    $rows | Format-Table -AutoSize

    if ($rows | Where-Object { $_.Status -eq 'PHANTOM' }) {
        Write-Host ''
        Write-Warning @'
A PHANTOM listener is present: a socket still in LISTEN whose process no longer exists.
It will keep serving STALE CODE and refuse new binds, and it survives Stop-Process/taskkill.
This has happened on ports 8002, 8003 and 8103 in this repo. The remedy that works is to move
that service to a new port and repoint every consuming .env (and .env.example, and the READMEs).
'@
    }
}

function Stop-Targets($targets) {
    foreach ($svc in @($targets)[($targets.Count - 1)..0]) {   # reverse: iam-service last
        $state = Get-ServiceState $svc
        if (-not $state.Up) {
            Write-Host ("  {0,-24} already stopped" -f $svc.Name)
            continue
        }

        if ($null -eq $svc.Port) {
            foreach ($procId in Get-WorkerPids $svc) { Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue }
        }
        else {
            # A reloading uvicorn runs its real server in a multiprocessing child with a
            # different PID than the parent, so killing the port owner alone can leave the
            # parent alive to respawn it. Take the whole tree.
            $owner = $state.Pid
            $children = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
                Where-Object { $_.ParentProcessId -eq $owner } |
                Select-Object -ExpandProperty ProcessId
            foreach ($procId in @($children) + @($owner)) {
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            }
        }

        Start-Sleep -Milliseconds 700
        $after = Get-ServiceState $svc
        if ($after.Phantom) {
            Write-Host ("  {0,-24} STOPPED, but port {1} is now a PHANTOM listener" -f $svc.Name, $svc.Port) -ForegroundColor Red
        }
        elseif ($after.Up) {
            Write-Host ("  {0,-24} did not stop (pid {1})" -f $svc.Name, $after.Pid) -ForegroundColor Yellow
        }
        else {
            Write-Host ("  {0,-24} stopped" -f $svc.Name) -ForegroundColor DarkGray
        }
    }
}

function Start-Targets($targets) {
    foreach ($svc in $targets) {
        $state = Get-ServiceState $svc
        if ($state.Phantom) {
            Write-Host ("  {0,-24} SKIPPED - port {1} is held by a phantom listener" -f $svc.Name, $svc.Port) -ForegroundColor Red
            continue
        }
        if ($state.Up) {
            Write-Host ("  {0,-24} already running (pid {1})" -f $svc.Name, $state.Pid)
            continue
        }

        $dir = Join-Path $Root $svc.Dir
        if (-not (Test-Path $dir)) {
            Write-Host ("  {0,-24} SKIPPED - {1} not found" -f $svc.Name, $dir) -ForegroundColor Yellow
            continue
        }

        # -NoExit so the window stays open with its logs (and with any startup traceback) rather
        # than vanishing the instant something fails.
        $inner = "`$host.UI.RawUI.WindowTitle = '$($svc.Name)'; & '$($svc.Exe)' $($svc.Args)"
        Start-Process -FilePath 'powershell.exe' `
                      -ArgumentList '-NoExit', '-NoProfile', '-Command', $inner `
                      -WorkingDirectory $dir | Out-Null

        Write-Host ("  {0,-24} starting..." -f $svc.Name) -ForegroundColor DarkGray

        if ($svc.Wait -gt 0 -and $null -ne $svc.Port) {
            $deadline = (Get-Date).AddSeconds($svc.Wait)
            while ((Get-Date) -lt $deadline -and -not (Get-PortOwner $svc.Port)) { Start-Sleep -Milliseconds 400 }
        }
    }
}

# --- Run --------------------------------------------------------------------------------------

Write-Host ''
switch ($Action) {
    'status' {
        Show-Status
    }
    'stop' {
        Write-Host 'Stopping services...' -ForegroundColor Cyan
        Stop-Targets (Select-Targets)
        Write-Host ''
        Show-Status
    }
    'start' {
        Write-Host 'Starting services...' -ForegroundColor Cyan
        Start-Targets (Select-Targets)
        Write-Host ''
        Write-Host 'Giving everything a few seconds to bind...' -ForegroundColor DarkGray
        Start-Sleep -Seconds 8
        Show-Status
    }
    'restart' {
        Write-Host 'Stopping services...' -ForegroundColor Cyan
        Stop-Targets (Select-Targets)
        Start-Sleep -Seconds 2
        Write-Host ''
        Write-Host 'Starting services...' -ForegroundColor Cyan
        Start-Targets (Select-Targets)
        Write-Host ''
        Write-Host 'Giving everything a few seconds to bind...' -ForegroundColor DarkGray
        Start-Sleep -Seconds 10
        Show-Status
    }
}
Write-Host ''
