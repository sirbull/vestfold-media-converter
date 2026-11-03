# Vestfold media converter

Portabel Windows-app for lyd og video. Grensesnittet er på norsk, med engelske fagord der det er naturlig. Bygget med Python 3.12, PySide6/Qt Widgets og medfølgende FFmpeg/FFprobe.

Grensesnittet bruker Nunito, papirfargede flater og rødt/gult fra Vestfold-våpenskjoldet. Konvertering har en tydelig rød hovedknapp. Fonten følger med programmet og fungerer offline uten installasjon på Windows.

Øverst velges tema med tre ikoner: skjerm for systemtema, sol for lyst og måne for mørkt. Valgt ikon er markert. Pek på et ikon for forklaring; piltastene kan også brukes til å bytte tema.

Små geometriske detaljer og lyse naturtoner er inspirert av fylkeskommunens designmanual. Se [visuell retning](docs/DESIGN.md) for kilder og tilpasninger.

## Bruk

1. Åpne `VestfoldMediaConverter.exe` fra den komplette programmappen.
2. Dra inn en fil, flere filer eller en mappe. Du kan også bruke importknappene.
3. Trykk **Konverter**.

Video får automatisk **MP4 – Anbefalt** (H.264, CRF 21, medium, AAC-LC 192 kbit/s, yuv420p, faststart). Lyd får **MP3 – Anbefalt** ved 192 kbit/s. En MTS-fil med AC-3 blir dermed MP4 med H.264/AAC. En WAV-fil blir MP3. Albumgrafikk gjør ikke en lydfil til video.

Resultatene lagres i Windows sin Dokumenter-mappe under `Mediekonverter`. **Velg målmappe** endrer dette. Originalene beholdes alltid. Ved navnekonflikt brukes `navn (1).mp4`, `navn (2).mp4` osv. FFmpeg skriver til en midlertidig fil i målmappen; bare verifiserte resultater får endelig navn. **Avbryt** stopper den aktuelle jobben og beholder allerede fullførte resultater.

Køen viser type, originalformat, varighet, størrelse, profil og status. Velg en rad for å se filen i forhåndsvisningen ved siden av. Ctrl/Shift eller Ctrl+A velger flere rader. Profilvalg gjelder valgte rader; **Konverter** behandler alle ufullførte, gyldige rader. Dobbeltklikk eller **Detaljer** viser feil og filstier. Ctrl+O importerer; Delete fjerner valgte rader fra køen.

Medietype, originalformat og varighet vises under filnavnet. Statusmerker og fremdrift vises til høyre; filhandlingene ligger under køen. Målmappe og konverteringsknappen er samlet nederst.

Sidepanelet har fanene **Forhåndsvisning** og **Eksportvalg**. Eksportvalg-knappen under køen åpner innstillingene. På små skjermer forenkles kolonnene slik at filliste og forhåndsvisning fortsatt kan stå ved siden av hverandre.

## Forhåndsvisning

Velg en videofil i køen for å se et bilde fra kilden. **Spill av** og **Pause** styrer enkel avspilling uten lyd. Tidslinjen lar deg velge et annet tidspunkt. Dette virker også når en hel mappe eller mange filer er importert; valgt rad bestemmer hvilken fil som vises.

Forhåndsvisningen dekodes i bakgrunnen med medfølgende FFmpeg, uten Windows-kodeker, nettverk eller ekstra avhengigheter. Den bruker opptil 640 × 360 og 12 bilder/s for å begrense ressursbruken. Original oppløsning og bildefrekvens ved eksport påvirkes ikke. Ingen forhåndsvisningsfiler lagres på disk. Ved filbytte avbrytes den tidligere dekodingen; ved lukking stoppes prosessen. Lydfiler viser filinformasjon. HDR-forhåndsvisning er foreløpig ikke støttet.

## Avansert bruk

**Avanserte innstillinger** er lukket ved oppstart. Endringer her tas i bruk med **Bruk innstillinger på valgte filer**. Ferdige profiler brukes straks de velges. Ved blandet utvalg kan «Anbefalt» sette en egen passende standard per fil. Andre felles innstillinger brukes bare når hele utvalget er kompatibelt.

- Video: MP4, MOV, MKV, WebM, AVI; H.264, HEVC, AV1, VP9, ProRes, MPEG-4 Part 2 og kompatibel stream copy.
- Lyd: MP3, WAV, FLAC, M4A/AAC, Opus, OGG/Vorbis, AIFF og ALAC. Video med lyd kan også eksporteres til disse.
- Juster kvalitet/bitrate, preset, oppløsning, bildefrekvens, sideforhold, deinterlacing, pikselformat, lydspor, samplingsfrekvens, mono/stereo og støttet bitdybde.
- Bare tilgjengelige encodere og godkjente containerkombinasjoner vises. ProRes-profilen velger MOV og 10-bit 4:2:2. PCM-bitdybde velges gjennom lydkodeken.
- NVIDIA/Intel/AMD-encodere vises hvis FFmpeg inneholder dem. De krever fungerende GPU og driver. Ved feil forklares dette; velg CPU-profil og prøv igjen. Ingen automatisk kvalitetsendring/fallback.

Original bildefrekvens og oppløsning beholdes som standard. FFmpeg håndterer rotasjon. Kjent interlaced video deinterlaces automatisk med `bwdif` ved samme bildefrekvens. SDR-fargetagger føres videre. Odde dimensjoner får maksimalt én ekstra piksel i hver retning for kompatibel 4:2:0. HDR krever eksplisitt 10-bit HEVC/AV1/VP9 eller stream copy; automatisk HDR til SDR inngår ikke. Flere lydspor reduseres til valgt standardspor, og flerkanalslyd nedmikses til stereo. Ingen kunstig lyd genereres. Undertekster, vedlegg og ekstra videostrømmer eksporteres ikke i MVP-en.

## Kjør fra kildekode

På Windows x64, med [uv](https://docs.astral.sh/uv/) og nettverk under klargjøring:

```powershell
uv sync --frozen --extra dev
.\scripts\fetch_ffmpeg.ps1
uv run python -m vestfold_converter
```

`uv` henter Python 3.12 ved behov. Prosjektet trenger bare PySide6 Essentials, som inneholder Qt Widgets; WebEngine og Qt Multimedia brukes ikke. FFmpeg lastes ned **kun av utviklingsskriptet**, aldri av appen. Hentingen er låst til en bestemt versjon og SHA-256. Et allerede nedlastet arkiv kan brukes med `-Archive C:\sti\ffmpeg.zip`. Appen søker aldri etter FFmpeg i PATH.

Hvis `uv` sin Python-starter feiler på utviklingsmaskinen, kan standard `python -m venv .venv --upgrade` brukes med den installerte Python 3.12-tolken. Organisasjonens sikkerhetspolicy skal følges; en blokkert applikasjon skal godkjennes av IT.

Når miljøet er klargjort, kan grensesnittet testes direkte fra prosjektmappen uten den pakkede EXE-filen eller nye nedlastinger:

```powershell
uv run --frozen --offline python -m vestfold_converter
```

Dette åpner det vanlige programvinduet fra Python. Lukk vinduet for å avslutte. FFmpeg og FFprobe i prosjektets `vendor`-mappe brukes fortsatt til analyse og konvertering.

## Tester og bygg

```powershell
uv run python -m pytest -q
uv run ruff check src tests scripts
.\scripts\build.ps1
```

Integrasjonstestene genererer små mediefiler lokalt med den medfølgende FFmpeg-bygningen. Uten FFmpeg blir de hoppet over ved vanlig utvikling. Byggskript og CI setter `VMC_REQUIRE_FFMPEG=1`, slik at manglende verktøy gir feil. Se [testomfang](docs/TESTING.md) og [testresultat](docs/TESTRESULTAT.md).

PyInstaller lager `dist/VestfoldMediaConverter/` med EXE, `_internal`-mappe, dokumentasjon, lisenser, applikasjonens kildearkiv, `BUILD-INFO.json` og `SHA256SUMS.txt`. **Hele mappen** må kopieres. Ingen Python-installasjon trengs hos brukeren. `-SkipTests` er kun for lokal iterasjon etter en bestått testkjøring. `-SigningCertificateThumbprint` signerer appen med et eksisterende sertifikat i brukerens sertifikatlager før kontrollsummer beregnes.

Programmet bruker ingen nettverkstjenester, telemetri, registerlagring, systemtjenester eller administratorrettigheter. Tema og sist valgte målmappe lagres i `%LOCALAPPDATA%/VestfoldMediaConverter/settings.json`. Kildestier og køhistorikk lagres ikke mellom kjøringer.

## Prosjektstruktur

```text
src/vestfold_converter/
  models.py        Medieinformasjon, kø og eksportinnstillinger
  probe.py         FFprobe-analyse og klassifisering
  profiles.py      Profiler og eksplisitt kompatibilitetsmodell
  engine.py        Kommandoer, konvertering, fremdrift og resultatkontroll
  process.py       Avbrytbare bakgrunnsprosesser uten shell
  storage.py       Målmapper, JSON-innstillinger og trygg publisering
  workers.py       Analyse og sekvensiell batch i Qt-tråd
  ui.py            Qt Widgets-grensesnitt
  app.py           Oppstart
scripts/           Verifisert FFmpeg-henting, bygg og distribusjonsinventar
tests/             Enhetstester, ekte FFmpeg-tester og Qt-flyter
vendor/ffmpeg/     Fast versjon av FFmpeg/FFprobe og opprinnelsesdata
```

## Lisens og distribusjonsstatus

Applikasjonens kildekode er **GPL-3.0-or-later**, se [LICENSE](LICENSE). Den valgte Gyan-bygningen av FFmpeg er **GPLv3**, med `--enable-gpl`, `--enable-version3`, libx264 og libx265. Den er ikke en LGPL-bygning. Qt/PySide6 har egne LGPL/GPL-lisenser og tredjepartsvilkår.

Vestfold-våpenskjoldet er et separat, brukerlevert profilasset. Original SVG er bevart uendret i `src/vestfold_converter/assets/vestfold-vapen.svg`, inkludert originalfargene. QtSvg rendrer logoen med riktig skalering; assets følger med ved pakking. Appens GPL-merking gjelder egen kildekode.

Den portable mappen er et teknisk testbygg. Før den deles videre må ansvarlig distributør sikre tilsvarende kildekode, bygghjelpemidler og notices for den **faktiske** FFmpeg-bygningen og dens biblioteker, samt oppfylle Qt-lisensvilkårene. Applikasjonens kildekode følger med; hele kildegrunnlaget til Gyan-bygningens statiske tredjepartsbiblioteker følger ikke automatisk med. Dette er beskrevet i [IT-GODKJENNING.md](IT-GODKJENNING.md) og [lisensnotatet](docs/LICENSES.md).

