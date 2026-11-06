# Lisensgrunnlag

Vestfold Media Converter er gratis programvare under **GPL-3.0-or-later**, med full tekst i `LICENSE`. Alle komponenter som følger med, er åpen kildekode. Tilsvarende kildekode for hele programmet følger med i mappen `source/` i det ferdige bygget:

| Fil i `source/` | Innhold |
| --- | --- |
| `APPLICATION-SOURCE.zip` | Appens kildekode, tester, byggskript, MSI-definisjon og låste avhengigheter (`uv.lock`) |
| `ffmpeg-vmc-<versjon>-source.tar` | Uendrede kildearkiv for FFmpeg og alle bibliotekene som er lenket inn i den, byggoppskriften og verktøykjedens versjoner |

Byggskriptet stopper hvis FFmpeg-kildekoden mangler eller ikke stemmer med kontrollsummen fra installasjonen. Den samme kildekoden kan derfor ikke bli skilt fra programfilene ved et uhell.

## FFmpeg

FFmpeg og FFprobe er prosjektets eget bygg. De lages av `scripts/ffmpeg/build.sh` på Ubuntu 24.04 i GitHub Actions, med krysskompilering for 64-bit Windows. Hver kilde er låst i `scripts/ffmpeg/sources.json` med SHA-256 eller git-commit. Bygget er statisk og har ingen nettverksstøtte (`--disable-network`).

Med `--enable-gpl --enable-version3` og x264/x265 er det ferdige FFmpeg-bygget **GPLv3**, ikke LGPL. `--enable-nonfree` er aldri med, og kontrollen i `scripts/ffmpeg/verify.py` avviser et bygg som har det.

| Komponent | Bruk i appen | Lisens |
| --- | --- | --- |
| FFmpeg | Analyse, dekoding, konvertering og forhåndsvisning | GPL-3.0-or-later (med valgene over) |
| x264 | H.264-koding | GPL-2.0-or-later |
| x265 (8, 10 og 12 bit) | HEVC-koding | GPL-2.0-or-later |
| libaom | AV1-koding og -dekoding | BSD-2-Clause (og AOMs patentlisens) |
| libvpx | VP9-koding (også 10 bit) | BSD-3-Clause (og WebM-patentlisensen) |
| LAME | MP3-koding | LGPL-2.0-or-later |
| Opus | Opus-koding | BSD-3-Clause |
| libogg, libvorbis | OGG/Vorbis-koding | BSD-3-Clause |
| nv-codec-headers | NVIDIA NVENC (bare headere; driveren følger med Windows/GPU) | MIT |
| AMF-headere | AMD AMF (bare headere) | MIT |
| libvpl | Intel Quick Sync (dispatcher) | MIT |
| zlib, bzip2, xz | Komprimering i blant annet PNG, TIFF og MKV | Zlib, bzip2-1.0.6, 0BSD |
| mingw-w64-runtime, libgcc, libstdc++ | Statisk kjøretidsstøtte fra verktøykjeden | ZPL/MIT/offentlig eiendom, GCC Runtime Library Exception |

Lisenstekstene ligger i lisenssamlingen under `_internal/licenses/ffmpeg/`, én mappe per komponent. Verktøykjeden (GCC, binutils, mingw-w64) regnes som allment tilgjengelige verktøy etter GPL, og versjonene står i `BUILD-INFO.json`.

Sammenlignet med det tidligere Gyan-bygget kan appen eksportere og forhåndsvise de samme formatene som før. Fem sjeldne innleseformater er bevisst utelatt: AviSynth-skript (laster eksterne DLL-er), DASH-strømmelister, IMF-mastringspakker, spillmusikk og trackermusikk. Øvrige biblioteker som er utelatt (blant annet nettverk, undertekstgjengivelse og ekstra filtre), brukes ikke av appen. Dekoderne fra eksterne bibliotek som er utelatt, har en innebygd FFmpeg-dekoder for samme format. `scripts/ffmpeg/requirements.json` lister hver utelatelse med begrunnelse, og `verify.py` sjekker bygget mot det forrige på hvert bygg.

## Qt, Python og byggverktøy

PySide6 Essentials/Shiboken leveres fra Qt for Python under LGPLv3/GPLv2/GPLv3. Se [Qt for Python-lisenser](https://doc.qt.io/qtforpython-6/licenses.html). Qt-bibliotekene er dynamiske filer i programmappen og kan byttes ut av brukeren, slik LGPL krever. Det brukes ingen kommersiell Qt-lisens, og ikke Qt WebEngine eller Qt Multimedia.

Python: PSF License, i `PYTHON-LICENSE.txt` fra valgt runtime. pywin32 (Windows-grensesnitt for Hurtigtilgang og søk): PSF License. PyInstaller: GPL med eget bootloader-unntak, som tillater distribusjon av programmer pakket med det. Byggskriptet kopierer pakkenes egne lisensfiler, og de nøyaktige versjonene står i `uv.lock`, `BUILD-INFO.json` og `SBOM.cdx.json`.

MSI-pakken bygges med WiX Toolset 5 (MS-RL). WiX 6 har andre lisensvilkår og brukes ikke.

## Nunito

Nunito fra [Google Fonts sitt kildearkiv](https://github.com/google/fonts/tree/main/ofl/nunito) følger med som en uendret variabel TTF-font, lisensiert under **SIL Open Font License 1.1**. Copyright- og lisenstekst ligger sammen med fonten i `src/vestfold_converter/assets/fonts/OFL.txt`, og `ORIGIN.json` dokumenterer kilde-URL og SHA-256. Fonten lastes fra programmappen til Qt sitt prosessminne. Den installeres ikke i Windows og hentes ikke fra nettet.

## Patenter

Opphavsrettslisensene over gir ikke automatisk rettigheter til patenter. Koding til H.264, HEVC og AAC kan være omfattet av patentpooler (blant annet Via LA og Access Advance). Hvordan dette slår ut for gratis, intern bruk i skole og offentlig sektor, er en juridisk vurdering for fylkeskommunen og ikke noe programmet kan avgjøre. MP3-patentene er utløpt. Opus, Vorbis, VP9 og AV1 er laget for å kunne brukes royaltyfritt.

## Distribusjonsrutine

1. Bygg i GitHub Actions eller med `scripts/build.ps1 -Msi` fra et rent utsjekk, med prosjektets FFmpeg-bygg og kildearkiv.
2. Signer med organisasjonens kodesigneringssertifikat og tidsstempel. Kontrollsummer og SBOM beregnes etter signering.
3. Distribuer hele programmappen eller MSI-pakken. Mappen `source/` og lisenssamlingen skal følge med uendret.
4. Arkiver artefaktene fra bygget (programmappe, MSI og FFmpeg-kildearkiv) for hver versjon som rulles ut. GPL krever at kildekoden kan utleveres så lenge programmet distribueres.
