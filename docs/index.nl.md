---
description: "HomeDarts for Autodarts brengt elke dart naar Home Assistant: spellen, een scorebord, statistieken en automatiseringen. Lokaal en gratis, zonder cloudaccount."
hide:
  - navigation
  - toc
# The headline of the preview card of a shared link, under the name of the website
# (in one line, which markdownlint doesn't take for the title of the page).
social: { cards_layout_options: { title: "Je Autodarts-bord live in Home Assistant" } }
---

# HomeDarts for Autodarts

![Het pictogram van de integratie: een huis met een dartbord](branding/icon.svg){ width="96" align="right" }

**Je Autodarts-bord live in Home Assistant: lokaal, in realtime en klaar voor automatiseringen.**

HomeDarts for Autodarts brengt je Autodarts-bord naar Home Assistant: een dart verschijnt een fractie van een seconde nadat hij in het bord zit, rechtstreeks van de Board Manager in je eigen netwerk. Elk ander dartbord doet ook mee, met darts die je met de hand invoert of die een Granboard verstuurt. Speel en train ermee, zet een scorebord naast het bord, volg je statistieken en laat je huis meedoen. Geen account, geen cloud, geen client-ID.

HomeDarts for Autodarts is een onofficieel communityproject, niet verbonden aan Autodarts. Tot versie 1.18 heette het Autodarts: [From Autodarts to HomeDarts](new-name.md) legt de nieuwe naam uit en hoe HomeDarts je borden overneemt.

[:material-download: Installeren met HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=Dennis-Otto&repository=homedarts-for-autodarts&category=integration){ .md-button .md-button--primary } [:material-rocket-launch: Aan de slag](getting-started.nl.md){ .md-button } <a href="demo/index.html?lang=nl" class="md-button">:material-play-circle: Live uitproberen</a>

<picture>
  <source media="(max-width: 600px)" srcset="images/en/hero-mobile.webp">
  <img class="off-glb" src="images/en/hero.webp" alt="Animatie: een 301-wedstrijd op de livekaart en het scorebord. Alex gooit drie keer triple 20, de vakken lichten op en het scorebord telt af naar 121; Sam gooit 85; Alex gooit 121 uit met T20, outer bull en D18 voor de game shot">
</picture>

## Wat het doet

<div class="grid cards pictures" markdown>

- ![De livekaart op het dashboard van Home Assistant: de huidige beurt, de drie darts, de laatste beurten, de trainingssessie en het bord](images/en/dashboard-live.png){ loading=lazy }

    :material-lan-connect:{ .lg .middle } **Lokaal en in realtime**

    ---

    Automatisch gevonden met Board Manager 2; Board Manager 1 werkt ook. Er verlaat niets je netwerk, tenzij je de bordzoekfunctie of de onlinebrug gebruikt, en geheimen van het bord worden nooit opgeslagen.

    [:octicons-arrow-right-24: How it works](how-it-works.md)

- ![Animatie: een 180 op het scorebord, met een gouden gloed en confetti](images/en/celebration.webp){ loading=lazy }

    :material-bullseye-arrow:{ .lg .middle } **Spellen**

    ---

    X01 van 101 tot 1001 met de uitgooiroute na elke dart, Cricket, Cut-Throat Cricket, Tactics, Wild Mouse, Random en Hidden Cricket, en negen partyspellen voor maximaal acht spelers, alleen of als wedstrijd van maximaal vier met legs, sets, teams en handicaps.

    [:octicons-arrow-right-24: Games and rules](games.md)

- ![Animatie: Around the Clock op de livekaart; elke treffer schuift het doel door en markeert de vakken van het volgende getal](images/en/training-game.webp){ loading=lazy }

    :material-target:{ .lg .middle } **Training**

    ---

    Trainingssessies die met de eerste dart beginnen, acht trainingsspellen van Around the Clock tot de JDC Challenge, een dagdoel, een trainingsreeks en persoonlijke records.

    [:octicons-arrow-right-24: Training games](games.md#training-games)

- ![Animatie: op het scherm voor een nieuw spel op de tablet bij het bord wordt een spel gekozen, dat op het scorebord begint](images/en/lobby.webp){ loading=lazy }

    :material-monitor-dashboard:{ .lg .middle } **Scorebord en kaarten**

    ---

    Een scorebord voor een tablet of tv, ook via Chromecast, leesbaar vanaf de oche, met een scherm voor een nieuw spel, een caller en een rustmodus. Zeven dashboardkaarten en een automatisch dashboard, in het Engels, Duits, Nederlands, Frans en Spaans.

    [:octicons-arrow-right-24: Scoreboard at the board](scoreboard.md) · [Dashboard cards](cards.md)

- ![Animatie: de heatmap wisselt van vakken naar getallen en de echte posities van de darts, en dan naar de darts van één speler](images/en/heatmap-modes.webp){ loading=lazy }

    :material-chart-line:{ .lg .middle } **Statistieken met heatmaps**

    ---

    3-dart-gemiddelde, first 9-gemiddelde, uitgooi- en dubbelpercentage, een heatmap van elk vak of van de echte dartposities, en waar elke speler per dart het meest scoort. Spelersprofielen met badges, weektrends, een ranglijst, een weekrapport en een trainingsagenda.

    [:octicons-arrow-right-24: Statistics and players](statistics.md)

- ![De galerij met highlights in de mediabrowser van Home Assistant, met foto's van een uitgooi en twee hoge beurten](images/en/media-gallery.png){ loading=lazy }

    :material-home-automation:{ .lg .middle } **Automatiseringen en blueprints**

    ---

    Bordgebeurtenissen voor elke dart, beurt, verwijdering van de darts, bust, gewonnen leg en wedstrijd, en het begin en einde van elk spel. Zestien blueprints: lichtshow, opkomstmuziek, scoreweergave, dart- en oefencallers, highlightfoto's, rapporten, meldingen, routines, spellen starten en darts invoeren met je stem, en antwoorden van Assist over je darts.

    [:octicons-arrow-right-24: Automations](automations.md)

- ![Animatie: het knock-outschema van vijf spelers op het scorebord, tot Alex de finale wint](images/en/tournament-bracket.webp){ loading=lazy }

    :material-tournament:{ .lg .middle } **Toernooien en een bot**

    ---

    Toernooien van drie tot 32 spelers, als iedereen tegen iedereen met een stand, als knock-out, als dubbele knock-out of als groepen en knock-out, aan één bord of op meerdere borden tegelijk, en een bot van niveau 20 tot 120 om X01 en Cricket tegen te spelen.

    [:octicons-arrow-right-24: Tournaments](games.md#tournaments) · [The bot](games.md#playing-against-the-bot)

- ![Animatie: darts ingevoerd met de stem, met Assist geopend boven het scorebord, dat antwoordt met de resterende score](images/en/manual-voice.webp){ loading=lazy }

    :material-microphone:{ .lg .middle } **Stem**

    ---

    Zeg "Speel 501 voor Alex en Sam" tegen Assist, in het Nederlands, Engels, Duits, Frans of Spaans, en het spel begint; daarna voert "Alex heeft 140" of "Triple 20" de darts in, zoals bij een dartautomaat, en "Wat is mijn gemiddelde vandaag?" krijgt zijn antwoord uit de statistieken van het bord. Elk spel start ook met één actie van een automatisering.

    [:octicons-arrow-right-24: Start a game by voice](automations.md#start-a-game-by-voice)

    [:octicons-arrow-right-24: Enter darts by voice](automations.md#enter-darts-by-voice)

    [:octicons-arrow-right-24: Ask Assist about your darts](automations.md#ask-assist-about-your-darts)

</div>

## Van de dart naar je huis

Alles gebeurt in je eigen netwerk, in minder dan een seconde: de Board Manager benoemt het vak, en Home Assistant toont het op de kaarten en geeft het door aan je automatiseringen.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/en/dart-journey-dark.png">
  <img src="images/en/dart-journey-light.png" alt="The journey of a dart: a dart lands in triple 20. The cameras of the board see it, and the Board Manager on the board PC names the field. A realtime message carries it over your network to HomeDarts in Home Assistant, which updates the entities, sends the board events and lights up the field on the cards and the scoreboard. Your automation reacts to the events, for example with flashing lights for a 180 or a caller. All of it takes less than a second and needs no cloud" lang="en" width="560">
</picture>

[:octicons-arrow-right-24: How it works](how-it-works.md)

## Hoe het zich verhoudt

Anders dan de Autodarts-app met de browserextensie Tools for Autodarts, darts-caller en darts-wled, en de andere integraties van Home Assistant voor Autodarts:

- **Zonder cloud:** HomeDarts praat met de lokale interface van de Board Manager en heeft geen Autodarts-account nodig.
- **Entiteiten en gebeurtenissen in Home Assistant:** een gebeurtenis voor elke dart, beurt, verwijdering van de darts, bust, leg en wedstrijd, en zestien blueprints die er meteen iets mee doen.
- **Statistieken thuis:** gemiddelden, heatmaps, profielen en een jaar geschiedenis, opgeslagen in Home Assistant.
- **Ook zonder Autodarts-bord:** op een toetsenblok of met een Granboard via Bluetooth *(experimenteel)*.
- **Gratis:** open source onder de MIT-licentie, zonder betaalde versie.

[Coming from another tool](coming-from.md) vergelijkt alles met bronnen en laat zien hoe je overstapt *(in het Engels)*.

## Handleidingen

- :material-rocket-launch: [**Van nul tot het scorebord**](getting-started.nl.md): Home Assistant, HACS, de integratie en het eerste spel, voor Autodarts-spelers die Home Assistant nog niet kennen
- :material-download: [**Installatie en instellen**](installation.nl.md): vereisten, HACS of handmatig, en de manieren om een bord toe te voegen
- :material-frequently-asked-questions: [**Veelgestelde vragen**](faq.nl.md): het account, apparaten, online spelen, privacy, meerdere borden, schermen, talen en updates

In het Engels:

- :material-pencil: [**Play without Autodarts**](without-autodarts.md): elk dartbord, met elk spel, de training en de statistieken, de darts ingevoerd op een toetsenblok
- :material-bluetooth: [**Granboard over Bluetooth**](granboard.md): de darts van een Granboard via Bluetooth en de ESPHome-proxy's van Home Assistant *(experimenteel)*
- :material-swap-horizontal: [**Coming from another tool**](coming-from.md): de andere integraties, MQTT-bruggen, darts-caller, darts-wled en Tools for Autodarts vergeleken, en hoe je overstapt
- :material-rename-box: [**From Autodarts to HomeDarts**](new-name.md): de nieuwe naam sinds versie 2.0, en hoe HomeDarts je borden overneemt
- :material-bullseye-arrow: [**Games and rules**](games.md): elk spel in één oogopslag, vier manieren om er een te starten, wedstrijden, teams, handicaps, de bull-off en toernooien
- :material-television: [**Scoreboard at the board**](scoreboard.md): een tablet of tv naast het bord, liggend en staand, het scherm voor een nieuw spel, de caller en de rustmodus
- :material-chart-line: [**Statistics and players**](statistics.md): sessies, persoonlijke records, heatmaps, waar je moet mikken, vooruitgang, profielen, prestaties en de ranglijst
- :material-home-automation: [**Automations**](automations.md): zestien blueprints, hun instellingen, bordgebeurtenissen en kant-en-klare voorbeelden
- :material-play-network: [**Online matches**](online-matches.md): busts, gewonnen legs en wedstrijden van onlinewedstrijden als bordgebeurtenissen, met Tools for Autodarts *(experimenteel)*

## Naslag

<div class="grid cards" markdown>

- :material-view-dashboard:{ .lg .middle } [**Dashboard cards**](cards.md)

    ---

    Alle zeven kaarten en het automatische dashboard, met elke optie en de toegankelijkheid.

- :material-format-list-bulleted:{ .lg .middle } [**Entities and events**](entities.md)

    ---

    Elke entiteit, bordgebeurtenis, toestand, eigenschap en actie, en welke generatie van de Board Manager ze levert.

- :material-cog-transfer:{ .lg .middle } [**How it works**](how-it-works.md)

    ---

    Architectuur, update-intervallen, verbindingsgedrag, training en records, opgeslagen gegevens en privacy.

- :material-lifebuoy:{ .lg .middle } [**Troubleshooting**](troubleshooting.md)

    ---

    Meldingen bij het instellen, reparaties, onbeschikbare entiteiten, mislukte acties, diagnose en logboeken.

- :material-shield-lock:{ .lg .middle } [**Security design**](security.md)

    ---

    Wat beschermd wordt, vertrouwensgrenzen, bedreigingen en tegenmaatregelen.

- :material-book-alphabet:{ .lg .middle } [**Glossary**](glossary.md)

    ---

    De woorden van het darten en van deze integratie.

</div>

Wat elke versie bracht, staat in de [changelog](changelog.md), wat er nog komt in de [roadmap](roadmap.md). Voor video's, artikelen en berichten heeft de [creator kit](creator-kit.md) feiten, kant-en-klare teksten, video's en afbeeldingen, vrij te gebruiken.

## Ondersteunde apparaten

- **Board Manager 2:** Autodarts 2 zonder scherm (headless), getest tot 2.1.0, en automatisch gevonden.
- **Board Manager 1:** de klassieke app, getest met 1.0.7.
- **Autodarts Desktop** op Linux werkt volgens een speler; Autodarts Desktop op Windows en de apparaten van Winmau, zoals Autodarts X, zijn nog niet getest.
- **Home Assistant** 2026.8 of nieuwer.
- **Zonder Autodarts:** elk dartbord, met de darts ingevoerd op een toetsenblok.

Alle hardware waarop de Board Manager van Autodarts draait, werkt, want de integratie praat met de Board Manager en niet met de camera's. [Supported devices](README.md#supported-devices) heeft de hele tabel. Staat jouw opstelling er niet in? Een [compatibiliteitsrapport](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new?template=board_compatibility.yml) helpt, ook als alles werkt.

## Talen

De integratie spreekt Nederlands, Engels, Duits, Frans en Spaans: het instellen, de opties, de entiteiten en hun toestanden, de acties, meldingen en reparaties, de kaarten met hun editors en de caller van het scorebord. Ze volgt de taal van Home Assistant; een regionale variant zoals `nl-BE` telt als die taal.

Deze website is er in het Engels en Duits, en de start, de snelle start, de installatie en de veelgestelde vragen ook in het Nederlands, Frans en Spaans. De andere pagina's toont hij in het Engels. Spreek je Nederlands? [Help mee met de vertaling](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CONTRIBUTING.md#translations): verbeter een zin of vertaal een pagina die je mist, direct op GitHub, zonder te programmeren.
