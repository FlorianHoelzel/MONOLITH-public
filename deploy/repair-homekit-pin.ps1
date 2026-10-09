param([Parameter(Mandatory = $true)][string]$Target)

$ErrorActionPreference = "Stop"
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$environmentPath = Join-Path $projectRoot ".env"
if (-not (Test-Path -LiteralPath $environmentPath)) {
    throw "Lokale .env fehlt. Der bisherige HomeKit-PIN muss privat wiederhergestellt werden."
}
$configuration = [IO.File]::ReadAllText($environmentPath)
$pinEntries = [regex]::Matches($configuration, '(?m)^[ \t]*(?:export[ \t]+)?HOMEKIT_PIN[ \t]*=[ \t]*([^\r\n]*)')
if ($pinEntries.Count -eq 0) { throw "HOMEKIT_PIN fehlt in der lokalen .env." }
$pin = ($pinEntries[$pinEntries.Count - 1].Groups[1].Value -split '#', 2)[0].Trim().Trim([char[]]@([char]34, [char]39))
if ($pin -notmatch '^[0-9]{3}-[0-9]{2}-[0-9]{3}$') { throw "Lokaler HOMEKIT_PIN ist ungültig." }

$recoveryId = [guid]::NewGuid().ToString("N")
$temporaryRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$pinPath = [IO.Path]::GetFullPath((Join-Path $temporaryRoot "monolith-homekit-$recoveryId.pin"))
if (-not $pinPath.StartsWith($temporaryRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Temporärer Pfad außerhalb des erlaubten Verzeichnisses."
}
$remoteDirectory = ".monolith-homekit-recovery-$recoveryId"

try {
    [IO.File]::WriteAllText($pinPath, $pin, [Text.UTF8Encoding]::new($false))
    & ssh $Target "umask 077; mkdir '$remoteDirectory'"
    if ($LASTEXITCODE -ne 0) { throw "Privates Wiederherstellungsverzeichnis konnte nicht erstellt werden." }
    & scp $pinPath "${Target}:${remoteDirectory}/pin"
    if ($LASTEXITCODE -ne 0) { throw "PIN-Übertragung fehlgeschlagen." }
    & scp (Join-Path $PSScriptRoot "migrate-homekit-pin.py") "${Target}:${remoteDirectory}/migrate.py"
    if ($LASTEXITCODE -ne 0) { throw "Übertragung des Wiederherstellungswerkzeugs fehlgeschlagen." }
    & ssh -t $Target (
        "sudo python3 '$remoteDirectory/migrate.py' --pin-file '$remoteDirectory/pin' " +
        "--env-file /etc/monolith/monolith.env && " +
        "rm -f '$remoteDirectory/pin' '$remoteDirectory/migrate.py' && " +
        "rmdir '$remoteDirectory' && " +
        "sudo systemctl restart monolith-homekit.service && " +
        "sleep 3 && " +
        "systemctl is-active monolith-homekit.service"
    )
    if ($LASTEXITCODE -ne 0) { throw "Wiederherstellung oder Neustart fehlgeschlagen." }
    Write-Host "HomeKit-PIN wiederhergestellt und Bridge neu gestartet."
}
finally {
    if (Test-Path -LiteralPath $pinPath) { Remove-Item -LiteralPath $pinPath -Force }
    & ssh $Target "rm -f '$remoteDirectory/pin' '$remoteDirectory/migrate.py'; rmdir '$remoteDirectory' 2>/dev/null || true"
}
