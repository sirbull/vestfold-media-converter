# Visuell retning

Appen kombinerer en enkel mediekø med et vennlig uttrykk inspirert av [Vestfold fylkeskommunes designmanual](https://www.vestfoldfylke.no/no/Designmanual/). Dette er en tilpasning for appen, ikke en påstand om at alle profilregler er fulgt ordrett.

- [Konseptet Dualitet](https://www.vestfoldfylke.no/no/Designmanual/meny/Visuell-verktoykasse/konseptet/) og [grafiske elementer](https://www.vestfoldfylke.no/no/Designmanual/meny/Visuell-verktoykasse/grafiske-elementer/) inspirerer kombinasjonen av sirkler, kvadrater og avrundede skjoldformer. Detaljene er tegnet med Qt. I kompakt visning fjernes toppdekoren og importillustrasjonen gjøres mindre.
- Fra [fargepaletten](https://www.vestfoldfylke.no/no/Designmanual/meny/Visuell-verktoykasse/farger/) brukes blant annet lyse Strand-toner, Vann og Nype til små elementer og bakgrunner. Utvalget i køen har en svak rosa flate og tydelig rød sidemarkering.
- Den røde konverteringsknappen og små gule markeringer beholdes fra brukerens ønskede retning. Gult brukes mer sparsomt enn i første fargeutkast.
- Nunito beholdes som avtalt. Fonten er også del av manualens [typografiske profil](https://www.vestfoldfylke.no/no/Designmanual/meny/Visuell-verktoykasse/typografi/).
- Brukerens eget programikon (skjold med avspillingsknapp) beholder farger og proporsjoner. Ingen tagline legges til.

Lys og mørk modus har samme hierarki. Forhåndsvisning, filvalg og eksport skal være lette å finne; dekor står aldri over kontroller eller tekst. Skjermbilder kan gjenskapes med `uv run --frozen --offline python scripts/preview.py`.

Tema velges med tre ikonknapper i en samlet kontroll: skjerm, sol og måne. Ett ikon er markert med gult om gangen. Forklarende navn finnes i verktøytips og for skjermlesere, og piltastene bytter mellom valgene.
