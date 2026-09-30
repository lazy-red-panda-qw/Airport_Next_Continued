param(
    [switch]$Deploy,
    [ValidateSet('Debug', 'Release')][string]$Configuration = 'Release'
)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$staging = [IO.Path]::GetFullPath((Join-Path $taskRoot 'artifacts\LocalMod'))
if (-not $staging.StartsWith($taskRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Staging path is outside the workspace.'
}
& dotnet build (Join-Path $taskRoot 'Airport Decal Pack Countinue.sln') -c $Configuration "-p:AirportDeployDir=$staging" --nologo
if ($LASTEXITCODE -ne 0) { throw 'Build failed.' }
if (-not $Deploy) { Write-Output "Built package: $staging"; return }
if (Get-Process Cities2 -ErrorAction SilentlyContinue) { throw 'Exit Cities: Skylines II before deployment.' }
$modsParent = [IO.Path]::GetFullPath((Join-Path $env:USERPROFILE 'AppData\LocalLow\Colossal Order\Cities Skylines II\Mods'))
$destination = [IO.Path]::GetFullPath((Join-Path $modsParent 'Airport Details Pack Countinue'))
if ((Split-Path -Parent $destination) -ne $modsParent -or (Split-Path -Leaf $destination) -ne 'Airport Details Pack Countinue') {
    throw 'Unexpected local mod destination.'
}
if (Test-Path -LiteralPath $destination) {
    $backup = Join-Path $taskRoot ('artifacts\deploy-backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
    Copy-Item -LiteralPath $destination -Destination $backup -Recurse
    # The absolute target and its exact named parent have been verified above.
    Remove-Item -LiteralPath $destination -Recurse -Force
    Write-Output "Previous local package saved: $backup"
}
New-Item -ItemType Directory -Path $modsParent -Force | Out-Null
Copy-Item -LiteralPath $staging -Destination $destination -Recurse
Write-Output "Installed local test package: $destination"
