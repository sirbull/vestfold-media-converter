# Testomfang

`uv run python -m pytest -q` kjører:

- Analyse basert på strømmer, inklusive lyd med vedlagt albumgrafikk og ukjent filendelse.
- Automatiske standardprofiler, kompatibilitetsmodell og avvisning av ugyldige innstillinger.
- Ekte MTS/H.264/AC-3, MP4/AAC, MOV, MKV, WAV, MP3, FLAC og video uten lyd til anbefalt profil.
- Avanserte lydformater, HEVC, ProRes, høy kvalitet, stream copy og uttrekk av lyd fra video.
- Valgt lydspor, standardspor, interlaced materiale, rotasjon, faststart og kontroll av utstrømmer.
- Norsk tekst/mellomrom i filstier, navnekonflikter, originalenes kontrollsummer og mappeimport.
- Feilaktige filer, bortfalt kilde, simulert plassmangel, avbrudd før og under FFmpeg og opprydding.
- 64-bit filstørrelser over 4 GB med simulert stat-resultat, uten å allokere gigabyte i testene.
- Qt-flyter med faktisk bakgrunnsanalyse og konvertering: blandet kø uten justeringer, kun lydinnstillinger for lydfiler, flervalg og lukking under arbeid.
- FFmpeg-basert forhåndsvisning: MTS/MP4/interlaced video, stillbilde, avspilling/pause, søking til en annen scene, kansellering ved bytte til lyd, lesefeil og opprydding. Mappeimport og valg av en annen rad styrer forhåndsvisningen ved siden av køen, også i kompakt visning.
- Avspillingsikoner og hopp på fem sekunder: sceneendring med ekte video, avgrensning ved start/slutt, fortsatt avspilling etter hopp og deaktivering for lydfiler. Små vinduer kontrolleres også med søkefelt og visningsikoner inne i filpanelet.
- Importbrowser: forhåndsvisning og avspilling før import, flervalg på tvers av liste/rutenett, navigasjon, filfilter, justerbar panelbredde, små vinduer og opprydding ved avbrudd. Feil ved lesing av Hurtigtilgang og systemfilvelgerens retur/avbrudd testes uten å endre systemets snarveier.
- Klikkbar filsti og Windows-søk: søketreff med forhåndsvisning, bytte av visning, åpning av treffets mappe, tomme treff, utilgjengelig indeks og kansellering ved mappebytte. Søkeord med apostrofer, SQL-jokertegn og norsk tekst testes som data, sammen med resultatgrense og ugyldige svar fra søketjenesten. Automatiske tester bruker simulerte indekssvar; faktisk Windows Search kontrolleres separat fra terminalen.

Mediefiksturer lages med FFmpeg i pytest sin midlertidige mappe. Ingen eksterne mediedata eller nettverk brukes under testene. Qt-testene kjører med offscreen-plattform. En Windows-CI er inkludert; denne er ikke automatisk kjørt bare fordi filen finnes lokalt.

Manuell målmiljøtest kreves for Premiere Pro-import og tidslinjeavspilling, lange og store faktiske opptak, fysisk disk full, defekte minnekort, omdirigerte mapper/tilgangsfeil, GPU-er/drivere, Narrator, høy DPI, HDR-utstyr og Windows-sikkerhetspolicyer. Syntetiske filer kan ikke dokumentere alle skader eller kameravarianter.

