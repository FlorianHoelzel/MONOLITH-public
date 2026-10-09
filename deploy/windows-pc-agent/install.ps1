#Requires -RunAsAdministrator

[CmdletBinding()]
param(
    [string]$PythonPath = "C:\Python314\python.exe",
    [string]$TaskName = "PC Agent"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$agentDirectory = Split-Path -Parent $PSCommandPath
$agentPath = Join-Path $agentDirectory "pc_agent.py"
$requirementsPath = Join-Path $agentDirectory "requirements.txt"
$pythonDirectory = Split-Path -Parent $PythonPath
$pythonwPath = Join-Path $pythonDirectory "pythonw.exe"
$tokenDirectory = Join-Path $env:LOCALAPPDATA "MONOLITH"
$tokenPath = Join-Path $tokenDirectory "pc-agent-token.txt"
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

foreach ($requiredPath in @(
    $PythonPath,
    $pythonwPath,
    $agentPath,
    $requirementsPath
)) {
    if (-not (Test-Path -LiteralPath $requiredPath)) {
        throw "Benötigte Datei fehlt: $requiredPath"
    }
}

Write-Host "Installiere die Windows-Medienabhängigkeiten..."
& $PythonPath -m pip install --user -r $requirementsPath

if ($LASTEXITCODE -ne 0) {
    throw "Die Python-Abhängigkeiten konnten nicht installiert werden."
}

New-Item -ItemType Directory -Path $tokenDirectory -Force | Out-Null

$secureToken = Read-Host `
    "Bestehenden PC_AGENT_TOKEN eingeben" `
    -AsSecureString
$tokenPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR(
    $secureToken
)

try {
    $plainToken = [Runtime.InteropServices.Marshal]::PtrToStringBSTR(
        $tokenPointer
    )

    if ([string]::IsNullOrWhiteSpace($plainToken)) {
        throw "Das Token darf nicht leer sein."
    }

    [IO.File]::WriteAllText(
        $tokenPath,
        $plainToken.Trim(),
        [Text.UTF8Encoding]::new($false)
    )
}
finally {
    if ($tokenPointer -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR(
            $tokenPointer
        )
    }

    $plainToken = $null
}

$tokenAcl = New-Object Security.AccessControl.FileSecurity
$tokenAcl.SetOwner(
    [Security.Principal.NTAccount]$currentUser
)
$tokenAcl.SetAccessRuleProtection($true, $false)
$tokenRule = New-Object Security.AccessControl.FileSystemAccessRule(
    $currentUser,
    "FullControl",
    "Allow"
)
$tokenAcl.AddAccessRule($tokenRule)
Set-Acl -LiteralPath $tokenPath -AclObject $tokenAcl

$taskAction = New-ScheduledTaskAction `
    -Execute $pythonwPath `
    -Argument ('"{0}"' -f $agentPath)
$taskTrigger = New-ScheduledTaskTrigger -AtLogOn -User $currentUser
$taskPrincipal = New-ScheduledTaskPrincipal `
    -UserId $currentUser `
    -LogonType Interactive `
    -RunLevel Highest
$taskSettings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

$existingTask = Get-ScheduledTask `
    -TaskName $TaskName `
    -ErrorAction SilentlyContinue

if (
    ($null -ne $existingTask) -and
    ($existingTask.State -eq "Running")
) {
    Stop-ScheduledTask -TaskName $TaskName

    for ($attempt = 0; $attempt -lt 20; $attempt++) {
        $state = (
            Get-ScheduledTask -TaskName $TaskName
        ).State

        if ($state -ne "Running") {
            break
        }

        Start-Sleep -Milliseconds 250
    }
}

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $taskAction `
    -Trigger $taskTrigger `
    -Principal $taskPrincipal `
    -Settings $taskSettings `
    -Description "MONOLITH PC- und Medienstatus" `
    -Force | Out-Null

Start-ScheduledTask -TaskName $TaskName

Write-Host "PC-Agent wurde installiert und gestartet."
Write-Host "Medienstatus: http://127.0.0.1:8765/media"
