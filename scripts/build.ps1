param([switch]$SkipTests, [string]$SigningCertificateThumbprint = '')
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent
Push-Location $root
try {
    & uv sync --frozen --extra dev
    if ($LASTEXITCODE -ne 0) { throw 'Kunne ikke opprette byggmiljoet.' }
    foreach ($name in @('ffmpeg.exe', 'ffprobe.exe')) {
        if (-not (Test-Path -LiteralPath "vendor\ffmpeg\bin\$name")) { throw 'Kjor scripts/fetch_ffmpeg.ps1 forst.' }
    }
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
    if ($SigningCertificateThumbprint) {
        $certificate = Get-Item -LiteralPath "Cert:\CurrentUser\My\$SigningCertificateThumbprint"
        $signature = Set-AuthenticodeSignature -FilePath 'dist\VestfoldMediaConverter\VestfoldMediaConverter.exe' -Certificate $certificate -HashAlgorithm SHA256
        if ($signature.Status -ne 'Valid') { throw "Signering feilet: $($signature.StatusMessage)" }
    }
    Copy-Item -LiteralPath README.md,IT-GODKJENNING.md,LICENSE -Destination dist\VestfoldMediaConverter
    Copy-Item -LiteralPath docs -Destination dist\VestfoldMediaConverter -Recurse -Force
    & uv run --frozen python scripts/distribution.py --audit dist/VestfoldMediaConverter
    if ($LASTEXITCODE -ne 0) { throw 'Inventar/kontrollsummer feilet.' }
    Write-Host "Portabelt testbygg: $root\dist\VestfoldMediaConverter"
    Write-Host 'Se IT-GODKJENNING.md og BUILD-INFO.json for distribusjonsforutsetninger.'
} finally { Pop-Location }

