param([string]$Archive = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
$version = '9.0.2'
$url = "https://www.gyan.dev/ffmpeg/builds/packages/ffmpeg-$version-essentials_build.zip"
$expected = '60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba'
$vendor = Join-Path $root 'vendor\ffmpeg'
New-Item -ItemType Directory -Force -Path "$vendor\downloads","$vendor\bin","$vendor\licenses" | Out-Null
if (-not $Archive) {
    $Archive = "$vendor\downloads\ffmpeg-release-essentials.zip"
    for ($attempt = 0; $attempt -lt 6; $attempt++) {
        if ((Test-Path -LiteralPath $Archive) -and
            ((Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant() -eq $expected)) { break }
        & curl.exe -L --fail -sS -C - -o $Archive $url
        if ($LASTEXITCODE -ne 0) { Write-Warning 'Nedlastingen ble avbrutt. Fortsetter fra siste byte.' }
    }
}
$Archive = (Resolve-Path -LiteralPath $Archive).Path
if ((Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
    throw 'FFmpeg-arkivet har feil SHA-256. Ingen programfiler ble tatt i bruk.'
}
Expand-Archive -LiteralPath $Archive -DestinationPath "$vendor\upstream" -Force
$package = Join-Path $vendor "upstream\ffmpeg-$version-essentials_build"
foreach ($tool in @('ffmpeg.exe', 'ffprobe.exe')) {
    Copy-Item -LiteralPath "$package\bin\$tool" -Destination "$vendor\bin\$tool" -Force
}
Copy-Item -LiteralPath "$package\LICENSE" -Destination "$vendor\licenses\FFmpeg-GPL-3.0.txt" -Force
Copy-Item -LiteralPath "$package\README.txt" -Destination "$vendor\licenses\GYAN-README.txt" -Force
$utf8 = New-Object System.Text.UTF8Encoding($false)
[IO.File]::WriteAllText("$vendor\origin.json", (@{
    version = $version; url = $url; archive_sha256 = $expected;
    provider = 'Gyan Doshi / gyan.dev'; source_commit = '946fcce07b'; license = 'GPL-3.0-or-later'
} | ConvertTo-Json), $utf8)
Write-Host "FFmpeg $version og FFprobe er verifisert og lagt i vendor/ffmpeg/bin."

