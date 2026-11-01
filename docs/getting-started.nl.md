---
description: "Van nul tot het scorebord op een tablet bij je Autodarts-bord in ongeveer een uur: Home Assistant, HACS, de integratie en het dashboard."
---

# Van nul tot het scorebord

[← Documentatie](README.md) · [English](getting-started.md)

Je speelt op een Autodarts-bord en hebt Home Assistant nog nooit gebruikt? Deze handleiding brengt je van nul tot het scorebord op een tablet naast je bord. Home Assistant, HACS en de integratie zijn gratis. Reken op ongeveer een uur; de meeste tijd gaat zitten in het installeren van Home Assistant zelf.

<img src="images/en/scoreboard-lobby.png" alt="Het scherm voor een nieuw spel op een liggende tablet: de spellen per groep met 501 gekozen, Alex en Sam met hun foto, Sam begint vanaf 301, drie legs per set, double out en de startknop" width="760">

**Op deze pagina:** [Wat je nodig hebt](#wat-je-nodig-hebt) · [1. Home Assistant installeren](#1-home-assistant-installeren) · [2. HACS installeren](#2-hacs-installeren) · [3. De integratie installeren](#3-de-integratie-installeren) · [4. Je bord toevoegen](#4-je-bord-toevoegen) · [5. Het dashboard maken](#5-het-dashboard-maken) · [6. Het scorebord naast het bord zetten](#6-het-scorebord-naast-het-bord-zetten) · [7. Je eerste spel spelen](#7-je-eerste-spel-spelen) · [En dan?](#en-dan) · [Als iets niet werkt](#als-iets-niet-werkt)

## Wat je nodig hebt

- **Je Autodarts-bord,** ingesteld en werkend. [Ondersteunde apparaten](index.nl.md#ondersteunde-apparaten) noemt de geteste opstellingen. Geen Autodarts? [Speel zonder Autodarts](without-autodarts.md) op elk dartbord en voer je darts in op een toetsenblok.
- **Een apparaat voor Home Assistant** dat altijd aan staat, in hetzelfde netwerk als het bord: een Raspberry Pi 4 of 5, een mini-pc of een virtuele machine op een computer die altijd draait. Home Assistant verkoopt ook kant-en-klare apparaten. Gebruik een apart apparaat: de bord-pc heeft zijn rekenkracht nodig voor de detectie.
- **Een gratis GitHub-account,** waarmee HACS integraties downloadt.
- **Een scherm voor het scorebord,** als je er een wilt: een tablet, een tv met een browser of een oude telefoon.

## 1. Home Assistant installeren

Volg de officiële [installatiehandleiding](https://www.home-assistant.io/installation/) voor je apparaat; die laat elke stap met afbeeldingen zien. Kies op een Raspberry Pi **Home Assistant OS** ([handleiding voor de Raspberry Pi](https://www.home-assistant.io/installation/raspberrypi)).

Open Home Assistant aan het eind in een browser, meestal op `http://homeassistant.local:8123`, en maak je account aan. De [handleiding voor de eerste start](https://www.home-assistant.io/getting-started/onboarding/) legt de vragen uit.

## 2. HACS installeren

HACS is de winkel voor integraties en kaarten van de community, zoals deze. Volg de officiële handleiding om [HACS te downloaden](https://www.hacs.xyz/docs/use/download/download/) en het [in te stellen](https://www.hacs.xyz/docs/use/configuration/basic/) met je GitHub-account. Daarna staat **HACS** in de zijbalk van Home Assistant.

## 3. De integratie installeren

[![Open je Home Assistant en open deze repository in HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Dennis-Otto&repository=homedarts-for-autodarts&category=integration)

1. Selecteer de knop hierboven en bevestig het adres van je Home Assistant. HACS opent deze integratie. Zonder de knop: open **HACS**, zoek naar **HomeDarts** en open de integratie.
2. Selecteer **Download**.
3. Start Home Assistant opnieuw: **Instellingen → Systeem**, de aan-uitknop rechtsboven, **Herstart Home Assistant**.

## 4. Je bord toevoegen

[![Open je Home Assistant en begin met het instellen van HomeDarts for Autodarts.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=homedarts)

Met Board Manager 2 vindt Home Assistant het bord meestal vanzelf: **Instellingen → Apparaten en diensten** toont **Autodarts-bord gevonden** onder *Ontdekt*. Selecteer **Voeg toe** en bevestig. De animatie toont de weg van hier naar het scorebord, in minder dan een minuut.

<img src="images/en/setup.webp" alt="Animatie: het instellen in vijf stappen met bijschriften, in het Engels, op het scherm van een telefoon. 1: Home Assistant toont het gevonden bord onder Ontdekt. 2: toevoegen en bevestigen in het venster Autodarts-bord gevonden; het bord is ingesteld en de apparaatpagina opent. 3: instellingen, dashboards, dashboard toevoegen. 4: de zoekopdracht vindt HomeDarts, de titel HomeDarts, aanmaken. 5: het nieuwe dashboard opent op de liveweergave en dan op het scorebord, dat drie triple 20's optelt tot 180" width="100%">

Selecteer anders de knop hierboven en kies **Borden zoeken in dit netwerk**, of **Bordadres invoeren** met het IP-adres van de bord-pc. Je hebt geen Autodarts-account nodig.

<img src="images/en/setup-menu.png" alt="Het menu voor het instellen van HomeDarts: borden zoeken in dit netwerk, een bordadres invoeren of een dartbord zonder Autodarts" width="520">

De [installatiehandleiding](installation.nl.md#je-bord-toevoegen) legt de manieren uitgebreid uit. Zonder Autodarts kies je **Dartbord zonder Autodarts: elke dart zelf invoeren** en geef je het bord een naam; [Play without Autodarts](without-autodarts.md) laat de rest zien.

## 5. Het dashboard maken

Ga naar **Instellingen → Dashboards → Voeg dashboard toe → HomeDarts**. Geef het een titel en selecteer **Maak aan**: dat maakt een compleet dashboard voor je bord, met weergaven voor het livespel, het scorebord, de training, de spelers en het bord. Het werkt zichzelf bij wanneer je een bord toevoegt of wanneer een latere versie nieuwe weergaven brengt.

<img src="images/en/dashboard-strategy.png" alt="De trainingsweergave van het automatische dashboard" width="760">

## 6. Het scorebord naast het bord zetten

1. Open op de tablet Home Assistant in de browser of in de [Home Assistant-app](https://companion.home-assistant.io/) en log in. Een eigen gebruiker zonder beheerdersrechten voorkomt dat het scherm je instellingen verandert.
2. Open het HomeDarts-dashboard en de weergave *Scorebord*.
3. Tik op de knop voor volledig scherm rechtsboven op het scorebord: die vult het scherm en houdt het aan. Waar de browser het scherm niet aan kan houden, zoals op een adres met `http://`, zet je de schermtime-out van de tablet uit; zie [volledig scherm](scoreboard.md#full-screen).

De [handleiding van het scorebord](scoreboard.md#set-up-the-screen) bevat de details en de opties, zoals de caller.

## 7. Je eerste spel spelen

Tik op het scorebord op **Nieuw spel**. Kies 501, voeg jezelf toe, voeg met **+ Bot** de **bot** toe als je alleen speelt, en tik op **501 starten**. Gooi je darts: het scorebord telt, toont je uitgooiroute en laat na elke beurt de volgende speler gooien.

Leest het bord een dart verkeerd, tik dan op die dart in de beurt en corrigeer hem. De [handleiding van de spellen](games.md#start-a-game) toont elk spel en de andere manieren om er een te starten.

## En dan?

- **Licht en geluid:** de [blueprints](automations.md#blueprints) laten je lampen knipperen bij een 180, roepen de scores om of maken een highlightfoto. Ze worden met de integratie meegeleverd en staan klaar op de pagina met blueprints van Home Assistant.
- **Je vooruitgang:** persoonlijke records, een heatmap van je darts, trends en prestaties staan in de [handleiding van de statistieken](statistics.md).
- **Vrienden op bezoek:** teams, handicaps en toernooien voor maximaal 32 spelers staan in de [handleiding van de spellen](games.md).

## Als iets niet werkt

- De [handleiding voor probleemoplossing](troubleshooting.md) legt elke melding bij het instellen en elke reparatiemelding uit.
- Stel je vraag in [GitHub Discussions](https://github.com/Dennis-Otto/homedarts-for-autodarts/discussions/categories/q-a). Daar worden vragen beantwoord, zodat elk antwoord ook de volgende speler helpt. Vragen in het Engels of Duits worden het snelst beantwoord.
- Staat jouw opstelling niet in de lijst van [ondersteunde apparaten](index.nl.md#ondersteunde-apparaten), dan helpt een [compatibiliteitsrapport](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new?template=board_compatibility.yml), of het nu werkt of niet.
