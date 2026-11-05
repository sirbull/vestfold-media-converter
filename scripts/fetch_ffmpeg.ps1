# Installer prosjektets eget FFmpeg-bygg (scripts/ffmpeg/build.sh) i vendor/ffmpeg.
#
# Pakken og kildearkivet lages av arbeidsflyten "Bygg og test" i GitHub Actions
# (artefakten "ffmpeg"). Last den ned og pakk ut zip-filen fra Actions, og kjør:
#   .\scripts\fetch_ffmpeg.ps1 -Package ffmpeg-vmc-9.0.2-win64.zip -Source ffmpeg-vmc-9.0.2-source.tar
# Appen henter aldri FFmpeg selv, og søker aldri etter FFmpeg i PATH.
param(
    [Parameter(Mandatory = $true)][string]$Package,
    [string]$Source = '',
    [string]$ExpectedSha256 = ''
)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$vendor = Join-Path $root 'vendor\ffmpeg'
$Package = (Resolve-Path -LiteralPath $Package).Path
$packageHash = (Get-FileHash -LiteralPath $Package -Algorithm SHA256).Hash.ToLowerInvariant()
if ($ExpectedSha256 -and $packageHash -ne $ExpectedSha256.ToLowerInvariant()) {
    throw 'FFmpeg-pakken har feil SHA-256. Ingen programfiler ble tatt i bruk.'
}

$staging = Join-Path $vendor 'upstream'
if (Test-Path -LiteralPath $staging) { Remove-Item -LiteralPath $staging -Recurse -Force }
Expand-Archive -LiteralPath $Package -DestinationPath $staging
$folder = @(Get-ChildItem -LiteralPath $staging -Directory)
if ($folder.Count -ne 1) { throw 'FFmpeg-pakken har uventet innhold.' }
$folder = $folder[0].FullName

# Kontroller hver fil mot pakkens egen kontrollsumliste før noe tas i bruk.
foreach ($line in Get-Content -LiteralPath (Join-Path $folder 'SHA256SUMS.txt')) {
    $expected, $name = $line -split '  ', 2
    $file = Join-Path $folder $name
    if (-not (Test-Path -LiteralPath $file) -or
        (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
        throw "Kontrollsummen stemmer ikke for $name. Ingen programfiler ble tatt i bruk."
    }
}
$info = Get-Content -LiteralPath (Join-Path $folder 'BUILD-INFO.json') -Raw -Encoding UTF8 | ConvertFrom-Json
if ($info.provider -ne 'vmc') { throw 'Pakken er ikke laget av prosjektets FFmpeg-oppskrift.' }

foreach ($name in @('bin', 'licenses', 'source')) {
    $path = Join-Path $vendor $name
    if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Recurse -Force }
    New-Item -ItemType Directory -Path $path | Out-Null
}
foreach ($tool in @('ffmpeg.exe', 'ffprobe.exe')) {
    Copy-Item -LiteralPath (Join-Path $folder "bin\$tool") -Destination (Join-Path $vendor "bin\$tool")
}
Copy-Item -LiteralPath (Join-Path $folder 'LICENSE.txt') -Destination (Join-Path $vendor 'licenses\FFmpeg-GPL-3.0.txt')
Copy-Item -Path (Join-Path $folder 'licenses\*') -Destination (Join-Path $vendor 'licenses') -Recurse
Copy-Item -LiteralPath (Join-Path $folder 'BUILD-INFO.json') -Destination (Join-Path $vendor 'BUILD-INFO.json') -Force

$sourceName = ''
$sourceHash = ''
if ($Source) {
    $Source = (Resolve-Path -LiteralPath $Source).Path
    $sourceName = Split-Path $Source -Leaf
    if ($sourceName -ne "ffmpeg-vmc-$($info.ffmpeg_version)-source.tar") {
        throw "Kildearkivet $sourceName hører ikke til FFmpeg $($info.ffmpeg_version)."
    }
    Copy-Item -LiteralPath $Source -Destination (Join-Path $vendor "source\$sourceName")
    $sourceHash = (Get-FileHash -LiteralPath $Source -Algorithm SHA256).Hash.ToLowerInvariant()
}
$utf8 = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText((Join-Path $vendor 'origin.json'), ([ordered]@{
    provider = 'vmc'; version = $info.ffmpeg_version; package = (Split-Path $Package -Leaf)
    package_sha256 = $packageHash; source = $sourceName; source_sha256 = $sourceHash; license = 'GPL-3.0-or-later'
} | ConvertTo-Json), $utf8)
Remove-Item -LiteralPath $staging -Recurse -Force
Write-Host "FFmpeg $($info.ffmpeg_version) (prosjektets eget bygg) er kontrollert og lagt i vendor/ffmpeg."
if (-not $Source) { Write-Warning 'Kildearkivet ble ikke oppgitt. Et distribuerbart bygg krever -Source.' }
