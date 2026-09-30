# Restores the separately built baseline package; leaves the working branch intact.
$ErrorActionPreference = 'Stop'
if (Get-Process Cities2 -ErrorAction SilentlyContinue) { throw 'Exit Cities: Skylines II before restoring the baseline.' }
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$package = Join-Path $taskRoot 'artifacts\BaselineMod'
if (-not (Test-Path -LiteralPath (Join-Path $package 'Airport Details Pack Countinue.dll'))) {
    throw 'The baseline package is missing. Use the retained baseline Git tag to rebuild it.'
}
$modsParent = [IO.Path]::GetFullPath((Join-Path $env:USERPROFILE 'AppData\LocalLow\Colossal Order\Cities Skylines II\Mods'))
$destination = [IO.Path]::GetFullPath((Join-Path $modsParent 'Airport Details Pack Countinue'))
if ((Split-Path -Parent $destination) -ne $modsParent -or (Split-Path -Leaf $destination) -ne 'Airport Details Pack Countinue') {
    throw 'Unexpected local mod destination.'
}
if (Test-Path -LiteralPath $destination) {
    $backup = Join-Path $taskRoot ('artifacts\before-baseline-restore-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
    Copy-Item -LiteralPath $destination -Destination $backup -Recurse
    # The absolute target and exact named parent have been verified above.
    Remove-Item -LiteralPath $destination -Recurse -Force
    Write-Output "Previous installed package saved: $backup"
}
New-Item -ItemType Directory -Path $modsParent -Force | Out-Null
Copy-Item -LiteralPath $package -Destination $destination -Recurse
Write-Output "Baseline installed: $destination"
