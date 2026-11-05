# IT-godkjenning – Vestfold Media Converter 1.0.0

Status: **Klar for IT-vurdering. Lisensgrunnlaget for FFmpeg-bygningen må avklares før videredistribusjon.** Dette dokumentet er et beslutningsgrunnlag, ikke en påstand om at IT allerede har godkjent programmet.

## Formål og brukerflyt

Lokal konvertering av lyd og video for videregående skole. Elever importerer medier og trykker Konverter. Standard videoeksport er MP4/H.264/AAC; standard lydeksport er MP3. Ingen konto eller internett kreves. Originaler åpnes kun for lesing.

Valgt video kan forhåndsvises uten lyd med medfølgende FFmpeg. Bilder overføres gjennom en lokal prosesspipe og holdes begrenset i minnet; ingen nye mediefiler opprettes for forhåndsvisning. Filbytte og lukking avbryter dekodingen. Dette bruker ikke installerte Windows-kodeker eller nettverk.

## Teknologi og faktisk inventar

Python 3.12+, PySide6 Essentials (Qt Widgets), Shiboken6, FFmpeg og FFprobe. PyInstaller brukes ved bygging til en portabel **onedir**-mappe. Låste Python-avhengigheter ligger i `uv.lock`. Nøyaktige versjoner, FFmpeg-konfigurasjon og liste over eksekverbare filer genereres i `BUILD-INFO.json` for hvert bygg.

Nunito-fonten følger med programmet under SIL Open Font License 1.1. Qt registrerer fonten bare i programmets minne. Ingen font installeres i Windows, og dette krever verken registerendring, administratorrettigheter eller nettverk. Fontfil og original lisens følger med i assets-mappen; lisensen samles også i byggmappens lisenssamling.

Forventede EXE-filer:

| Fil | Funksjon |
| --- | --- |
| `VestfoldMediaConverter.exe` | Qt-applikasjon og inkludert Python-kjøremiljø |
| `_internal/vendor/ffmpeg/bin/ffmpeg.exe` | Lokal dekoding og konvertering |
| `_internal/vendor/ffmpeg/bin/ffprobe.exe` | Analyse av kilde og resultat |

Eventuelle øvrige EXE-filer samlet av Qt/PyInstaller fremgår av den genererte listen og skal inngå i IT-vurderingen. DLL-/PYD-filer og Qt-plattformplugin inngår også i kontrollsumlisten. `ffplay.exe` distribueres ikke. Ingen installer, systemtjeneste, planlagt oppgave eller driver opprettes.

## Tilganger og lagring

| Område | Tilgang |
| --- | --- |
| Brukervalgte kildefiler og mapper | Lesing og mappeopplisting, inkludert undermapper |
| Dokumenter/Mediekonverter eller valgt målmappe | Opprette mappe, midlertidige filer og ferdige resultatfiler |
| `%LOCALAPPDATA%/VestfoldMediaConverter/settings.json` | Skrive/lese målmappe og tema |
| Brukerens TEMP-mappe | Kortvarig FFmpeg-feilutskrift under konvertering; slettes ved normal avslutning |
| Programmappen | Lesing av EXE, runtime, FFmpeg og dokumentasjon |

Originalfilene endres eller slettes ikke. Eksisterende resultater overskrives ikke. Ved avbrudd slettes den påbegynte `.vmc-*.part.*`-filen. Strømbrudd, tvangsavslutning eller frakoblet disk kan etterlate denne; den kan slettes manuelt. Kø og kildefilstier holdes kun i minnet. Feilmeldinger kan inneholde lokale filstier. Ingen permanente medielogger eller analysehistorikk opprettes.

Sist valgte målmappe brukes bare når den fortsatt finnes og er tilgjengelig. Ellers brukes Windows Known Folder API for Dokumenter og undermappen Mediekonverter. Brukerens eventuelle OneDrive-/nettverksomdirigering av Dokumenter følger Windows-oppsettet. Selve appen har ingen nettverksklient; organisasjonens synkronisering/filserver kan likevel håndtere filer brukeren lagrer der.

## Nettverk og rettigheter

**Ingen nettverkstilgang behøves ved bruk.** Ingen telemetri, oppdateringssjekk, kodeknedlasting, datainnsamling, innlogging eller skybehandling. Kun lokal FFmpeg-protokoll `file,pipe` tillates i kommandoene. Utviklingsskript bruker HTTPS til pakkekilder/Gyan under klargjøring. Disse skriptene kjøres ikke av sluttbrukerprogrammet.

Vanlig bruker er tilstrekkelig. Manifestet bruker `asInvoker`, DPI-awareness og long-path-awareness. Appen skriver ikke til registeret og installerer ingenting. Filtilganger og operativsystemets lengdegrenser gjelder fortsatt. FFmpeg startes med absolutte programstier, argumentlister og `CREATE_NO_WINDOW`, aldri `shell=True`. Appen bruker ikke installerte Windows-kodeker. Valgfri GPU-encoding bruker allerede installert driver.

## Lisenser

Applikasjonen leveres under GPL-3.0-or-later. Lisenssamlingen ligger under `_internal/licenses`. Se [docs/LICENSES.md](docs/LICENSES.md) for kilder og konkrete distribusjonsforutsetninger.

FFmpeg 9.0.2 Essentials fra Gyan er kompilert med `--enable-gpl --enable-version3 --enable-libx264 --enable-libx265`. Den faktiske `ffmpeg -L`-utskriften lagres i bygginventaret. **Denne bygningen er GPLv3, ikke LGPL.** Byggskriptet avviser `--enable-nonfree`. Lisensmessige krav gjelder også statisk innlenkede biblioteker. GPL betyr ikke at patentspørsmål automatisk er avklart.

Før deling må distributør sikre fullstendig tilsvarende kildekode og bygghjelpemidler for de medfølgende GPL-komponentene, samt alle notices/lisenser som følger med eksterne biblioteker. En generell lenke til FFmpeg eller x264 er ikke alene tilstrekkelig. Det genererte `APPLICATION-SOURCE.zip` dekker appens egen kildekode, ikke hele Gyan-bygningen. Et egnet alternativ er en egen dokumentert og reproduserbar FFmpeg-byggkjede med arkivert kildegrunnlag.

PySide6/Qt Essentials og Shiboken har LGPLv3/GPLv3-/kommersielle lisensalternativer og tredjepartskomponenter. Brukerens rettigheter til modifikasjon, erstatning av bibliotekene og nødvendig informasjon må ivaretas. onedir gjør de delte Qt-bibliotekene tilgjengelige. Ingen lisensserver eller kommersiell Qt-lisens antas. PyInstaller har GPL med bootloader-unntak; Python har PSF-lisens. Byggskriptet samler pakkefølgende lisensfiler, men automatisert innsamling erstatter ikke fullstendig lisenskontroll.

## SHA-256

`SHA256SUMS.txt` i den ferdige programmappen inneholder faktiske SHA-256-verdier for alle øvrige filer, inkludert app-EXE, FFmpeg, FFprobe, DLL/PYD, dokumentasjon og kildearkiv. `BUILD-INFO.json` beskriver bygget. Kontrollsummer beregnes **etter eventuell signering**. Etter endringer eller signering av andre filer må inventarskriptet kjøres på nytt.

Det innhentede FFmpeg-ziparkivet er låst til SHA-256:

```text
60f467265b1e312373dbcd92200c2618a74850f98d3d078e94296bb3fa2047ba
```

EXE-kontrollsummer må hentes fra det faktiske bygget, ikke gjenbrukes fra tidligere versjoner. Signert distribusjonsinventar eller en kontrollsum publisert i en betrodd kanal kan brukes for integritetskontroll; en lokal kontrollsum alene beviser ikke opphav.

## Signering og bedriftsdistribusjon

Bygget er usignert med mindre et eksisterende kodesigneringssertifikat oppgis til byggskriptet. Ingen selvsignert sertifikat installeres. For produksjon bør organisasjonen signere med godkjent Authenticode-sertifikat, bruke sin ordinære tidsstempling og følge godkjent sertifikathåndtering. Byggskriptets valgfrie lokale signering bruker ikke nettverkstidsstempel. Signatur, utgiver og kjede kontrolleres før utrulling.

Distribuer hele onedir-mappen via godkjent filområde/Intune/SCCM eller tilsvarende. Ingen lokal installasjon kreves av appen. AppLocker/WDAC/Defender-vurdering må dekke app, FFmpeg, FFprobe og runtime. Hash- og publisherregler håndteres av IT etter organisasjonens policy. Programmet gjør ingen forsøk på å endre eller omgå sikkerhetspolicyer. Test standardbruker, offlinekjøring, mappeomdirigering og målmaskinens maskinvare før utrulling.

## Validering og begrensninger

Den automatiske testpakken kjøres av byggskriptet før hvert bygg. Den dekker analyse, profiler og kompatibilitet, ekte konverteringer med medfølgende FFmpeg, avbrudd og opprydding, forhåndsvisning og Qt-flytene, med lokalt genererte mediefiler. Premiere Pro-import, flere timers skoleopptak, defekte minnekort, fysisk full disk og alle GPU-/driverkombinasjoner skal prøves i målmiljøet. Ingen slik godkjenning påstås på grunnlag av syntetiske tester alene.

På utviklingsmaskinen ble oppstart av et tidligere usignert EXE-bygg avvist med «Ingen tilgang». Årsaken er ikke fastslått, og ingen sikkerhetspolicy ble endret eller omgått. Oppstart og komplett flyt fra den pakkede, signerte EXE-en skal derfor verifiseres med standardbruker i målmiljøet, og hele filsettet skal kontrolleres mot `SHA256SUMS.txt` før utrulling.

