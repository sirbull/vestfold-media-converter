# IT-godkjenning – Vestfold Media Converter 1.0.0

Status: **Klar for IT-vurdering.** Tilsvarende kildekode for hele programmet, inkludert FFmpeg og alle bibliotekene i den, følger med. Dette dokumentet er et beslutningsgrunnlag, ikke en påstand om at IT allerede har godkjent programmet.

Gjenstår før utrulling:

1. Signering med organisasjonens kodesigneringssertifikat, med tidsstempel.
2. Juridisk vurdering av patentpooler for H.264/HEVC/AAC-koding (se [lisensnotatet](docs/LICENSES.md#patenter)).
3. Prøving i målmiljøet (se [Validering](#validering-og-begrensninger)).

## Formål og brukerflyt

Lokal konvertering av lyd og video for videregående skole. Elever importerer medier og trykker Konverter. Standard videoeksport er MP4/H.264/AAC, og standard lydeksport er MP3. Ingen konto eller internett kreves. Originaler åpnes bare for lesing.

Valgt fil kan forhåndsvises med den medfølgende FFmpeg. Bilder og lyd overføres gjennom en lokal prosesspipe og holdes begrenset i minnet, og ingen nye mediefiler opprettes for forhåndsvisning. Lyd spilles gjennom Windows sin innebygde lydutgang (winmm). Installerte Windows-kodeker brukes ikke.

## Leveranse

| Form | Bruk |
| --- | --- |
| `VestfoldMediaConverter-1.0.0.msi` | Installasjon for hele maskinen til `C:\Program Files\Vestfold Media Converter`, med snarvei på Start-menyen. Anbefalt for Intune/SCCM. |
| Programmappen `VestfoldMediaConverter/` | Samme filer uten installasjon. Må ligge på et sted AppLocker/WDAC tillater. |

```powershell
msiexec /i VestfoldMediaConverter-1.0.0.msi /qn /l*v install.log    # stille installasjon
msiexec /x VestfoldMediaConverter-1.0.0.msi /qn                     # avinstallasjon
```

MSI-pakken har ingen egne installasjonshandlinger, tjenester, drivere, planlagte oppgaver eller oppstartsoppføringer. En ny versjon erstatter den gamle automatisk (fast UpgradeCode `844f7685-e5b2-49fa-b061-60ab2c4100f2`). Ingen installasjon, oppdatering eller nedlasting skjer fra selve appen.

## Teknologi og inventar

Python 3.12, PySide6 Essentials (Qt Widgets), Shiboken6 og pywin32, pakket med PyInstaller til en **onedir**-mappe, samt FFmpeg og FFprobe. Alle komponenter, versjoner, lisenser og kontrollsummer står i `SBOM.cdx.json` (CycloneDX 1.5) og `BUILD-INFO.json` i hvert bygg. Låste Python-avhengigheter ligger i `uv.lock`.

| EXE-fil | Funksjon |
| --- | --- |
| `VestfoldMediaConverter.exe` | Qt-applikasjonen med Python-kjøremiljøet |
| `_internal/vendor/ffmpeg/bin/ffmpeg.exe` | Lokal dekoding, konvertering og forhåndsvisning |
| `_internal/vendor/ffmpeg/bin/ffprobe.exe` | Analyse av kilde og resultat |

`ffplay.exe` følger ikke med. DLL-, PYD- og Qt-plugin-filer lastes bare fra `_internal` i programmappen og står i kontrollsumlisten.

**FFmpeg er prosjektets eget bygg**, laget i GitHub Actions fra kildekode låst med SHA-256 eller git-commit (`scripts/ffmpeg/`). Det har bare bibliotekene appen bruker, og **ingen nettverksstøtte** (`--disable-network`). Det kan altså ikke åpne nettadresser, selv om noen skulle prøve. Byggskriptet kontrollerer på hvert bygg at FFmpeg mangler alle nettverksprotokoller, ikke er bygget med `--enable-nonfree`, og dekker alt appen bruker.

## Prosesser og Windows-integrasjon

| Hva | Hvordan |
| --- | --- |
| Underprosesser | Bare `ffmpeg.exe` og `ffprobe.exe` fra programmappen. Absolutt sti, argumentliste, aldri `shell=True`, aldri PATH-oppslag, `CREATE_NO_WINDOW`. Kun protokollene `file` og `pipe` er tillatt i kommandoene. |
| PowerShell, cmd, skript | Brukes ikke. |
| Hurtigtilgang | Leses direkte fra Windows Shell (COM `Shell.Application`) i appens egen prosess. Ingenting endres. |
| Filsøk | Leses fra Windows Search-indeksen gjennom OLE DB (COM `ADODB` med `Search.CollatorDSO`), i appens egen prosess. Søkeord escapes som SQL-litteraler og brukes aldri som kommandoer. |
| Dokumenter-mappen | Windows Known Folder API (`SHGetKnownFolderPath`), som følger omdirigering til OneDrive eller nettverk. |
| Lyd | Windows sin innebygde lydutgang (winmm). |

## Tilganger og lagring

| Område | Tilgang |
| --- | --- |
| Brukervalgte kildefiler og mapper | Lesing og mappeopplisting, inkludert undermapper |
| Dokumenter/Mediekonverter eller valgt målmappe | Opprette mappe, midlertidige filer og ferdige resultatfiler |
| `%LOCALAPPDATA%\VestfoldMediaConverter\settings.json` | Lese/skrive tema, målmappe og visningsvalg i filbrowseren |
| Brukerens TEMP-mappe | Kortvarig FFmpeg-feilutskrift under konvertering, slettes etterpå |
| Programmappen | Bare lesing. Appen skriver aldri til sin egen mappe. |
| Registeret | Appen skriver ikke til registeret. MSI-pakken lager Windows Installer sine vanlige avinstallasjonsoppføringer og nøkkelen `HKLM\Software\Vestfold Media Converter` for Start-menysnarveien. |

Originalfilene endres eller slettes ikke, og eksisterende resultater overskrives ikke. Ved avbrudd slettes den påbegynte `.vmc-*.part.*`-filen. Strømbrudd, tvangsavslutning eller frakoblet disk kan etterlate denne, og den kan da slettes manuelt. Kø og kildefilstier holdes bare i minnet. Feilmeldinger kan inneholde lokale filstier. Ingen medielogger eller analysehistorikk lagres.

## Nettverk og rettigheter

**Ingen nettverkstilgang behøves eller brukes.** Ingen telemetri, oppdateringssjekk, nedlasting av kode, datainnsamling, innlogging eller skybehandling. Selve appen har ingen nettverksklient. Organisasjonens synkronisering eller filserver kan likevel håndtere filer brukeren lagrer i en omdirigert mappe.

Vanlig bruker er nok. Manifestet bruker `asInvoker`, DPI-tilpasning og lange stier. Valgfri GPU-koding bruker allerede installert driver: NVENC krever en NVIDIA-driver som støtter Video Codec SDK 13.0, og Quick Sync og AMF bruker driverne fra Intel og AMD.

## Sikkerhetsregler (AppLocker, WDAC, Defender)

- **Utgiverregel:** Når bygget er signert, har alle EXE-, DLL- og PYD-filer uten leverandørsignatur organisasjonens signatur, også FFmpeg, FFprobe og Python-modulene. Filer fra Qt og Python beholder leverandørens signatur. Én utgiverregel for organisasjonens sertifikat og leverandørene dekker dermed hele programmet. Hash-regler kan lages fra `SHA256SUMS.txt`.
- **Sti:** MSI-en installerer til Program Files, som standardreglene i AppLocker tillater. Ingen programfiler kjøres fra TEMP eller brukermapper.
- **Defender og ASR:** Programmet starter ingen skript, PowerShell, cmd eller Office-prosesser, og laster ikke kode fra nettet. Regelen *Block executable files from running unless they meet a prevalence, age, or trusted list criterion* vil stoppe et nytt, usignert bygg. Signering og IT sin godkjenning av sertifikatet håndterer dette.
- Programmet gjør ingen forsøk på å endre eller omgå sikkerhetsinnstillinger.

## Lisenser

Programmet er gratis og leveres under GPL-3.0-or-later. Lisenstekstene ligger i `_internal/licenses`, og tilsvarende kildekode i `source/`:

- `APPLICATION-SOURCE.zip`: appens egen kildekode, tester og byggoppskrift
- `ffmpeg-vmc-9.0.2-source.tar`: uendrede kildearkiv for FFmpeg og hvert bibliotek som er lenket inn, med byggskript og verktøykjedens versjoner

Med x264 og x265 er FFmpeg-bygget **GPLv3, ikke LGPL**. Qt/PySide6 er LGPLv3, og Qt-bibliotekene ligger som utskiftbare DLL-filer. Python og pywin32 har PSF-lisens, PyInstaller GPL med bootloader-unntak, og Nunito SIL OFL 1.1. Se [docs/LICENSES.md](docs/LICENSES.md) for hver komponent og distribusjonsrutinen.

## Kontrollsummer og SBOM

`SHA256SUMS.txt` i programmappen har SHA-256 for alle øvrige filer: EXE, FFmpeg, FFprobe, DLL/PYD, dokumentasjon, kildearkiv og SBOM. MSI-pakken har sin egen `.msi.sha256`. Kontrollsummer og SBOM beregnes **etter signering**. FFmpeg-pakken kontrolleres mot sin egen kontrollsumliste før den tas inn i bygget, og kildearkivet mot kontrollsummen fra installasjonen.

En lokal kontrollsum alene beviser ikke opphav. Signatur og en kontrollsum fra en betrodd kanal (for eksempel byggartefaktene i GitHub Actions) brukes for integritetskontroll.

## Signering

Byggskriptet signerer med et eksisterende sertifikat i brukerens sertifikatlager (`-SigningCertificateThumbprint`) og organisasjonens tidsstempeltjeneste (`-TimestampServer`). Uten tidsstempel blir signaturen ugyldig når sertifikatet utløper, og da vil sikkerhetsregler blokkere programmet. I GitHub Actions kan sertifikatet legges i repoets hemmeligheter. Det installeres aldri noe selvsignert sertifikat. Signatur, utgiver og kjede kontrolleres før utrulling.

## Validering og begrensninger

Den automatiske testpakken kjøres før hvert bygg. Den dekker analyse, profiler og kompatibilitet, ekte konverteringer med den medfølgende FFmpeg, avbrudd og opprydding, forhåndsvisning, filbrowser, Hurtigtilgang og søk uten underprosesser, og Qt-flytene, med lokalt genererte mediefiler.

Skal prøves i målmiljøet med standardbruker før utrulling:

- Installasjon og avinstallasjon av MSI-en, og oppstart fra Start-menyen
- Hurtigtilgang og filsøk i filbrowseren i den pakkede appen
- Import i Adobe Premiere Pro, flere timers skoleopptak, defekte minnekort og fysisk full disk
- GPU-koding på skolens maskiner og drivere
- Omdirigert Dokumenter-mappe og offline bruk

På utviklingsmaskinen ble oppstart av et tidligere usignert EXE-bygg én gang avvist med «Ingen tilgang». Årsaken er ikke fastslått. Et senere bygg startet normalt fra samme maskin. Ingen sikkerhetsinnstilling ble endret eller omgått.
