# HomeDarts for Autodarts

[← Projektseite](https://github.com/Dennis-Otto/homedarts-for-autodarts) · [English documentation](README.md) · [Nederlands](index.nl.md) · [Français](index.fr.md) · [Español](index.es.md)

**Dein Autodarts-Board live in Home Assistant: lokal, in Echtzeit und bereit für Automationen.**

**HomeDarts for Autodarts** bringt dein Autodarts-Board nach Home Assistant: jeden Dart, live vom Board Manager in deinem Netzwerk. Jede andere Dartscheibe spielt auch mit, ihre Darts von Hand eingegeben oder von einem Granboard gesendet. HomeDarts for Autodarts ist ein inoffizielles Community-Projekt ohne Verbindung zu Autodarts. Bis Version 1.18 hieß es Autodarts; [Von Autodarts zu HomeDarts](https://dennis-otto.github.io/homedarts-for-autodarts/de/new-name.html) erklärt den neuen Namen und wie HomeDarts deine Boards übernimmt.

Die [Website der Dokumentation](https://dennis-otto.github.io/homedarts-for-autodarts/de/) hat dieselben Seiten, mit Suche und Umschalter auf Englisch; ihre Startseite gibt es auch auf [Niederländisch](https://dennis-otto.github.io/homedarts-for-autodarts/nl/), [Französisch](https://dennis-otto.github.io/homedarts-for-autodarts/fr/) und [Spanisch](https://dennis-otto.github.io/homedarts-for-autodarts/es/).

<img src="images/de/hero.webp" alt="Animation: ein 301-Match auf der Live-Karte und der Anzeigetafel nebeneinander. Alex wirft drei Triple 20, die Felder leuchten auf und die Anzeigetafel zählt auf 121 herunter; Sam wirft 85; Alex checkt 121 mit T20, Single-Bull und D18 zum Game shot" width="100%">

**Schnell zu:** [Schnellstart](#schnellstart) · [Das kann die Integration](#das-kann-die-integration) · [Anleitungen](#anleitungen) · [Anwendungsfälle](#anwendungsfälle) · [Blueprints](#blueprints) · [Glossar](https://dennis-otto.github.io/homedarts-for-autodarts/de/glossary.html) · [Änderungen](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md)

## Schnellstart

Du brauchst Home Assistant ab 2026.8 mit [HACS](https://hacs.xyz) und ein Autodarts-Board in deinem Netzwerk oder eine beliebige Dartscheibe, deren Darts du auf einem Tastenfeld eingibst ([Voraussetzungen](#voraussetzungen)).

1. **Mit HACS installieren, dann Home Assistant neu starten.**

   [![Home Assistant öffnen und dieses Repository in HACS anzeigen.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Dennis-Otto&repository=homedarts-for-autodarts&category=integration)

   Alternativ öffnest du **HACS** in Home Assistant, suchst nach **HomeDarts** und wählst **Download**.

2. **Board hinzufügen.** Mit Board Manager 2 erscheint dein Board meist schon unter **Einstellungen → Geräte & Dienste → Entdeckt**. Sonst:

   [![Home Assistant öffnen und HomeDarts for Autodarts einrichten.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=homedarts)

   Wähle **Boards im Netzwerk suchen** oder **Board-Adresse eingeben** und bestätige. Ohne Autodarts wählst du **Dartscheibe ohne Autodarts: jeden Dart selbst eingeben**.

3. **Karten hinzufügen.** Erzeuge in einem Schritt ein komplettes Dashboard: **Einstellungen → Dashboards → Dashboard hinzufügen → HomeDarts**. Oder bearbeite ein Dashboard, wähle **Karte hinzufügen** und suche nach *HomeDarts*.

Neu bei Home Assistant? [Von null bis zur Anzeigetafel](https://dennis-otto.github.io/homedarts-for-autodarts/de/getting-started.html) führt dich von null bis zur Anzeigetafel neben deinem Board. Die [Installationsanleitung](https://dennis-otto.github.io/homedarts-for-autodarts/de/installation.html) beschreibt die manuelle Installation, die Neukonfiguration, Updates und das Entfernen.

Du kommst von Autodarts Local, einer anderen Integration für Autodarts oder darts-caller? [Umstieg von anderen Werkzeugen](https://dennis-otto.github.io/homedarts-for-autodarts/de/coming-from.html) zeigt, was hier an seine Stelle tritt und wie du umsteigst. Kurze Antworten auf die häufigen Fragen stehen in den [häufigen Fragen](https://dennis-otto.github.io/homedarts-for-autodarts/de/faq.html).

## Warum

- **Sofort und lokal.** Darts erscheinen in Home Assistant Sekundenbruchteile, nachdem sie landen, direkt vom Board Manager in deinem Netzwerk. Kein Konto, keine Cloud, keine Client-ID.
- **Ein ganzer Dartabend.** X01 von 101 bis 1001, sechs Cricket-Spiele, neun Partyspiele und acht Trainingsspiele, allein, als Match mit bis zu vier Spielern, als Partyspiel mit bis zu acht oder als Turnier mit bis zu 32, mit einer Anzeigetafel für das Tablet am Board.
- **Deine Entwicklung in Zahlen.** Averages, Trefferbilder der echten Dart-Positionen, Bestleistungen, Abzeichen, Wochentrends, Spielerprofile, ein Wochenbericht und ein Jahr Verlauf, alles bei dir zu Hause.
- **Dein Zuhause spielt mit.** Licht für eine 180, ein Caller auf deinen Lautsprechern, das Boardlicht bei der Entnahme, ein Foto deines besten Checkouts.

## Das kann die Integration

[Spielen](#spielen) · [Wie am Dartautomaten](#wie-am-dartautomaten) · [Trainieren](#trainieren) · [Auswerten](#auswerten) · [Bildschirm am Board](#bildschirm-am-board) · [Automatisieren](#automatisieren) · [Lokal und privat](#lokal-und-privat)

### Spielen

- X01 von 101 bis 1001 mit Straight, Double und Master In und Out, dem 50/50-Bull, einer Rundengrenze und dem Checkout-Weg nach jedem Dart
- Cricket, Cut-Throat Cricket, Tactics, Wild Mouse, Random Cricket und Hidden Cricket auf einer Kreidetafel
- Partyspiele für bis zu acht: Shanghai, Halve-It, Killer, Golf, Baseball, Count-Up, Bermuda, Round the World und Gotcha
- Turniere mit drei bis 32 Spielern: jeder gegen jeden mit Tabelle, K.-o.-System, Doppel-K.-o.-System oder Gruppen mit K.-o.-System, mit ihren Turnierbäumen, an einem Board oder auf mehreren Boards zugleich

<details>
<summary>Matches, der Bot, Korrekturen und mehr</summary>

- Matches mit bis zu vier Spielern, Legs und Sätzen, zwei Teams zu zwei, Startpunkten als Handicap und Ausbullen, und eine Zusammenfassung jedes Matches
- Ein Bot mit Stärke 20 bis 120 als Gegner bei X01 und Cricket
- Ein Tipp korrigiert einen falsch erkannten Dart; ein Tastenfeld gibt Darts von Hand ein, und die letzte Aufnahme lässt sich zurücknehmen
- Kein Autodarts? Jede Dartscheibe spielt mit, jeder Dart auf dem Tastenfeld eingegeben
- Stellwürfe, wo kein Checkout möglich ist, etwa T20 T20 S17 für Rest 32

</details>

<img src="images/de/tournament-bracket.webp" alt="Animation: der Turnierbaum mit fünf Spielern auf der Anzeigetafel; die Sieger rücken in die nächste Runde, bis Alex das Finale gewinnt" width="100%">

[Spiele und Regeln →](https://dennis-otto.github.io/homedarts-for-autodarts/de/games.html)

### Wie am Dartautomaten

- Wild Mouse, auch als Minnesota Cricket bekannt, mit Doubles, Triples und Three in a Bed
- Random Cricket mit neuen Zahlen in jedem Leg und Hidden Cricket, dessen Zahlen sich erst zeigen, wenn ein Dart sie findet
- Zielhilfen auf der Kreidetafel: grün, wo ein Dart punktet, gelb, was zu schließen ist, und ein Dart ohne Wirkung durchgestrichen
- Konfetti und ein goldenes Leuchten bei 180, Game Shot und Match, ein Leuchten bei einem Ton
- So wird gespielt: jedes Spiel kurz erklärt auf dem Bildschirm für ein neues Spiel, für Gäste, die es noch nie gespielt haben, und Partyspiele für bis zu acht Spieler

<img src="images/de/celebration.webp" alt="Animation: eine 180 auf der Anzeigetafel. Alex wirft drei Triple 20, ein goldenes Leuchten erhellt die Anzeigetafel und Konfetti fliegt aus ihrer Mitte, dann zeigt die Anzeigetafel 321 wie zuvor" width="100%">

[Wild Mouse →](https://dennis-otto.github.io/homedarts-for-autodarts/de/games.html#wild-mouse)

### Trainieren

- Trainingssessions, die mit dem ersten Dart beginnen und die letzten 20 Sessions behalten
- Acht Trainingsspiele: Around the Clock, Doppeltraining, Checkout-Training, Bob's 27, der 121-Checkout, Catch 40, die JDC Challenge und das Singles-Training
- [Trainingspläne](https://dennis-otto.github.io/homedarts-for-autodarts/de/games.html#trainingspläne), die mehrere Trainingsspiele nacheinander spielen, mit einem Plan des Tages nur ein Tippen entfernt
- Ein Tagesziel, eine Trainingsserie und Bestleistungen mit einem Ereignis, sobald du eine übertriffst

<img src="images/de/training-game.webp" alt="Animation: Around the Clock auf der Live-Karte; jeder Treffer bringt das Ziel weiter und umrandet die Felder der nächsten Zahl" width="100%">

[Trainingsspiele →](https://dennis-otto.github.io/homedarts-for-autodarts/de/games.html#trainingsspiele)

### Auswerten

- 3-Dart-Average, First-9-Average, Checkout- und Doppelquote
- Ein Trefferbild jedes Feldes oder der echten Dart-Positionen, mit der Streuung in Millimetern
- Spielerprofile mit Abzeichen in Bronze, Silber, Gold und Platin und eine Bestenliste; ein Profil lässt sich mit allen Zahlen umbenennen, und zwei Namen eines Spielers werden zu einem Profil

<details>
<summary>Trends, Berichte, Kalender und Exporte</summary>

- Wochentrends, direkte Vergleiche und der Match-Verlauf jedes Spielers
- Die Quote jedes Doubles, ein Wochenbericht, ein Trainingskalender und Exporte als CSV oder JSON
- Ein Backup jedes Boards, bevor es gelöscht wird, das ein wieder hinzugefügtes Board wiederherstellt, und die Spieler zweier Boards in einem zusammengeführt
- Langzeitstatistik für Grafiken über Wochen und Monate

</details>

<p align="center"><img src="images/de/heatmap-modes.webp" alt="Animation: Das Trefferbild der Trainingskarte wechselt von Feldern zu Zahlen und den echten Dart-Positionen, dann zu den Darts eines Spielers" width="520"></p>

[Statistik und Spieler →](https://dennis-otto.github.io/homedarts-for-autodarts/de/statistics.html)

### Bildschirm am Board

- Eine Anzeigetafel für Tablet oder Fernseher, auch über Chromecast, lesbar vom Abwurf aus, mit einer [Vollbild-Taste](https://dennis-otto.github.io/homedarts-for-autodarts/de/scoreboard.html#vollbild), die den Bildschirm anlässt
- Eine Spielauswahl, um Spiel, Spieler und Format direkt am Board zu wählen oder ein Turnier zu starten
- Ein Caller, der das Spiel über den Browser des Bildschirms ansagt, auch mit den aufgenommenen Voice-Packs von darts-caller oder einer Stimme, die du mit Piper aufnimmst
- Ein Ruhemodus mit Bestenliste, Bestleistungen, den Darts von heute und einer Uhr
- Ein [Stream-Overlay](https://dennis-otto.github.io/homedarts-for-autodarts/de/scoreboard.html#stream-overlay) für OBS: Punkte, Weg und Aufnahme über dem Bild deines Streams, durchsichtig oder auf einer Keyfarbe

<p align="center"><img src="images/de/lobby.webp" alt="Animation: Auf dem Tablet öffnet Neues Spiel die Spielauswahl, Cricket und ein zweiter Spieler werden gewählt und das Spiel startet" width="600"></p>

[Anzeigetafel am Board →](https://dennis-otto.github.io/homedarts-for-autodarts/de/scoreboard.html)

### Automatisieren

- Board-Ereignisse für jeden Dart, jede Aufnahme, Entnahme, jedes Überwerfen, gewonnene Leg und Match, Beginn und Ende jedes Spiels, jede Bestleistung und mehr
- Sechzehn Blueprints: Lichtshow, Walk-on-Musik, Spielstand-Anzeige, Dart- und Übungs-Caller, Highlight-Fotos, Berichte, Warnungen, Routinen, Spielstart und Darts per Sprache sowie Antworten von Assist zu deinen Darts, die mit der Integration kommen und mit ihr aktuell bleiben ([ansehen](#blueprints))
- Jedes Spiel mit einer Aktion starten, auch per Sprache, Assist deine Darts sagen, wie am Dartautomaten, und es fragen: „Wie ist mein Schnitt heute?“
- Online-Matches auf play.autodarts.io über eine optionale Brücke *(experimentell)*

<img src="images/de/media-gallery.png" alt="Die Highlight-Galerie in der Medienansicht von Home Assistant: Fotos eines 121er-Checkouts, einer 180 und einer 140" width="100%">

[Automationen →](https://dennis-otto.github.io/homedarts-for-autodarts/de/automations.html)

### Lokal und privat

- Mit Board Manager 2 automatisch gefunden; Board Manager 1 funktioniert auch
- Nichts verlässt dein Netzwerk, außer du nutzt die Board-Suche oder die Online-Brücke; Geheimnisse des Boards werden nie gespeichert
- Sieben Dashboard-Karten und ein automatisches Dashboard, auf Deutsch, Englisch, Niederländisch, Französisch und Spanisch ([Sprachen](#sprachen))
- Leicht für einen Raspberry Pi: Eine Nachricht des Boards aktualisiert nur die Entitäten, die zeigen, was sich geändert hat ([Aktualisierung](https://dennis-otto.github.io/homedarts-for-autodarts/de/how-it-works.html#aktualisierung))
- Alle Regeln der Qualitätsskala von Home Assistant bis Platin, 100 % Testabdeckung

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="images/de/architecture-dark.png">
    <img src="images/de/architecture-light.png" alt="Architektur: Der Board Manager auf dem Board-PC sendet Echtzeitereignisse an HomeDarts in Home Assistant; die Integration stellt Entitäten, Board-Ereignisse, Karten und Automationen bereit" width="480">
  </picture>
</p>

[Funktionsweise →](https://dennis-otto.github.io/homedarts-for-autodarts/de/how-it-works.html)

## Im Vergleich

Wie sich HomeDarts mit der Autodarts-App und ihrer Browser-Erweiterung, mit darts-caller und darts-wled und mit den anderen Home-Assistant-Integrationen für Autodarts vergleicht:

| Merkmal | HomeDarts | Autodarts-App mit [Tools for Autodarts](https://github.com/creazy231/tools-for-autodarts) | [darts-caller](https://github.com/Peschi90/darts-caller) und [darts-wled](https://github.com/Peschi90/darts-wled) | Andere Home-Assistant-Integrationen |
| --- | --- | --- | --- | --- |
| **Läuft ohne Cloud** | Ja, mit der [lokalen Schnittstelle](https://dennis-otto.github.io/homedarts-for-autodarts/de/how-it-works.html#datenschutz) des Board Managers | Nein, mit einem [Autodarts-Konto](https://autodarts.com/) | Nein, darts-caller [meldet sich bei Autodarts an](https://github.com/Peschi90/darts-caller#autodarts-login) | Manche ([Einzelheiten](https://dennis-otto.github.io/homedarts-for-autodarts/de/coming-from.html#darf-es-bleiben)) |
| **Entitäten und Ereignisse in Home Assistant** | Ja, ein [Ereignis](https://dennis-otto.github.io/homedarts-for-autodarts/de/entities.html#board-ereignisse) für jeden Dart, jede Aufnahme, Entnahme, jedes Überwerfen, Leg und Match | Nein | Nein | Sensoren der aktuellen Aufnahme oder des Spiels |
| **Blueprints** | [Sechzehn Blueprints](https://dennis-otto.github.io/homedarts-for-autodarts/de/automations.html#blueprints) | Nein | Nein | Nein |
| **Lichtshow** | Blueprint [Light show](https://dennis-otto.github.io/homedarts-for-autodarts/de/automations.html#light-show), für WLED oder jedes Licht | WLED, mit Tools | WLED, mit darts-wled | Eigene Automationen |
| **Caller** | Auf der [Anzeigetafel](https://dennis-otto.github.io/homedarts-for-autodarts/de/scoreboard.html#der-caller) oder deinen [Lautsprechern](https://dennis-otto.github.io/homedarts-for-autodarts/de/automations.html#welcher-caller) | In der App, mit einer Premium-Stimme in [Plus](https://autodarts.com/); mehr mit Tools | Sprachpakete, mit darts-caller | Nein |
| **Statistik bleibt zu Hause** | [Ja](https://dennis-otto.github.io/homedarts-for-autodarts/de/statistics.html): Averages, Trefferbilder, Profile und ein Jahr Verlauf | Nein, im Autodarts-Konto | Nein | Nein |
| **Ohne Autodarts-Board** | Ja, auf einem [Tastenfeld](https://dennis-otto.github.io/homedarts-for-autodarts/de/without-autodarts.html) oder einem [Granboard über Bluetooth](https://dennis-otto.github.io/homedarts-for-autodarts/de/granboard.html) *(experimentell)* | Ja, auf einem Tastenfeld oder mit [Lens](https://autodarts.com/) | Nein | Nein |
| **Online-Matches** | Deine Darts, und die Momente des Matches über die [Online-Brücke](https://dennis-otto.github.io/homedarts-for-autodarts/de/online-matches.html) *(experimentell)* | Ja | Ja | Manche, über die Cloud |
| **Lizenz und Kosten** | [MIT](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/LICENSE), kostenlos | Autodarts: ein kostenloser Tarif und das bezahlte [Plus](https://autodarts.com/); Tools: [CC BY-NC 4.0](https://github.com/creazy231/tools-for-autodarts/blob/main/LICENSE) | Kostenlos, ohne angegebene Lizenz | MIT, Apache 2.0 oder ohne Lizenzdatei |

*Stand Oktober 2026, aus der Dokumentation und dem Code jedes Projekts. [Umstieg von anderen Werkzeugen](https://dennis-otto.github.io/homedarts-for-autodarts/de/coming-from.html) hat die Einzelheiten, die Quellen und den Weg zum Umstieg.*

## Voraussetzungen

**Home Assistant ab 2026.8** mit [HACS](https://hacs.xyz) und ein Autodarts-Board in deinem Netzwerk oder eine beliebige Dartscheibe, deren Darts du auf einem Tastenfeld eingibst ([Spielen ohne Autodarts](https://dennis-otto.github.io/homedarts-for-autodarts/de/without-autodarts.html)), oder ein Granboard in Reichweite des Bluetooth von Home Assistant ([Granboard](https://dennis-otto.github.io/homedarts-for-autodarts/de/granboard.html), experimentell). Ein Autodarts-Konto brauchst du nicht.

- **Board Manager 2**, also Autodarts 2 ohne Bildschirm, ist empfohlen und bis 2.1.0 getestet; der klassische **Board Manager 1** funktioniert auch.
- Laut dem Bericht eines Spielers funktioniert auch **Autodarts Desktop** 2.0.2 unter Linux.
- Autodarts Desktop unter Windows und Winmau-Autodarts-Geräte wie Autodarts X sind noch nicht getestet; ein [Kompatibilitätsbericht](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new?template=board_compatibility.yml) hilft, ob es klappt oder nicht.

## Anleitungen

### Erste Schritte

- [Von null bis zur Anzeigetafel](https://dennis-otto.github.io/homedarts-for-autodarts/de/getting-started.html): für Autodarts-Spieler ohne Home Assistant: Home Assistant und HACS aufsetzen, die Integration installieren, das Board hinzufügen und das erste Spiel auf der Anzeigetafel
- [Installation und Einrichtung](https://dennis-otto.github.io/homedarts-for-autodarts/de/installation.html): Voraussetzungen, HACS und manuelle Installation, die Wege, ein Board hinzuzufügen, Neukonfiguration, Updates und Entfernen
- [Spielen ohne Autodarts](https://dennis-otto.github.io/homedarts-for-autodarts/de/without-autodarts.html): jede Dartscheibe mit allen Spielen, dem Training und den Statistiken: einrichten, die Darts auf einem Tastenfeld eingeben, und was anders ist
- [Granboard über Bluetooth](https://dennis-otto.github.io/homedarts-for-autodarts/de/granboard.html): die Darts eines Granboards über das Bluetooth von Home Assistant und ESPHome-Proxys, für jedes Spiel *(experimentell)*
- [Häufige Fragen](https://dennis-otto.github.io/homedarts-for-autodarts/de/faq.html): kurze Antworten zu Konto, Geräten, Online-Spiel, Datenschutz, mehreren Boards, Bildschirmen, Sprachen, Updates und Umstieg
- [Umstieg von anderen Werkzeugen](https://dennis-otto.github.io/homedarts-for-autodarts/de/coming-from.html): wie sich HomeDarts mit Autodarts Local, den anderen Integrationen, MQTT-Brücken, darts-caller, darts-wled und Tools for Autodarts vergleicht, und wie du von ihnen umsteigst
- [Von Autodarts zu HomeDarts](https://dennis-otto.github.io/homedarts-for-autodarts/de/new-name.html): warum die Integration seit Version 2.0 einen neuen Namen hat und wie HomeDarts deine Boards mit Entitäten, Statistiken und Dashboards übernimmt

### Anleitungen

- [Spiele und Regeln](https://dennis-otto.github.io/homedarts-for-autodarts/de/games.html): alle Spiele im Überblick, vier Wege, eines zu starten, Matches, Teams, Handicaps, das Ausbullen, die Match-Zusammenfassung, Turniere und die Regeln von X01, den Cricket-Spielen, den Partyspielen und den Trainingsspielen
- [Anzeigetafel am Board](https://dennis-otto.github.io/homedarts-for-autodarts/de/scoreboard.html): ein Tablet oder Fernseher neben dem Board: Einrichtung, Quer- und Hochformat, Spielauswahl, Turniere, Caller und Ruhemodus
- [Statistik und Spieler](https://dennis-otto.github.io/homedarts-for-autodarts/de/statistics.html): Trainingssessions, Bestleistungen, Trefferbild und Dart-Positionen, wohin zielen, Fortschritt über die Zeit, Doubles, Spielerprofile, Erfolge, Trends, Bestenliste, Wochenbericht, Trainingskalender, Exporte und Backups
- [Automationen](https://dennis-otto.github.io/homedarts-for-autodarts/de/automations.html): sechzehn Blueprints, ihre Einstellungen, Board-Ereignisse und fertige Beispiele
- [Online-Matches](https://dennis-otto.github.io/homedarts-for-autodarts/de/online-matches.html): Überwerfen, gewonnene Legs und Matches von Online-Matches als Board-Ereignisse, mit der Browser-Erweiterung Tools for Autodarts *(experimentell)*

### Nachschlagen

- [Dashboard-Karten](https://dennis-otto.github.io/homedarts-for-autodarts/de/cards.html): Live-Karte, Trainingskarte, Board-Status, Anzeigetafel, Doubles-Karte, Spielerkarte, Bestenliste und automatisches Dashboard, mit allen Optionen und Barrierefreiheit
- [Entitäten und Ereignisse](https://dennis-otto.github.io/homedarts-for-autodarts/de/entities.html): alle Entitäten, Board-Ereignisse, Zustände, Attribute und Aktionen, und welche Board-Manager-Generation sie liefert
- [Funktionsweise](https://dennis-otto.github.io/homedarts-for-autodarts/de/how-it-works.html): Architektur, Aktualisierung, Verbindungsverhalten, Board-Manager-Generationen, Adresswechsel, Training und Bestleistungen, gespeicherte Daten und Datenschutz
- [Fehlerbehebung](https://dennis-otto.github.io/homedarts-for-autodarts/de/troubleshooting.html): Meldungen bei der Einrichtung, Reparaturen, nicht verfügbare Entitäten, fehlgeschlagene Aktionen, Diagnose und Logs
- [Sicherheit](https://dennis-otto.github.io/homedarts-for-autodarts/de/security.html): Schutzgüter, Vertrauensgrenzen, Bedrohungen und Gegenmaßnahmen
- [Glossar](https://dennis-otto.github.io/homedarts-for-autodarts/de/glossary.html): die Begriffe des Dartsports und dieser Integration, mit ihren englischen Entsprechungen

### Projekt

- [Änderungen](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CHANGELOG.md): was jede Version gebracht hat (auf Englisch)
- [Roadmap](https://dennis-otto.github.io/homedarts-for-autodarts/de/roadmap.html): erschienene Versionen und was als Nächstes kommt
- [Development](https://dennis-otto.github.io/homedarts-for-autodarts/development.html), [Releases](https://dennis-otto.github.io/homedarts-for-autodarts/de/releases.html): die Entwickler-Dokumentation, auf Englisch
- [Bilder und Prüfungen der Karten](https://dennis-otto.github.io/homedarts-for-autodarts/de/development.html): wie die Bilder der Dokumentation entstehen, der Screenshot-Bot, der Bildvergleich und die Prüfung der Barrierefreiheit, auf Deutsch
- [Creator-Kit](https://dennis-otto.github.io/homedarts-for-autodarts/de/creator-kit.html): Fakten, Beschreibungen, fertige Beiträge für Foren, Reddit und Discord, Videos, Animationen und Bilder für YouTuber, Streamer und Blogger, frei nutzbar

## Anwendungsfälle

### Gezielt trainieren

Verfolge nach jeder Session deinen Average, deine 180er und wohin deine Darts fliegen, und lass dich von Tagesziel und Trainingsserie antreiben.

<p align="center">
  <picture>
    <source media="(prefers-color-scheme: light)" srcset="images/de/training-card-light.png">
    <img src="images/de/training-card.png" alt="Trainingskarte mit 3-Dart-Average, Trefferbild, Statistik und letzten Aufnahmen" width="480">
  </picture>
</p>

[Statistik →](https://dennis-otto.github.io/homedarts-for-autodarts/de/statistics.html)

### Ein Dartabend mit Freunden

Wähle das Spiel am Tablet neben dem Board oder starte ein Turnier, lass die Anzeigetafel zählen und ansagen, und sieh zwischen den Spielen Tabelle oder Bestenliste.

<p align="center"><img src="images/de/lobby.webp" alt="Animation: In der Spielauswahl des Tablets am Board wird ein Spiel gewählt und startet auf der Anzeigetafel" width="600"></p>

[Anzeigetafel →](https://dennis-otto.github.io/homedarts-for-autodarts/de/scoreboard.html)

### Atmosphäre

Lichtshows für eine 180 oder ein gewonnenes Match, ein Dart-Caller auf deinen Lautsprechern und das Boardlicht bei der Entnahme.

<img src="images/de/blueprint-light-show.png" alt="Eine neue Automation aus dem Blueprint Light show mit einem Abschnitt für jeden Moment des Spiels" width="100%">

[Automationen →](https://dennis-otto.github.io/homedarts-for-autodarts/de/automations.html)

### Highlights festhalten

Ein Foto des Boards nach jeder 180 oder jedem Checkout, auf dem Handy und in einer Galerie nach Monaten.

<img src="images/de/media-gallery.png" alt="Die Highlight-Galerie in der Medienansicht mit Fotos eines Checkouts und zweier hoher Aufnahmen" width="100%">

[Highlight-Galerie →](https://dennis-otto.github.io/homedarts-for-autodarts/de/automations.html#highlight-galerie)

### Fortschritt über Monate

Langzeitgrafiken, ein Wochenbericht aufs Handy und ein Trainingskalender mit einem Jahr Sessions und Matches.

<p align="center"><img src="images/de/dashboard-trends.png" alt="Grafiken der Darts pro Tag, des 3-Dart-Averages und der Übungslegs über vier Wochen" width="480"></p>

[Fortschritt über die Zeit →](https://dennis-otto.github.io/homedarts-for-autodarts/de/statistics.html#fortschritt-über-die-zeit)

### Ein Board, das sich selbst kümmert

Starte die Erkennung, wenn du den Dartraum betrittst, stoppe sie, wenn du gehst, und erfahre, wenn das Board offline geht oder eine Kamera ausfällt.

<picture>
  <source media="(prefers-color-scheme: light)" srcset="images/de/status-card-light.png">
  <img src="images/de/status-card.png" alt="Board-Status-Karte mit Erkennung, Verbindungen, Board-PC und Kameras" width="100%">
</picture>

[Blueprints →](https://dennis-otto.github.io/homedarts-for-autodarts/de/automations.html#blueprints)

## Blueprints

Die Integration bringt jeden Blueprint mit und hält die, die du nicht geändert hast, mit jedem ihrer Updates aktuell. Wähle einen auf der Blueprint-Seite von Home Assistant, wähle dein Board und fertig; die Buttons importieren einen von GitHub, etwa einen, den du gelöscht hast.

- **Light show.** Deine WLED-Presets oder Raumlichter bei einer 180, einem High Finish, beim Überwerfen, einem gewonnenen Leg oder Match, einer Bestleistung, einem Erfolg, dem Sieger eines Turniers und mehr, und danach zurück zu deinem normalen Licht.

  [![Blueprint „Light show“ importieren](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Flight_show.yaml)

- **Walk-on music.** Der Walk-on-Song jedes Spielers, wenn ein Spiel beginnt, wie auf der Bühne, bis zum ersten Dart, und der Song des Siegers nach dem Match.

  [![Blueprint „Walk-on music“ importieren](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fwalk_on.yaml)

- **Dart caller.** Jede Aufnahme auf deinen Lautsprechern, mit einer eigenen Ansage für die 180, in der Sprache von Home Assistant oder mit den aufgenommenen Sounds eines Voice-Packs.

  [![Blueprint „Dart caller“ importieren](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fdart_caller.yaml)

- **Highlight photo.** Ein Bild des Boards nach einer 180 oder einem Checkout, aufs Handy und in eine Galerie der Medienansicht, und mit einer Kamera im Raum ein Clip ab ein paar Sekunden vor dem Dart.

  [![Blueprint „Highlight photo“ importieren](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fhighlight_photo.yaml)

<details>
<summary>Zwölf weitere: Aufnahme feiern, Übungs-Caller, Spielstand-Anzeige, Entnahme, Erkennung, Routinen, Berichte, Warnungen und Sprache</summary>

- **Celebrate a visit score.** Deine Aktionen für jede 180, jede Aufnahme ab 100 oder eine Punktzahl deiner Wahl, sobald der dritte Dart landet.

  [![Blueprint „Celebrate a visit score“ importieren](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fvisit_score.yaml)

- **Practice caller.** Wer was braucht, Überwerfen und Game shots des Übungsspiels auf deinen Lautsprechern, in der Sprache von Home Assistant.

  [![Blueprint „Practice caller“ importieren](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fpractice_caller.yaml)

- **Score display.** Der Spielstand des Übungsspiels nach jedem Dart, sein Checkout-Weg, eine 180 und der Sieger auf einer AWTRIX 3 oder einem PixelIt am Board.

  [![Blueprint „Score display“ importieren](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fscore_display.yaml)

- **Takeout actions.** Licht am Board, während du die Darts ziehst.

  [![Blueprint „Takeout actions“ importieren](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Ftakeout.yaml)

- **Start and stop detection automatically**, je nachdem, ob jemand im Dartraum ist.

  [![Blueprint „Start and stop detection automatically“ importieren](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fauto_detection.yaml)

- **Training session routine.** Licht, Erkennung und Kalibrierung folgen deinen Trainingssessions.

  [![Blueprint „Training session routine“ importieren](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Ftraining_session.yaml)

- **Weekly report.** Deine Trainingswoche mit dem Trend deines 3-Dart-Averages, als Benachrichtigung in der Sprache von Home Assistant.

  [![Blueprint „Weekly report“ importieren](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fweekly_report.yaml)

- **Training report.** Deine Tageszusammenfassung mit dem 3-Dart-Average, in der Sprache von Home Assistant.

  [![Blueprint „Training report“ importieren](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Ftraining_report.yaml)

- **Board problem alert**, wenn das Board offline geht oder eine Kamera ausfällt, mit optionaler Entwarnung.

  [![Blueprint „Board problem alert“ importieren](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fboard_alert.yaml)

- **Start a game by voice.** Sag Assist „Starte 501 für Alex und Sam“, auf Deutsch, Englisch, Spanisch, Französisch oder Niederländisch.

  [![Blueprint „Start a game by voice“ importieren](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fstart_game_by_voice.yaml)

- **Enter darts by voice.** Sag Assist „Alex hat 140“, „Triple 20“ oder „Nächster Spieler“, wie am Dartautomaten, auf Deutsch, Englisch, Spanisch, Französisch oder Niederländisch.

  [![Blueprint „Enter darts by voice“ importieren](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fenter_darts_by_voice.yaml)

- **Ask Assist about your darts.** Frag Assist „Wie ist mein Schnitt heute?“, „Wie viele 180er diese Woche?“ oder „Wohin soll ich zielen?“, auf Deutsch, Englisch, Spanisch, Französisch oder Niederländisch, und die Statistiken des Boards antworten.

  [![Blueprint „Ask Assist about your darts“ importieren](https://my.home-assistant.io/badges/blueprint_import.svg)](https://my.home-assistant.io/redirect/blueprint_import/?blueprint_url=https%3A%2F%2Fgithub.com%2FDennis-Otto%2Fhomedarts-for-autodarts%2Fblob%2Fmain%2Fblueprints%2Fautomation%2Fhomedarts%2Fask_about_darts.yaml)

</details>

Die Blueprints sind auf Englisch beschriftet. Die Caller, der Trainings- und der Wochenbericht sprechen von sich aus die Sprache von Home Assistant, und eigene Texte, etwa für die Ansagen, wählst du beim Anlegen. Die [Anleitung zu Automationen](https://dennis-otto.github.io/homedarts-for-autodarts/de/automations.html) enthält deutsche Beispiele.

<!-- --8<-- [start:devices-and-languages] -->

## Unterstützte Geräte

| Aufbau | Unterstützt | Getestet mit |
| --- | --- | --- |
| Board Manager 2: Autodarts 2 ohne Bildschirm (Headless) | 2.x | 2.0.0, 2.0.2 und 2.1.0 |
| Board Manager 1 (klassische App) | 1.x | 1.0.7 |
| Autodarts Desktop unter Linux | Funktioniert laut Spielerbericht | 2.0.2 unter Ubuntu 24.04 ([Bericht](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/105)) |
| Autodarts Desktop unter Windows und anderen Systemen | Noch nicht getestet | – |
| Winmau-Autodarts-Geräte wie Autodarts X | Noch nicht getestet | – |
| Kameras | Jede Anzahl, die der Board Manager unterstützt | 3 |
| Home Assistant | ab 2026.8 ([warum](decisions/0022-home-assistant-2026-8-as-the-oldest-release.md), auf Englisch) | 2026.8.0 und 2026.9.4 |

Jede Board-Hardware, auf der der Autodarts Board Manager läuft, funktioniert, weil die Integration mit dem Board Manager spricht, nicht mit den Kameras. Einträge „laut Spielerbericht“ hat ein Spieler an seinem eigenen Board getestet, nicht das Projekt.

Seit September 2026 beschreibt die Doku von Autodarts den Board Manager als Browser-Oberfläche von Autodarts 0.x, die ab Version 2 nicht mehr unterstützt wird. Die lokale Schnittstelle auf Port 3180, die die Integration nutzt, antwortet mit Autodarts 2.1.0 weiterhin. Ändert ein Update sie, zeigt die Integration eine Reparaturmeldung, statt still auszufallen (siehe [Fehlerbehebung](troubleshooting.de.md#reparaturen)). Läuft dein Setup nicht in der Tabelle, hilft ein [Kompatibilitätsbericht](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new?template=board_compatibility.yml), auch wenn alles klappt.

Mit **Board Manager 2.1** funktioniert die Integration wie bisher, mit diesen Unterschieden:

- Der Schalter *Automatisch nachkalibrieren* ist nicht verfügbar, weil Board Manager 2.1 diese Option nicht mehr hat, und das erzeugte Dashboard lässt ihn weg. *Beim Start kalibrieren* und *Verzerrungskorrektur* bleiben.
- Die Tasten *Kamerastreams starten* und *Kamerastreams stoppen* sind nicht verfügbar, weil Board Manager 2.1 diese Befehle nicht mehr hat. Die Liveansicht der Kameras funktioniert ohne sie.
- *Hand erkannt*, *Bild stabil*, *Darts teilweise entfernt* und *Darts vollständig entfernt* kommen im Moment ihrer Änderung über den zweiten Socket des Boards, `/api/events/system`. Nur wenn dieser Socket ausbleibt, aktualisieren sie sich alle 2 Sekunden, solange die Erkennung läuft, und eine Hand, die nur einen Moment am Board ist, kann dann fehlen.

## Sprachen

Die Integration spricht Deutsch, Englisch, Niederländisch, Französisch und Spanisch: Einrichtung, Optionen, Entitäten und ihre Zustände, Aktionen, Meldungen und Reparaturen, die Karten mit ihren Editoren und der Caller der Anzeigetafel. Sie folgt der Sprache von Home Assistant, eine regionale Variante wie `de-CH` oder `es-419` zählt zu ihrer Sprache. Andere Sprachen sehen Englisch.

- Die Namen der Entitäten legt Home Assistant in der Sprache des Servers fest (**Einstellungen → System → Allgemein**), Zustände und Karten folgen der Sprache deines Benutzerprofils.
- Der Caller spricht die Sprache der Karte mit einer Stimme deines Browsers oder Tablets für diese Sprache, oder mit einem [Voice-Pack](scoreboard.de.md#voice-packs) aufgenommener Ansagen; `homedarts.generate_voice_pack` nimmt eines in der Sprache deiner Wahl auf.
- Die Dokumentation gibt es auf Englisch und Deutsch; ihre Startseite, die ersten Schritte, die Installation und die häufigen Fragen auch auf Niederländisch, Französisch und Spanisch, deren Websites die übrigen Seiten auf Englisch zeigen. Die Blueprints sind auf Englisch beschriftet, weil Home Assistant Blueprints nicht übersetzt. Ihre Ansagen sprechen trotzdem jede der fünf Sprachen: Die Integration gibt den Ereignissen die Worte der Caller und des Wochenberichts und dem Trainingsbericht seine Zusammenfassung in der Sprache von Home Assistant mit ([Ansagen in der Sprache von Home Assistant](automations.de.md#ansagen-in-der-sprache-von-home-assistant)). Die Sprach-Blueprints verstehen Sätze in allen fünf Sprachen. Assist antwortet in der Sprache von Home Assistant, bei *Ask Assist about your darts* in der Sprache der Frage.

Texte, die in einer Sprache fehlen oder älter sind als ihr englisches Original, stehen im [Übersetzungs-Issue](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues?q=is%3Aissue%20is%3Aopen%20label%3Atranslations) dieser Sprache, das ein Bot aktuell hält. Es erklärt, wie du sie direkt auf GitHub korrigierst, ganz ohne Programmierkenntnisse. Jede Sprache hat zwei kleine eigene Dateien, `translations/<Sprache>.json` für die Integration und `frontend/text/<Sprache>.js` für die Karten, beide in `custom_components/homedarts/`. Eine Übersetzung verbessern oder eine Sprache hinzufügen: [Übersetzungen in CONTRIBUTING.md](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CONTRIBUTING.md#translations).

<!-- --8<-- [end:devices-and-languages] -->

## Bekannte Einschränkungen

- **Keine Spieldaten aus der Cloud.** Autodarts vergibt keine Client-IDs an Integrationen von Dritten, deshalb gibt es keine Cloud-Verknüpfung; alles funktioniert mit dem Board Manager in deinem Netzwerk.
- **Online-Matches über eine Browser-Erweiterung.** Überwerfen und Game shots von Online-Matches kommen nur an, solange die Autodarts-Seite mit Tools for Autodarts offen ist, einer Erweiterung von Dritten. [Grenzen](https://dennis-otto.github.io/homedarts-for-autodarts/de/online-matches.html#grenzen).
- **Trainingssessions zählen Darts, keine Spiele.** Eine Session zählt jeden Dart, den das Board erkennt; Spieler, Legs und Checkouts gehören zum Übungsspiel, das seine eigene Statistik führt.
- **Board-Manager-Updates installierst du auf dem Board-PC.** Die Update-Entität meldet neue Versionen von Board Manager 2.
- **Liveansicht der Kameras nur mit Board Manager 2.** Mit Board Manager 1 zeigen die Kamera-Entitäten Standbilder.

## Hilfe und Mitmachen

- **Fragen und Ideen:** Die [häufigen Fragen](https://dennis-otto.github.io/homedarts-for-autodarts/de/faq.html) beantworten die üblichen; den Rest fragst du in den [GitHub Discussions](https://github.com/Dennis-Otto/homedarts-for-autodarts/discussions), gern auf Deutsch. **Fehler:** [Issues](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new/choose), mit den Diagnosedaten deines Boards. [SUPPORT.md](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/SUPPORT.md) erklärt, wo du was fragst.
- **Ausprobiert?** Ein [Erfahrungsbericht](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new?template=tester_report.yml) sagt uns, was geklappt hat, was nicht und was dir fehlt; kurze Antworten genügen, gern auf Deutsch.
- **Du sprichst Deutsch, Niederländisch, Französisch oder Spanisch?** Die [Übersetzungs-Issues](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues?q=is%3Aissue%20is%3Aopen%20label%3Atranslations) nennen die Texte, die in deiner Sprache fehlen oder veraltet sind, und wie du sie im Browser korrigierst, ganz ohne Programmierkenntnisse.
- **Sicherheit:** Melde Schwachstellen vertraulich, wie in [SECURITY.md](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/SECURITY.md) beschrieben.
- **Zeig dein Board:** Teile ein Foto deines Boards, des Bildschirms daneben und was Home Assistant damit macht, unter [Show and tell](https://github.com/Dennis-Otto/homedarts-for-autodarts/discussions/new?category=show-and-tell). Es gibt anderen Ideen und zeigt ihnen, dass die Integration an Boards wie ihrem läuft.
- **Zeigen:** Für Videos, Artikel und Beiträge gibt es ein [Creator-Kit](https://dennis-otto.github.io/homedarts-for-autodarts/de/creator-kit.html) mit Fakten, fertigen Texten, Videos und Bildern zur freien Verwendung.
- **Mitmachen:** Beiträge sind willkommen; [CONTRIBUTING.md](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CONTRIBUTING.md) erklärt die Prüfungen. Die Mitarbeit folgt dem [Verhaltenskodex](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/CODE_OF_CONDUCT.md) und der [Governance](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/GOVERNANCE.md) des Projekts.

## Qualität und Sicherheit

[![CodeQL](https://github.com/Dennis-Otto/homedarts-for-autodarts/actions/workflows/codeql.yml/badge.svg)](https://github.com/Dennis-Otto/homedarts-for-autodarts/actions/workflows/codeql.yml)
[![Secret scan](https://github.com/Dennis-Otto/homedarts-for-autodarts/actions/workflows/secret-scan.yml/badge.svg)](https://github.com/Dennis-Otto/homedarts-for-autodarts/actions/workflows/secret-scan.yml)
[![SBOM](https://github.com/Dennis-Otto/homedarts-for-autodarts/actions/workflows/sbom.yml/badge.svg)](https://github.com/Dennis-Otto/homedarts-for-autodarts/actions/workflows/sbom.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/Dennis-Otto/homedarts-for-autodarts/badge)](https://scorecard.dev/viewer/?uri=github.com/Dennis-Otto/homedarts-for-autodarts)
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/14935/badge)](https://www.bestpractices.dev/projects/14935)

- Erfüllt jede Regel der [Qualitätsskala für Home-Assistant-Integrationen](https://developers.home-assistant.io/docs/core/integration-quality-scale/) bis Platin ([Selbstbewertung](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/custom_components/homedarts/quality_scale.yaml)), einschließlich strikter Typisierung.
- 100 % Zeilen- und Zweigabdeckung der Integration, Fuzz-Tests der Karten, ein Docker-End-to-End-Test gegen beide Board-Manager-Generationen und das älteste unterstützte Home Assistant, ein echter Browsertest jeder Karte und wöchentliche [Mutationstests](https://dennis-otto.github.io/homedarts-for-autodarts/de/development.html#mutationstests) der Spielregeln. [Entwicklung](https://dennis-otto.github.io/homedarts-for-autodarts/development.html) (englisch).
- Signierte Release-Pakete mit SLSA-Herkunftsnachweis. [Releases](https://dennis-otto.github.io/homedarts-for-autodarts/de/releases.html#signed-release-packages) (englisch).
- CI-Jobs, die nur die Hosts erreichen, die sie brauchen: Harden-Runner sperrt jeden anderen, die Bots, die schreiben dürfen, erreichen nur GitHub, und das getestete Home Assistant bleibt offline. [Netzwerk der Jobs](https://dennis-otto.github.io/homedarts-for-autodarts/de/development.html#netzwerk-der-jobs).

## Herkunft und Lizenz

HomeDarts begann als Fork von [Trkal/HACSAutodarts](https://github.com/Trkal/HACSAutodarts), einem cloudbasierten Prototyp vom April 2026. Seit September 2026 ist es neu geschrieben und wird unabhängig von [@Dennis-Otto](https://github.com/Dennis-Otto) gepflegt: lokale Echtzeitsteuerung für beide Board-Manager-Generationen, Spiele, Trainingsauswertung, Dashboard-Karten, Blueprints, Tests und Dokumentation. Bis Version 1.18 hieß es Autodarts und teilte die Domain `autodarts` mit dem Original; seit 2.0 hat es die Domain `homedarts`, deshalb können beide nebeneinander installiert sein, und die [Installationsanleitung](https://dennis-otto.github.io/homedarts-for-autodarts/de/installation.html#von-der-ursprünglichen-integration-umsteigen) erklärt den Wechsel. Danke an Trkal für die ursprüngliche Arbeit und an das Autodarts-Team für seine offene lokale Schnittstelle.

Lizenziert unter der [MIT-Lizenz](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/LICENSE). Sie gilt auch für das Symbol. Die Namen Autodarts und Winmau gehören ihren Inhabern. HomeDarts for Autodarts ist ein inoffizielles Community-Projekt ohne Verbindung zu Autodarts.
