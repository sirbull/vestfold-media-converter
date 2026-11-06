# Lag MSI-pakken fra den ferdige programmappen (kjør scripts/build.ps1 først).
# Krever WiX 5: dotnet tool install --global wix --version 5.0.2
# WiX 5 er åpen kildekode (MS-RL). WiX 6 har andre lisensvilkår og brukes ikke.
param(
    [string]$SigningCertificateThumbprint = '',
    [string]$TimestampServer = '',
    [string]$Manufacturer = 'Vestfold Media Converter'
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$dist = Join-Path $root 'dist\VestfoldMediaConverter'
if (-not (Test-Path -LiteralPath (Join-Path $dist 'SHA256SUMS.txt'))) { throw 'Kjor scripts/build.ps1 forst.' }
if (-not (Get-Command wix -ErrorAction SilentlyContinue)) {
    throw 'WiX mangler. Installer med: dotnet tool install --global wix --version 5.0.2'
}
$wixVersion = (& wix --version) -replace '\+.*$', ''
if (-not $wixVersion.StartsWith('5.')) { throw "Forventet WiX 5, fant $wixVersion." }

$version = (Get-Content -LiteralPath (Join-Path $dist 'BUILD-INFO.json') -Raw -Encoding UTF8 | ConvertFrom-Json).version
$output = Join-Path $root "dist\VestfoldMediaConverter-$version.msi"
& wix build (Join-Path $root 'installer\VestfoldMediaConverter.wxs') -arch x64 `
    -d "Version=$version" -d "AppDir=$dist" -d "Manufacturer=$Manufacturer" `
    -d "IconFile=$(Join-Path $root 'build\vmc-ikon.ico')" -o $output
if ($LASTEXITCODE -ne 0) { throw 'WiX kunne ikke bygge MSI-pakken.' }

if ($SigningCertificateThumbprint) {
    $certificate = Get-Item -LiteralPath "Cert:\CurrentUser\My\$SigningCertificateThumbprint"
    $arguments = @{ FilePath = $output; Certificate = $certificate; HashAlgorithm = 'SHA256' }
    if ($TimestampServer) { $arguments.TimestampServer = $TimestampServer }
    $signature = Set-AuthenticodeSignature @arguments
    if ($signature.Status -ne 'Valid') { throw "Signering av MSI feilet: $($signature.StatusMessage)" }
}
$hash = (Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash.ToLowerInvariant()
$utf8 = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText("$output.sha256", "$hash  $(Split-Path $output -Leaf)`n", $utf8)
Write-Host "MSI: $output"
