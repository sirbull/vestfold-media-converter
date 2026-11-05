# Bygg den portable programmappen, og eventuelt MSI-pakken, fra kildekoden.
#
# Forutsetning: prosjektets eget FFmpeg-bygg er installert med scripts/fetch_ffmpeg.ps1
# (med -Source), slik at kildekoden til FFmpeg kan følge med programmet.
#
#   .\scripts\build.ps1                                     usignert bygg for testing
#   .\scripts\build.ps1 -SigningCertificateThumbprint <tp> -TimestampServer <url> -Msi
#
# Signering bruker et eksisterende kodesigneringssertifikat i brukerens sertifikatlager.
# Alle EXE/DLL/PYD-filer som ikke allerede har gyldig signatur fra leverandøren signeres,
# slik at AppLocker/WDAC kan godkjenne hele programmet med én utgiverregel.
param(
    [switch]$SkipTests,
    [string]$SigningCertificateThumbprint = '',
    [string]$TimestampServer = '',
    [switch]$Msi
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$dist = Join-Path $root 'dist\VestfoldMediaConverter'

function Set-ProjectSignature([string[]]$Files) {
    $certificate = Get-Item -LiteralPath "Cert:\CurrentUser\My\$SigningCertificateThumbprint"
    foreach ($file in $Files) {
        $arguments = @{ FilePath = $file; Certificate = $certificate; HashAlgorithm = 'SHA256' }
        if ($TimestampServer) { $arguments.TimestampServer = $TimestampServer }
        $signature = Set-AuthenticodeSignature @arguments
        if ($signature.Status -ne 'Valid') { throw "Signering feilet for ${file}: $($signature.StatusMessage)" }
    }
}

Push-Location $root
try {
    & uv sync --frozen --extra dev
    if ($LASTEXITCODE -ne 0) { throw 'Kunne ikke opprette byggmiljoet.' }
    foreach ($name in @('ffmpeg.exe', 'ffprobe.exe')) {
        if (-not (Test-Path -LiteralPath "vendor\ffmpeg\bin\$name")) { throw 'Kjor scripts/fetch_ffmpeg.ps1 forst.' }
    }
    $origin = Get-Content -LiteralPath 'vendor\ffmpeg\origin.json' -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($origin.provider -ne 'vmc' -or -not $origin.source) {
        throw 'Bygget krever prosjektets eget FFmpeg-bygg med kildearkiv (scripts/fetch_ffmpeg.ps1 -Package ... -Source ...).'
    }
    & uv run --frozen python scripts/ffmpeg/verify.py vendor/ffmpeg/bin/ffmpeg.exe
    if ($LASTEXITCODE -ne 0) { throw 'FFmpeg-bygget dekker ikke appens behov.' }
    if (-not $SkipTests) {
        $oldRequire = $env:VMC_REQUIRE_FFMPEG
        try {
            $env:VMC_REQUIRE_FFMPEG = '1'
            & uv run --frozen python -m pytest -q
            if ($LASTEXITCODE -ne 0) { throw 'Testene feilet.' }
        } finally { $env:VMC_REQUIRE_FFMPEG = $oldRequire }
    }
    & uv run --frozen python scripts/distribution.py --prepare
    if ($LASTEXITCODE -ne 0) { throw 'Kunne ikke samle lisenser.' }
    & uv run --frozen python -m PyInstaller --noconfirm VestfoldMediaConverter.spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller feilet.' }
    Copy-Item -LiteralPath README.md, IT-GODKJENNING.md, LICENSE -Destination $dist
    Copy-Item -LiteralPath docs -Destination $dist -Recurse -Force

    if ($SigningCertificateThumbprint) {
        $unsigned = Get-ChildItem -LiteralPath $dist -Recurse -File -Include *.exe, *.dll, *.pyd |
            Where-Object { (Get-AuthenticodeSignature -LiteralPath $_.FullName).Status -ne 'Valid' } |
            ForEach-Object { $_.FullName }
        Set-ProjectSignature $unsigned
        Write-Host "Signerte $(@($unsigned).Count) programfiler."
        if (-not $TimestampServer) {
            Write-Warning 'Uten -TimestampServer blir signaturen ugyldig når sertifikatet utløper.'
        }
    } else {
        Write-Warning 'Bygget er usignert. Signer med organisasjonens sertifikat før utrulling.'
    }

    # Kildearkiv, SBOM og kontrollsummer lages etter signering, så de beskriver de endelige filene.
    & uv run --frozen python scripts/distribution.py --audit $dist
    if ($LASTEXITCODE -ne 0) { throw 'Inventar/kontrollsummer feilet.' }
    Write-Host "Portabel programmappe: $dist"

    if ($Msi) {
        & "$PSScriptRoot\build_msi.ps1" -SigningCertificateThumbprint $SigningCertificateThumbprint -TimestampServer $TimestampServer
    }
    Write-Host 'Se IT-GODKJENNING.md, BUILD-INFO.json og SBOM.cdx.json for IT-vurderingen.'
} finally { Pop-Location }
