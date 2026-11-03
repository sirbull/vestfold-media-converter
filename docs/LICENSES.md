# Lisensgrunnlag

Applikasjonens egen kode er GPL-3.0-or-later, med full tekst i `LICENSE`. Den portable mappen inneholder også appens kildekode. Kilde, byggskript og låste avhengigheter skal følge samme versjon som programfilene.

## Valgt FFmpeg-bygning

- Bygger: Gyan Doshi, [byggside](https://www.gyan.dev/ffmpeg/builds/).
- Versjon: 9.0.2 Essentials, Windows x64, statisk. Arkiv-URL, kontrollsum og FFmpeg-commit er i `vendor/ffmpeg/origin.json`.
- FFmpeg-commit oppgitt av bygger: `946fcce07b`.
- `--enable-gpl`, `--enable-version3`, `--enable-libx264`, `--enable-libx265` finnes i den kontrollerte bygningen.
- Bygger oppgir GPLv3 for Windows-bygningene. Lisensutskrift og komplett configure-linje genereres i `BUILD-INFO.json`. GPL-teksten og byggerens README følger i lisensmappen.

[FFmpegs lisensside](https://ffmpeg.org/legal.html) forklarer hvordan valgfrie GPL-komponenter endrer lisensen til den ferdige FFmpeg-bygningen. [FFmpegs LICENSE](https://ffmpeg.org/doxygen/7.0/md_LICENSE.html) nevner blant annet libx264/libx265. Bygningen som brukes her skal ikke omtales som LGPL. `--enable-nonfree` aksepteres ikke av inventarskriptet.

Før videredistribusjon må distributør oppfylle GPLv3 for **det faktisk leverte binærsettet**, inkludert tilsvarende kildekode, relevante bygghjelpemidler og vilkår/notices fra alle innlenkede tredjepartskomponenter. FFmpeg-commit og leverandørlenke gir sporbarhet, men dekker ikke alene alle statiske avhengigheter. Kildepakken til hele Gyan-bygningen er **ikke innhentet automatisk i dette prosjektet**. Dette er et konkret utestående punkt før skoleutrulling, ikke et påstått ferdig oppfylt krav.

## Qt, Python og byggverktøy

PySide6 Essentials/Shiboken leveres fra Qt for Python. Se [Qt for Python-lisenser](https://doc.qt.io/qtforpython-6/licenses.html) og lisensfilene i de faktiske hjulpakkene. Appen bruker dynamiske Qt-biblioteker, uten Qt WebEngine/Multimedia. Byggskriptet kopierer medfølgende `licenses`/`LICENSE`/`COPYING`-filer fra de valgte pakkene. Det velges ingen kommersiell Qt-lisens.

Python: PSF License og inkluderte notices i `PYTHON-LICENSE.txt` fra valgt runtime. PyInstaller: GPL med et eget bootloader-unntak; pakkefølgende tekst kopieres. De nøyaktige versjonene ligger i `uv.lock` og i bygginventaret.

## Nunito

Nunito fra [Google Fonts sitt kildearkiv](https://github.com/google/fonts/tree/main/ofl/nunito) følger med som en uendret variabel TTF-font. Den er lisensiert under **SIL Open Font License 1.1**. Original copyright- og lisenstekst ligger sammen med fonten i `src/vestfold_converter/assets/fonts/OFL.txt`. `ORIGIN.json` dokumenterer kilde-URL og SHA-256. Ved bygging kopieres lisensen også til lisenssamlingen som `Nunito-OFL-1.1.txt`. Fonten lastes fra programmappen til Qt sitt prosessminne; den installeres ikke i Windows og hentes ikke fra nettet ved bruk.

## Distribusjonsrutine

1. Arkiver kildekode og bygggrunnlag for app, runtime og de faktiske tredjepartsbinærene. Oppfyll GPL/LGPLs krav til utlevering, merknader og brukerrettigheter.
2. Bevar lisenssamlingen og dokumenter eventuelle modifikasjoner.
3. Kjør testene, bygg på Windows, signer etter organisasjonens regler og generer kontrollsummer etter siste endring.
4. Vurder lisens- og eventuelle patentforhold sammen med ansvarlig IT/juridisk funksjon før deling.

