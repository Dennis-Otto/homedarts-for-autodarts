---
description: "Korte antwoorden over HomeDarts for Autodarts: account, apparaten, online spelen, privacy, meerdere borden, schermen, talen, updates en overstappen."
---

# Veelgestelde vragen

[← Documentatie](README.md) · [English](faq.md)

Korte antwoorden, elk met de pagina die de details heeft; die pagina's zijn meestal in het Engels. Mis je een vraag? Stel hem in [GitHub Discussions](https://github.com/Dennis-Otto/homedarts-for-autodarts/discussions).

**Ga naar:** [Voordat je begint](#voordat-je-begint) · [Spelen](#spelen) · [Schermen en talen](#schermen-en-talen) · [Privacy](#privacy) · [Updates en overstappen](#updates-en-overstappen)

## Voordat je begint

### Heb ik een Autodarts-account of een abonnement nodig?

Nee. De integratie praat met de Board Manager op je bord-pc, via je eigen netwerk, op TCP-poort 3180. Ze heeft geen Autodarts-login, wachtwoord of API-sleutel nodig, en geen abonnement zoals Autodarts Plus, en ze verandert nooit de registratie van je bord bij Autodarts. Een dartbord zonder Autodarts heeft helemaal niets van Autodarts nodig. [Vereisten](installation.nl.md#vereisten)

### Wat heb ik nodig?

Home Assistant 2026.8 of nieuwer met [HACS](https://hacs.xyz), en een Autodarts-bord in je netwerk of een willekeurig dartbord waarvan je de darts op een toetsenblok invoert. Nog geen ervaring met Home Assistant? [Van nul tot het scorebord](getting-started.nl.md) brengt je van nul tot het eerste spel op het scorebord.

### Werkt het met Autodarts Desktop, Autodarts X of Lens?

De integratie heeft een Board Manager nodig die Home Assistant in je netwerk bereikt. Board Manager 2 is getest tot 2.1.0, de klassieke Board Manager 1 werkt ook, en volgens een speler werkt Autodarts Desktop 2.0.2 op Linux. Autodarts Desktop op Windows en Autodarts X zijn nog niet getest. Een [compatibiliteitsrapport](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new?template=board_compatibility.yml) vertelt ons hoe het met de jouwe gaat, of het nu werkt of niet. [Ondersteunde apparaten](index.nl.md#ondersteunde-apparaten)

Lens telt de score met de camera van een telefoon of tablet in de Autodarts-app, zonder Board Manager in je netwerk, dus de integratie kan de darts niet lezen. Voer ze in plaats daarvan in op het toetsenblok. Een koppeling via de cloud van Autodarts komt er ook niet: Autodarts geeft geen client-ID's uit aan integraties van derden ([beslissing 0025](decisions/0025-no-cloud-link.md)). [Play without Autodarts](without-autodarts.md)

### Kost het iets?

Nee. De integratie is gratis en open source onder de [MIT-licentie](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/LICENSE): er valt niets te betalen en er is geen betaalde versie. [Sponsoren](https://github.com/sponsors/Dennis-Otto) helpt het project en is helemaal vrijwillig.

### Is dit een officiële integratie van Autodarts?

Nee. HomeDarts for Autodarts is een onofficieel communityproject, niet verbonden aan Autodarts, en wordt onderhouden door [@Dennis-Otto](https://github.com/Dennis-Otto). Het gebruikt de lokale interface van de Board Manager, die het team van Autodarts openhoudt. Tot versie 1.18 heette het Autodarts, totdat Autodarts om een eigen naam vroeg. [From Autodarts to HomeDarts](new-name.md) · [Credits and license](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/README.md#credits-and-license)

## Spelen

### Ik heb geen Autodarts-bord. Kan ik het gebruiken?

Ja. Stel een dartbord zonder Autodarts in en voer elke dart in op het toetsenblok van het scorebord, of met je stem. Elk spel, de training en de statistieken werken. Krijgt je dartbord later Autodarts, dan behoudt het de spellen, spelers en statistieken. [Play without Autodarts](without-autodarts.md)

### Kan ik onlinewedstrijden spelen?

Ja, op play.autodarts.io zoals voorheen. De integratie ziet dan de darts op je eigen bord: `dart_detected`, `visit_thrown` en het verwijderen van de darts komen zoals gewoonlijk binnen. Busts, gewonnen legs en wedstrijden gebeuren in de browser; de optionele onlinebrug brengt ze naar Home Assistant met de browserextensie Tools for Autodarts *(experimenteel)*. [Online matches](online-matches.md)

### Meerdere spelers met hun eigen Autodarts-account op één scherm?

Ja, online op play.autodarts.io: de Chrome-extensie [Player Switch for Autodarts](https://dennis-otto.github.io/player-switch-for-autodarts/), van de auteur van deze integratie, houdt ieders account klaar, en één tik op een tegel wisselt van speler, zonder in te loggen. Ze heeft geen Home Assistant nodig, en de integratie ziet de darts op je bord, wie er ook is ingelogd. [Online matches](online-matches.md#several-accounts-at-one-display)

### Het bord las een dart verkeerd. Hoe corrigeer ik dat?

Tik op het scorebord op de dart en kies waar hij terechtkwam, op de toetsen of op een afbeelding van het bord. In automatiseringen doet `homedarts.correct_dart` hetzelfde, en `homedarts.undo_visit` neemt de laatste beurt terug. [Correct and enter darts](scoreboard.md#correct-and-enter-darts)

### Kan ik meerdere borden gebruiken?

Ja. Elk bord is een eigen vermelding en een eigen apparaat, met eigen entiteiten, spellen en statistieken, en het automatische dashboard geeft elk bord zijn weergaven, zoals `/scoreboard-1` en `/scoreboard-2`. De acties van de integratie hebben dan de `config_entry_id` van het bord nodig. [Several boards](without-autodarts.md#several-boards)

Een clubavond kan ook [één toernooi op meerdere borden tegelijk](games.md#a-tournament-on-several-boards) spelen, elk bord met een eigen wedstrijd.

Een speler die op twee borden gooit, heeft op elk een profiel. [`homedarts.restore`](entities.md#restore-a-backup-homedartsrestore) met `mode: merge` voegt een back-up van het ene bord toe aan het andere, en de cijfers van de speler worden opgeteld. [Backups](statistics.md#backups)

## Schermen en talen

### Kan ik het scorebord op een tv of een Fire-tablet tonen?

Ja: op elk scherm waarvan de browser je Home Assistant opent, zoals een tablet aan de muur, ook een Fire-tablet, een tv met een browser, een kleine pc of een oude telefoon. Er hoeft niets op geïnstalleerd te worden. Geef het scherm een eigen gebruiker in Home Assistant en open de weergave *Scorebord* van het automatische dashboard, op volledig scherm of in een kioskbrowser. Een tv met een Chromecast of een Google Nest Hub toont het via Home Assistant Cast, zonder eigen browser. [Set up the screen](scoreboard.md#set-up-the-screen) · [Home Assistant Cast](scoreboard.md#on-a-tv-with-home-assistant-cast)

### Welke talen spreekt het, en welke stemmen heeft de caller?

Nederlands, Engels, Duits, Frans en Spaans, volgens de taal van Home Assistant: het instellen, de entiteiten, de kaarten en de caller. De caller van het scorebord spreekt met een stem van de browser van het scherm voor die taal, of met de opgenomen geluiden van een stempakket, zoals een van darts-caller of een die je met Piper opneemt. De blueprints van de dartcaller en de oefencaller spreken in de taal van Home Assistant, via de tekst-naar-spraak en de luidsprekers van je Home Assistant. [Talen](index.nl.md#talen) · [Which caller?](automations.md#which-caller)

## Privacy

### Wat verlaat mijn netwerk?

Niets, in de lokale modus. Alleen wat je zelf kiest, praat met het internet: de bordzoekfunctie raadpleegt de openbare zoekdienst van Autodarts één keer, en de onlinebrug ontvangt alleen de oproepen van Tools for Autodarts. Geheimen van het bord worden nooit opgeslagen, en de diagnose verbergt de ID's van borden, adressen en spelersnamen. Sommige browsers spreken de oproepen van het scorebord uit met online stemmen; een offline stem van het apparaat houdt ze thuis. [Privacy](how-it-works.md#privacy) · [Security design](security.md)

### Waar worden mijn statistieken bewaard?

In de eigen opslag van Home Assistant, nooit in de cloud: de trainingssessies, het oefenspel, de persoonlijke records, de spelersprofielen met hun wedstrijden, en de trainingsagenda met een jaar aan sessies en wedstrijden. Wie het bord verwijdert, verwijdert ze ook, maar pas na een [back-up](statistics.md#backups) ervan, en [`homedarts.export`](entities.md#export-training-data-homedartsexport) schrijft ze weg voor een spreadsheet. [Stored data](how-it-works.md#stored-data)

### Ik heb mijn bord verwijderd. Zijn mijn statistieken weg?

Nee. Voordat een bord wordt verwijderd, schrijft HomeDarts een back-up van alles wat het heeft opgeslagen naar `homedarts/backups` in de mediamap. Voeg het bord opnieuw toe, en de reparatie *Er is een back-up van …* brengt alles terug; [`homedarts.restore`](entities.md#restore-a-backup-homedartsrestore) zet elke back-up terug. [Backups](statistics.md#backups)

## Updates en overstappen

### Hoe werk ik de Board Manager bij?

Op de bord-pc, zoals Autodarts het beschrijft. Home Assistant laat je weten wanneer een update nodig is: met Board Manager 2 toont de update-entiteit *Software* de geïnstalleerde en de nieuwste versie, en een bord met Board Manager 1 krijgt een reparatiemelding voor de stap naar Board Manager 2. De integratie zelf werk je bij via HACS. [Update to Board Manager 2](installation.md#update-from-board-manager-1-to-board-manager-2) · [Health and connections](entities.md#health-and-connections)

### De integratie heette Autodarts. Wat verandert er voor mij?

Sinds versie 2.0 heet ze HomeDarts for Autodarts, met het domein `homedarts`. Voeg na de update **HomeDarts for Autodarts** toe en kies **De borden van de integratie Autodarts overnemen**: je borden houden hun entiteiten, geschiedenis, statistieken en dashboards. Automatiseringen en scripts die de oude acties aanroepen, zoals `autodarts.start_game`, hebben de nieuwe namen nodig, zoals `homedarts.start_game`; een reparatie noemt ze. [From Autodarts to HomeDarts](new-name.md)

### Ik gebruik de oorspronkelijke HACSAutodarts. Hoe stap ik over?

Installeer HomeDarts ernaast: het origineel heeft het domein `autodarts`, HomeDarts het domein `homedarts`, dus beide draaien tegelijk. Voeg je bord toe aan HomeDarts, zet je automatiseringen over, verwijder dan de vermelding van HACSAutodarts en verwijder het in HACS. HomeDarts neemt die vermelding niet over. [Switch from the original integration](installation.md#switch-from-the-original-integration)

### Ik gebruik een ander Autodarts-hulpmiddel. Hoe stap ik over?

[Coming from another tool](coming-from.md) behandelt Autodarts Local, de andere integraties van Home Assistant, MQTT-bruggen, darts-caller en darts-wled, en Tools for Autodarts: wat elk biedt, de entiteiten, gebeurtenissen en blueprints die de plaats ervan innemen, en hoe je overstapt terwijl het geïnstalleerd blijft. HomeDarts heeft een eigen domein, dus geen van hen hoeft eerst weg.

### Iets werkt niet. Waar krijg ik hulp?

[Troubleshooting](troubleshooting.md) legt de meldingen, reparaties en diagnose uit. Stel vragen in [GitHub Discussions](https://github.com/Dennis-Otto/homedarts-for-autodarts/discussions) en meld fouten als [issue](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new/choose), met de diagnose van je bord; [SUPPORT.md](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/SUPPORT.md) legt uit waar je wat vraagt.
