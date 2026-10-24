---
description: "HomeDarts for Autodarts bringt jeden Dart nach Home Assistant: Spiele, eine Anzeigetafel, Statistik und Automationen. Lokal und kostenlos, ohne Cloud-Konto."
hide:
  - navigation
  - toc
# The headline of the preview card of a shared link, under the name of the website
# (in one line, which markdownlint doesn't take for the title of the page).
social: { cards_layout_options: { title: "Dein Autodarts-Board live in Home Assistant" } }
---

# HomeDarts for Autodarts

![Das Symbol der Integration: ein Haus mit Dartscheibe](branding/icon.svg){ width="96" align="right" }

**Dein Autodarts-Board live in Home Assistant: lokal, in Echtzeit und bereit für Automationen.**

HomeDarts for Autodarts bringt dein Autodarts-Board nach Home Assistant: Darts erscheinen Sekundenbruchteile, nachdem sie landen, direkt vom Board Manager in deinem Netzwerk. Jede andere Dartscheibe spielt auch mit, ihre Darts von Hand eingegeben oder von einem Granboard gesendet. Spiele und trainiere damit, stell eine Anzeigetafel neben das Board, verfolge deine Statistik und lass dein Zuhause mitspielen. Kein Konto, keine Cloud, keine Client-ID.

HomeDarts for Autodarts ist ein inoffizielles Community-Projekt ohne Verbindung zu Autodarts. Bis Version 1.18 hieß es Autodarts: [Von Autodarts zu HomeDarts](new-name.de.md) erklärt den neuen Namen und wie HomeDarts deine Boards übernimmt.

[:material-download: Mit HACS installieren](https://my.home-assistant.io/redirect/hacs_repository/?owner=Dennis-Otto&repository=homedarts-for-autodarts&category=integration){ .md-button .md-button--primary } [:material-rocket-launch: Erste Schritte](getting-started.de.md){ .md-button } <a href="demo/index.html?lang=de" class="md-button">:material-play-circle: Live ausprobieren</a>

<picture>
  <source media="(max-width: 600px)" srcset="images/de/hero-mobile.webp">
  <img class="off-glb" src="images/de/hero.webp" alt="Animation: ein 301-Match auf der Live-Karte und der Anzeigetafel. Alex wirft drei Triple 20, die Felder leuchten auf und die Anzeigetafel zählt auf 121 herunter; Sam wirft 85; Alex checkt 121 mit T20, Single-Bull und D18 zum Game shot">
</picture>

## Das kann die Integration

<div class="grid cards pictures" markdown>

- ![Die Live-Karte im Dashboard von Home Assistant: die aktuelle Aufnahme, ihre drei Darts, die letzten Aufnahmen, die Trainingssession und das Board](images/de/dashboard-live.png){ loading=lazy }

    :material-lan-connect:{ .lg .middle } **Lokal und in Echtzeit**

    ---

    Mit Board Manager 2 automatisch gefunden; Board Manager 1 funktioniert auch. Nichts verlässt dein Netzwerk, außer du nutzt die Board-Suche oder die Online-Brücke, und Geheimnisse des Boards werden nie gespeichert.

    [:octicons-arrow-right-24: Funktionsweise](how-it-works.de.md)

- ![Animation: eine 180 auf der Anzeigetafel, mit goldenem Leuchten und Konfetti](images/de/celebration.webp){ loading=lazy }

    :material-bullseye-arrow:{ .lg .middle } **Spiele**

    ---

    X01 von 101 bis 1001 mit dem Checkout-Weg nach jedem Dart, Cricket, Cut-Throat Cricket, Tactics, Wild Mouse, Random und Hidden Cricket und neun Partyspiele für bis zu acht, allein oder als Match mit bis zu vier Spielern, mit Legs, Sätzen, Teams und Handicap.

    [:octicons-arrow-right-24: Spiele und Regeln](games.de.md)

- ![Animation: Around the Clock auf der Live-Karte; jeder Treffer bringt das Ziel weiter und umrandet die Felder der nächsten Zahl](images/de/training-game.webp){ loading=lazy }

    :material-target:{ .lg .middle } **Training**

    ---

    Trainingssessions, die mit dem ersten Dart beginnen, acht Trainingsspiele von Around the Clock bis zur JDC Challenge, ein Tagesziel, eine Trainingsserie und Bestleistungen.

    [:octicons-arrow-right-24: Trainingsspiele](games.de.md#trainingsspiele)

- ![Animation: Auf dem Tablet am Board wird in der Spielauswahl ein Spiel gewählt, und es startet auf der Anzeigetafel](images/de/lobby.webp){ loading=lazy }

    :material-monitor-dashboard:{ .lg .middle } **Anzeigetafel und Karten**

    ---

    Eine Anzeigetafel für Tablet oder Fernseher, auch über Chromecast, lesbar vom Abwurf aus, mit Spielauswahl, Caller und Ruhemodus. Sieben Dashboard-Karten und ein automatisches Dashboard, auf Deutsch, Englisch, Niederländisch, Französisch und Spanisch.

    [:octicons-arrow-right-24: Anzeigetafel am Board](scoreboard.de.md) · [Dashboard-Karten](cards.de.md)

- ![Animation: Das Trefferbild wechselt von Feldern zu Zahlen und den echten Dart-Positionen, dann zu den Darts eines Spielers](images/de/heatmap-modes.webp){ loading=lazy }

    :material-chart-line:{ .lg .middle } **Statistik mit Trefferbildern**

    ---

    3-Dart-Average, First-9-Average, Checkout- und Doppelquote, ein Trefferbild jedes Feldes oder der echten Dart-Positionen und wohin jeder Spieler für die meisten Punkte pro Dart zielt. Spielerprofile mit Abzeichen, Wochentrends, eine Bestenliste, ein Wochenbericht und ein Trainingskalender.

    [:octicons-arrow-right-24: Statistik und Spieler](statistics.de.md)

- ![Die Highlight-Galerie in der Medienansicht von Home Assistant: Fotos eines 121er-Checkouts, einer 180 und einer 140](images/de/media-gallery.png){ loading=lazy }

    :material-home-automation:{ .lg .middle } **Automationen und Blueprints**

    ---

    Board-Ereignisse für jeden Dart, jede Aufnahme, Entnahme, jedes Überwerfen, gewonnene Leg und Match, Beginn und Ende jedes Spiels. Sechzehn Blueprints: Lichtshow, Walk-on-Musik, Spielstand-Anzeige, Dart- und Übungs-Caller, Highlight-Fotos, Berichte, Warnungen, Routinen, Spielstart und Darts per Sprache sowie Antworten von Assist zu deinen Darts.

    [:octicons-arrow-right-24: Automationen](automations.de.md)

- ![Animation: der Turnierbaum mit fünf Spielern auf der Anzeigetafel; die Sieger rücken in die nächste Runde, bis Alex das Finale gewinnt](images/de/tournament-bracket.webp){ loading=lazy }

    :material-tournament:{ .lg .middle } **Turniere und ein Bot**

    ---

    Turniere mit drei bis 32 Spielern, jeder gegen jeden mit Tabelle, im K.-o.-System, im Doppel-K.-o.-System oder in Gruppen mit K.-o.-System, an einem Board oder auf mehreren Boards zugleich, und ein Bot mit Stärke 20 bis 120 als Gegner bei X01 und Cricket.

    [:octicons-arrow-right-24: Turniere](games.de.md#turniere) · [Der Bot](games.de.md#gegen-den-bot-spielen)

- ![Animation: Darts per Sprache eingegeben, mit Assist über der Anzeigetafel, der mit dem Rest antwortet](images/de/manual-voice.webp){ loading=lazy }

    :material-microphone:{ .lg .middle } **Sprache**

    ---

    Sag Assist „Starte 501 für Alex und Sam“, auf Deutsch, Englisch, Spanisch, Französisch oder Niederländisch, und das Spiel beginnt; dann gibt „Alex hat 140“ oder „Triple 20“ die Darts ein, wie am Dartautomaten, und „Wie ist mein Schnitt heute?“ beantworten die Statistiken des Boards. Jedes Spiel startet auch mit einer Aktion einer Automation.

    [:octicons-arrow-right-24: Spiel per Sprache starten](automations.de.md#spiel-per-sprache-starten)

    [:octicons-arrow-right-24: Darts per Sprache eingeben](automations.de.md#enter-darts-by-voice)

    [:octicons-arrow-right-24: Assist nach deinen Darts fragen](automations.de.md#ask-assist-about-your-darts)

</div>

## Vom Dart in dein Zuhause

Alles geschieht in deinem Netzwerk, in weniger als einer Sekunde: Der Board Manager bestimmt das Feld, und Home Assistant zeigt es auf den Karten und gibt es an deine Automationen weiter.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/de/dart-journey-dark.png">
  <img src="images/de/dart-journey-light.png" alt="Der Weg eines Darts: Ein Dart landet in der Triple 20. Die Kameras des Boards sehen ihn, und der Board Manager auf dem Board-PC bestimmt das Feld. Eine Echtzeitnachricht bringt es durch dein Netzwerk zu HomeDarts in Home Assistant; die Integration aktualisiert die Entitäten, sendet die Board-Ereignisse und lässt das Feld auf den Karten und der Anzeigetafel aufleuchten. Deine Automation reagiert auf die Ereignisse, etwa mit blinkendem Licht bei einer 180 oder einem Caller. Das alles dauert weniger als eine Sekunde und braucht keine Cloud" width="560">
</picture>

[:octicons-arrow-right-24: Funktionsweise](how-it-works.de.md)

## Im Vergleich

Wie sich HomeDarts mit der Autodarts-App und ihrer Browser-Erweiterung, mit darts-caller und darts-wled und mit den anderen Home-Assistant-Integrationen für Autodarts vergleicht. [Umstieg von anderen Werkzeugen](coming-from.de.md) zeigt, wie du umsteigst.

--8<-- "docs/coming-from.de.md:compare"

*Stand Oktober 2026, aus der Dokumentation und dem Code jedes Projekts. [Umstieg von anderen Werkzeugen](coming-from.de.md) hat die Einzelheiten und die Quellen.*

## Anleitungen

- :material-rocket-launch: [**Von null bis zur Anzeigetafel**](getting-started.de.md): Home Assistant, HACS, die Integration und das erste Spiel, für Autodarts-Spieler, die Home Assistant noch nicht haben
- :material-download: [**Installation und Einrichtung**](installation.de.md): Voraussetzungen, HACS oder von Hand, die Wege, ein Board hinzuzufügen, Updates und Entfernen
- :material-pencil: [**Spielen ohne Autodarts**](without-autodarts.de.md): jede Dartscheibe, mit allen Spielen, dem Training und der Statistik, die Darts auf einem Tastenfeld eingegeben
- :material-bluetooth: [**Granboard über Bluetooth**](granboard.de.md): die Darts eines Granboards über das Bluetooth von Home Assistant und ESPHome-Proxys *(experimentell)*
- :material-frequently-asked-questions: [**Häufige Fragen**](faq.de.md): Konto, Geräte, Online-Spiel, Datenschutz, mehrere Boards, Bildschirme, Sprachen und Updates
- :material-swap-horizontal: [**Umstieg von anderen Werkzeugen**](coming-from.de.md): die anderen Integrationen, MQTT-Brücken, darts-caller, darts-wled und Tools for Autodarts im Vergleich, und wie du umsteigst
- :material-rename-box: [**Von Autodarts zu HomeDarts**](new-name.de.md): der neue Name seit Version 2.0, und wie HomeDarts deine Boards übernimmt
- :material-bullseye-arrow: [**Spiele und Regeln**](games.de.md): alle Spiele im Überblick, vier Wege, eines zu starten, Matches, Teams, Handicaps, das Ausbullen und Turniere
- :material-television: [**Anzeigetafel am Board**](scoreboard.de.md): ein Tablet oder Fernseher neben dem Board, Quer- und Hochformat, Spielauswahl, Caller und Ruhemodus
- :material-chart-line: [**Statistik und Spieler**](statistics.de.md): Sessions, Bestleistungen, Trefferbilder, wohin zielen, Fortschritt, Profile, Erfolge und Bestenliste
- :material-home-automation: [**Automationen**](automations.de.md): sechzehn Blueprints, ihre Einstellungen, Board-Ereignisse und fertige Beispiele
- :material-play-network: [**Online-Matches**](online-matches.de.md): Überwerfen, gewonnene Legs und Matches von Online-Matches als Board-Ereignisse, mit Tools for Autodarts *(experimentell)*

## Nachschlagen

<div class="grid cards" markdown>

- :material-view-dashboard:{ .lg .middle } [**Dashboard-Karten**](cards.de.md)

    ---

    Alle sieben Karten und das automatische Dashboard, mit allen Optionen und Barrierefreiheit.

- :material-format-list-bulleted:{ .lg .middle } [**Entitäten und Ereignisse**](entities.de.md)

    ---

    Alle Entitäten, Board-Ereignisse, Zustände, Attribute und Aktionen, und welche Board-Manager-Generation sie liefert.

- :material-cog-transfer:{ .lg .middle } [**Funktionsweise**](how-it-works.de.md)

    ---

    Architektur, Aktualisierung, Verbindungsverhalten, Training und Bestleistungen, gespeicherte Daten und Datenschutz.

- :material-lifebuoy:{ .lg .middle } [**Fehlerbehebung**](troubleshooting.de.md)

    ---

    Meldungen bei der Einrichtung, Reparaturen, nicht verfügbare Entitäten, fehlgeschlagene Aktionen, Diagnose und Logs.

- :material-shield-lock:{ .lg .middle } [**Sicherheit**](security.de.md)

    ---

    Schutzgüter, Vertrauensgrenzen, Bedrohungen und Gegenmaßnahmen.

- :material-book-alphabet:{ .lg .middle } [**Glossar**](glossary.de.md)

    ---

    Die Begriffe des Dartsports und dieser Integration, mit ihren englischen Entsprechungen.

</div>

Was jede Version gebracht hat, steht in den [Änderungen](changelog.md) (auf Englisch), was als Nächstes kommt, in der [Roadmap](roadmap.de.md). Für Videos, Artikel und Beiträge hat das [Creator-Kit](creator-kit.de.md) Fakten, fertige Texte, Videos und Bilder, frei nutzbar.

--8<-- "docs/README.de.md:devices-and-languages"
