---
description: "Fakten, die Geschichte, Bilder und Videos von HomeDarts for Autodarts, frei nutzbar für YouTuber, Streamer und Blogger."
---

# Creator-Kit

[← Dokumentation](README.de.md) · [English](creator-kit.md)

Für YouTuber, Streamer, Blogger und alle, die HomeDarts for Autodarts zeigen möchten, die Integration für Autodarts-Boards und jede Dartscheibe in Home Assistant. Alles auf dieser Seite darfst du frei in Videos, Artikeln und Beiträgen über die Integration verwenden; fragen musst du nicht.

<img src="images/de/hero.webp" alt="Animation: ein 301-Match auf der Live-Karte und der Anzeigetafel nebeneinander. Alex wirft drei Triple 20, die Felder leuchten auf und die Anzeigetafel zählt auf 121 herunter; Sam wirft 85; Alex checkt 121 mit T20, Single-Bull und D18 zum Game shot" width="760">

**Auf dieser Seite:** [Kurz gesagt](#kurz-gesagt) · [Fakten](#fakten) · [Die Geschichte](#die-geschichte) · [Ohne Board ausprobieren](#ohne-board-ausprobieren) · [Videos und Animationen](#videos-und-animationen) · [Bilder](#bilder) · [Deine Spiele streamen](#deine-spiele-streamen) · [So nennst du sie](#so-nennst-du-sie) · [Beiträge zum Start](#beiträge-zum-start) · [Kontakt](#kontakt)

## Kurz gesagt

Ein Satz:

```text
Dein Autodarts-Board wird Teil deines Smart Homes: Anzeigetafel auf jedem Tablet, Licht-Show beim 180er, Bot, Turniere und Statistik. Lokal, ohne Cloud, kostenlos.
```

Eine kurze Beschreibung:

```text
HomeDarts for Autodarts ist eine kostenlose Open-Source-Integration, die ein Autodarts-Board in Echtzeit mit Home Assistant verbindet, lokal und ohne Konto. Sie bringt eine Anzeigetafel für das Tablet am Board, X01, Cricket, Party- und Trainingsspiele, einen Bot, Turniere, Spielerstatistik mit Trefferbildern und Ereignisse für eigene Automationen, etwa Licht, das beim 180er aufblitzt.
```

## Fakten

| Thema | Fakt |
| --- | --- |
| Name | HomeDarts for Autodarts, kurz HomeDarts (`homedarts-for-autodarts`) |
| Früherer Name | Autodarts, bis Version 1.18; Autodarts hat um einen eigenen Namen gebeten ([Von Autodarts zu HomeDarts](new-name.de.md)) |
| Preis | Kostenlos, Open Source unter der MIT-Lizenz |
| Verbindung | Lokal und in Echtzeit mit dem Board Manager auf dem Board-PC; kein Autodarts-Konto, keine Cloud |
| Spiele | X01 von 101 bis 1001, sechs Cricket-Spiele, neun Partyspiele und acht Trainingsspiele |
| Spielen | Bis zu vier Spieler oder zwei Teams zu zweit, Handicap-Startpunkte, ein Bot von Stufe 20 bis 120, Turniere für drei bis 32 Spieler |
| Anzeigetafel | Eine Vollbild-Ansicht für Tablet oder Fernseher, mit Spielauswahl, Korrekturen, Caller und Ruhemodus |
| Statistik | Bestleistungen, Trefferbilder der echten Dart-Positionen, Trends, Erfolge, Bestenliste, Wochenbericht und Exporte |
| Zuhause | Sieben Dashboard-Karten, ein automatisches Dashboard und sechzehn Blueprints, etwa eine Licht-Show beim 180er |
| Sprachen | Englisch, Deutsch, Niederländisch, Französisch und Spanisch |
| Qualität | 100 % Testabdeckung, in Docker gegen beide Board-Manager-Generationen getestet; alle Regeln der Home-Assistant-Qualitätsskala bis Platin (Selbsteinschätzung) |
| Voraussetzungen | Home Assistant ab 2026.8 mit HACS; die getesteten Setups stehen unter [Unterstützte Geräte](README.de.md#unterstützte-geräte) |
| Online-Matches | Eine experimentelle Brücke über Tools for Autodarts bringt Überwerfen, gewonnene Legs und die Darts deiner Gegner als Ereignisse herein |

## Die Geschichte

```text
Ich spiele selbst auf einem Autodarts-Board. Ich wollte es in Home Assistant haben, habe lange nach einer vollständigen Lösung gesucht und keine gefunden. Also habe ich in meiner Freizeit selbst eine geschrieben. Von der Community, für die Community: Ich entwickle sie ständig weiter, und die Rückmeldungen echter Spieler entscheiden, was als Nächstes kommt. – Dennis Otto
```

## Ohne Board ausprobieren

Am schnellsten geht es mit der [Live-Demo](https://dennis-otto.github.io/homedarts-for-autodarts/demo/index.html?lang=de): Die Karten spielen ein 501 gegen den Bot, ein Cricket-Spiel und ein Turnier direkt im Browser, auch auf dem Handy und in allen fünf Sprachen, ohne dass du etwas installierst. Teile ihren Link; `?lang=de`, `nl`, `fr` oder `es` am Ende öffnet sie in dieser Sprache.

Für das ganze Home Assistant startest du die Demo mit simuliertem Board und erfundenen Spielern: Sie zeigt alle Karten, die Anzeigetafel und eine Trainingshistorie. Du brauchst Docker und Git; unter Windows startest du sie in der Git Bash.

```sh
git clone https://github.com/Dennis-Otto/homedarts-for-autodarts.git
cd homedarts-for-autodarts
DEMO_LANGUAGE=de bash tests/e2e/demo.sh
```

Öffne <http://127.0.0.1:18124/homedarts-demo/board>; vom eigenen Rechner aus ist keine Anmeldung nötig. Ohne `DEMO_LANGUAGE=de` startet die Demo auf Englisch. Das Skript zeigt am Ende den Befehl, der sie wieder stoppt. Mehr dazu in der [Entwickler-Dokumentation](development.md#demo-instance-and-browser-test), auf Englisch.

## Videos und Animationen

In der Demo mit simuliertem Board aufgenommen. MP4 funktioniert in Schnittprogrammen, auf Reddit und in Discord; GIF funktioniert in jedem Forum.

| Szene | Deutsch | Englisch |
| --- | --- | --- |
| Ein 301-Match auf der Live-Karte und der Anzeigetafel | [MP4](media/hero-de.mp4) · [GIF](media/hero-de.gif) | [MP4](media/hero-en.mp4) · [GIF](media/hero-en.gif) |
| Die Anzeigetafel in einem 501-Match | [MP4](media/scoreboard-de.mp4) · [GIF](media/scoreboard-de.gif) | [MP4](media/scoreboard-en.mp4) · [GIF](media/scoreboard-en.gif) |
| Konfetti für eine 180 auf der Anzeigetafel | [MP4](media/celebration-de.mp4) · [GIF](media/celebration-de.gif) | [MP4](media/celebration-en.mp4) · [GIF](media/celebration-en.gif) |
| Wild Mouse mit Doubles, Triples und Three in a Bed | [MP4](media/wild-mouse-de.mp4) · [GIF](media/wild-mouse-de.gif) | [MP4](media/wild-mouse-en.mp4) · [GIF](media/wild-mouse-en.gif) |
| Die Einrichtung, vom entdeckten Board bis zur Anzeigetafel | [MP4](media/setup-de.mp4) · [GIF](media/setup-de.gif) | [MP4](media/setup-en.mp4) · [GIF](media/setup-en.gif) |
| Ein Match gegen den Bot | [MP4](media/bot-match-de.mp4) · [GIF](media/bot-match-de.gif) | [MP4](media/bot-match-en.mp4) · [GIF](media/bot-match-en.gif) |
| Das nächste Spiel auf dem Tablet wählen | [MP4](media/lobby-de.mp4) · [GIF](media/lobby-de.gif) | [MP4](media/lobby-en.mp4) · [GIF](media/lobby-en.gif) |
| Ein Turnier mit Turnierbaum | [MP4](media/tournament-bracket-de.mp4) · [GIF](media/tournament-bracket-de.gif) | [MP4](media/tournament-bracket-en.mp4) · [GIF](media/tournament-bracket-en.gif) |

## Bilder

Alle Screenshots der Dokumentation liegen in [`docs/images/de`](https://github.com/Dennis-Otto/homedarts-for-autodarts/tree/main/docs/images/de) und [`docs/images/en`](https://github.com/Dennis-Otto/homedarts-for-autodarts/tree/main/docs/images/en), alle in der Demo aufgenommen. Einige, die die Integration auf einen Blick zeigen:

| Auf der Anzeigetafel | In Home Assistant |
| --- | --- |
| <img src="images/de/scoreboard-lobby.png" alt="Die Spielauswahl auf einem Tablet im Querformat: die Spiele nach Gruppen mit 501 gewählt, Alex und Sam mit ihren Bildern, Sam ab 301, drei Legs pro Satz, Double-Out und die Start-Taste" width="100%"> | <img src="images/de/players-card.png" alt="Spielerkarte mit den Profilen von Alex, Sam und Kim mit ihren Bildern, ihren Averages und Bestleistungen, den direkten Vergleichen der Spieler und den letzten Matches" width="100%"> |
| <img src="images/de/match-summary.png" alt="Anzeigetafel, nachdem Alex Sam in 301 mit 2 : 1 geschlagen hat: die Match-Zusammenfassung mit Legs, 3-Dart-Average, First 9, Checkout-Quote, höchstem Checkout, 180ern, 140+, 100+, bestem Leg, Darts aufs Double und Darts beider Spieler" width="100%"> | <img src="images/de/blueprints.png" alt="Die Blueprint-Seite von Home Assistant mit den sechzehn HomeDarts-Blueprints, von den Fragen an Assist zu deinen Darts bis zum Wochenbericht, und ihren Dateinamen" width="100%"> |

## Deine Spiele streamen

Du spielst im Stream? Die Anzeigetafel ist ein Overlay für OBS Studio, Streamlabs und jede andere Software mit einer Browserquelle: Punkte, Checkout-Weg und die Darts der Aufnahme am unteren Rand deines Bildes, in seiner Ecke oben links oder über das ganze Bild, durchsichtig oder auf einer Keyfarbe. Es füllt das Fenster von selbst und zeigt zwischen den Spielen nichts. Das Highlight-Foto nimmt jede 180 und jeden großen Checkout auch als Clip auf, ab ein paar Sekunden vor dem Dart, bereit zum Schneiden.

<img src="images/de/scoreboard-overlay.png" alt="Das Stream-Overlay am unteren Rand des Bildes vom Board: Übungsspiel 501, Alex am Board mit dem Weg T20 D12, Sam, und daneben die Darts der Aufnahme" width="760">

- [Das Stream-Overlay einrichten](scoreboard.de.md#stream-overlay): ein Benutzer für OBS, die Ansicht `…/overlay` des automatischen Dashboards und eine Browserquelle mit 1920 × 1080.
- [Clips deiner Highlights aufnehmen](automations.de.md#highlight-clips) mit der Kamera deines Streams.

## So nennst du sie

- Nenne sie **HomeDarts for Autodarts**, kurz **HomeDarts**, und verlinke <https://github.com/Dennis-Otto/homedarts-for-autodarts>. Bis Version 1.18 hieß sie Autodarts; bitte nutze diesen Namen nicht mehr für sie.
- Sag dazu, dass es ein **inoffizielles Community-Projekt** ist, ohne Verbindung zu Autodarts. Namen und Logos von Autodarts und Winmau gehören ihren Inhabern; bitte nutze sie nicht so, dass es nach einer Empfehlung aussieht, etwa in einem Vorschaubild. Das Projekt trägt kein Logo von Autodarts; sein eigenes Symbol, [ein Haus mit Dartscheibe](branding/icon.svg), darfst du frei zeigen.
- In Hashtags und Suchwörtern nennt *HomeDarts* das Projekt und *Autodarts* die Boards, mit denen es arbeitet, etwa `#HomeDarts #Autodarts #HomeAssistant`.
- Autodarts unterstützt die lokale Schnittstelle des Board Managers ab Version 2 nicht mehr offiziell. Die Integration funktioniert weiterhin damit; unter [Unterstützte Geräte](README.de.md#unterstützte-geräte) steht, was getestet ist.

## Beiträge zum Start

Fertige Texte für die Orte, an denen sich Home-Assistant-Nutzer und Autodarts-Spieler treffen. Der Maintainer veröffentlicht sie; wer die Integration selbst teilt, darf sich gern daraus bedienen, mit „ich nutze“ statt „ich habe gebaut“. Die Kopier-Schaltfläche eines Textes übernimmt ihn unverändert, mit seinem Markdown.

Jeder Text bleibt unter 300 Wörtern und führt seine Leser denselben Weg: die Live-Demo, um die Karten auszuprobieren, den Vergleich, um zu sehen, was sich ändert, die Schaltfläche, die das Repository in HACS öffnet, und *Show and tell*, um danach das eigene Board zu zeigen.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/de/launch-posts-dark.png">
  <img src="images/de/launch-posts-light.png" alt="Wohin ein Beitrag zum Start seine Leser führt: Ein Beitrag im Home-Assistant-Forum, auf Reddit oder auf Discord zeigt die Animation eines Matches und drei Punkte. Seine Links führen zur Live-Demo, in der die Karten im Browser spielen, und zum Vergleich mit den anderen Werkzeugen, der zeigt, was sie ersetzt und was bleiben kann. Die Schaltfläche öffnet das Repository in HACS, und der Leser fügt das Board in Home Assistant hinzu. Ein Foto unter Show and tell zeigt das Board dann den nächsten Lesern" width="420">
</picture>

Die Texte für das Home-Assistant-Forum und Reddit sind englisch, weil ihr Publikum englisch liest; sie stehen auf der [englischen Seite](creator-kit.md#launch-posts).

| Wo | Sprache | Anhang |
| --- | --- | --- |
| [Deutschsprachige Foren und Gruppen](#deutschsprachige-foren) | Deutsch | Nichts: Der Beitrag zeigt die [Animation](media/hero-de.gif) |
| [Autodarts-Discord](#autodarts-discord) | Deutsch | Das [Video](media/hero-de.mp4) |
| [Tools for Autodarts und darts-hub](#tools-for-autodarts-und-darts-hub) | Deutsch | Nichts |
| [Home-Assistant-Forum](creator-kit.md#home-assistant-forum) | Englisch | Nichts: Der Beitrag zeigt die [Animation](media/hero-en.gif) |
| [r/homeassistant](creator-kit.md#rhomeassistant) | Englisch | Das [Video](media/hero-en.mp4) |
| [r/Darts](creator-kit.md#rdarts) | Englisch | Das [Video](media/hero-en.mp4) |
| [Autodarts-Discord, auf Englisch](creator-kit.md#autodarts-discord) | Englisch | Das [Video](media/hero-en.mp4) |
| [Tools for Autodarts und darts-hub, auf Englisch](creator-kit.md#tools-for-autodarts-and-darts-hub) | Englisch | Nichts |

Vor dem Posten:

- Lies die Regeln des Ortes: Manche wollen ein Flair oder einen wöchentlichen Thread für Projekte, und alle wollen, dass du dich am Gespräch beteiligst.
- Poste an einem Ort pro Tag statt überall auf einmal, und beantworte die Kommentare. Eine Frage, die zweimal kommt, gehört in die [häufigen Fragen](faq.de.md).
- Trag jeden Beitrag unter [Reichweite](roadmap.de.md#reichweite) in der Roadmap ein, damit sich die Zahlen dort daran messen lassen.

### Deutschsprachige Foren

Für deutschsprachige Home-Assistant-Foren und -Gruppen, in der Kategorie für eigene Projekte. Die Animation in der ersten Zeile zeigt sich im Beitrag; wo das Forum keine Bilder von anderen Adressen zeigt, lädst du das [Video](media/hero-de.mp4) hoch.

```text title="Titel"
HomeDarts for Autodarts: dein Dartboard im Smart Home, mit Anzeigetafel, Bot und Licht-Show bei jedem 180er, lokal und kostenlos
```

```markdown title="Beitrag"
![Ein 301-Match auf der Live-Karte und der Anzeigetafel von HomeDarts for Autodarts](https://raw.githubusercontent.com/Dennis-Otto/homedarts-for-autodarts/main/docs/media/hero-de.gif)

Ich spiele an einem Autodarts-Board und wollte das ganze Spiel in Home Assistant haben, nicht nur die letzte Punktzahl. Eine vollständige Lösung habe ich nicht gefunden, also habe ich in meiner Freizeit eine gebaut: **HomeDarts for Autodarts**, kostenlos und Open Source unter der MIT-Lizenz.

- **Lokal und in Echtzeit.** Die Integration spricht mit dem Board Manager auf dem Board-PC in deinem Netzwerk: kein Autodarts-Konto, keine Cloud, nichts verlässt dein Zuhause.
- **Ein Dartautomat für zu Hause.** X01, sechs Cricket-Spiele, neun Party- und acht Trainingsspiele, ein Bot von Stufe 20 bis 120 und Turniere, auf einer Anzeigetafel im Vollbild für Tablet oder Fernseher, mit Caller.
- **Jeder Dart für deine Automationen.** Ereignisse für jeden Dart, jede Aufnahme, jedes Überwerfen, Leg und Match, sieben Dashboard-Karten und sechzehn Blueprints, von der Licht-Show beim 180er bis zum Wochenbericht. Die Statistik mit Trefferbildern bleibt in deinem Home Assistant.

**Erst ausprobieren:** Die [Live-Demo](https://dennis-otto.github.io/homedarts-for-autodarts/demo/index.html?lang=de) spielt die Karten in deinem Browser, ganz ohne Installation. Kein Autodarts-Board? Sie zählt auch Darts, die du auf einem Tastenfeld eingibst.

**Installieren:** Home Assistant ab 2026.8 mit HACS, dann [das Repository in HACS öffnen](https://my.home-assistant.io/redirect/hacs_repository/?owner=Dennis-Otto&repository=homedarts-for-autodarts&category=integration). Du nutzt schon eine andere Autodarts-Integration, darts-caller oder eine MQTT-Brücke? [Umstieg von anderen Werkzeugen](https://dennis-otto.github.io/homedarts-for-autodarts/de/coming-from.html) zeigt, was sie ersetzt und was bleiben kann.

[Anleitung](https://dennis-otto.github.io/homedarts-for-autodarts/de/) auf Deutsch und Englisch · [GitHub](https://github.com/Dennis-Otto/homedarts-for-autodarts) · Ein inoffizielles Community-Projekt, ohne Verbindung zu Autodarts.

Rückmeldungen von echten Boards entscheiden, was als Nächstes kommt. Und wenn sie bei dir läuft: [Zeig dein Board](https://github.com/Dennis-Otto/homedarts-for-autodarts/discussions/new?category=show-and-tell)!
```

### Autodarts-Discord

Im Kanal des Autodarts-Discords, in dem Mitglieder ihre eigenen Projekte zeigen, zusammen mit dem hochgeladenen [Video](media/hero-de.mp4). Die spitzen Klammern halten Discord davon ab, unter jeden Link eine Vorschau zu setzen. Die englische Nachricht steht auf der [englischen Seite](creator-kit.md#autodarts-discord).

```markdown title="Nachricht"
**HomeDarts for Autodarts**: Ich habe eine kostenlose Open-Source-Integration gebaut, die das Board in Home Assistant bringt, lokal und in Echtzeit, ohne Autodarts-Konto.

- Eine Anzeigetafel im Vollbild für Tablet oder Fernseher mit Caller: X01, Cricket, Party- und Trainingsspiele, ein Bot und Turniere
- Ein Ereignis für jeden Dart, jedes Überwerfen, Leg und Match: Licht-Show beim 180er, ein Foto nach dem Checkout, Spiele per Sprache starten
- Statistik mit Trefferbildern deiner echten Dart-Positionen, die bei dir zu Hause bleibt

Die Karten im Browser ausprobieren: <https://dennis-otto.github.io/homedarts-for-autodarts/demo/index.html?lang=de>
In HACS öffnen: <https://my.home-assistant.io/redirect/hacs_repository/?owner=Dennis-Otto&repository=homedarts-for-autodarts&category=integration>
Umstieg von anderen Werkzeugen: <https://dennis-otto.github.io/homedarts-for-autodarts/de/coming-from.html>
Zeig dein Board: <https://github.com/Dennis-Otto/homedarts-for-autodarts/discussions/new?category=show-and-tell>

Ein inoffizielles Community-Projekt, ohne Verbindung zu Autodarts. Rückmeldungen sind willkommen, hier oder auf GitHub!
```

### Tools for Autodarts und darts-hub

Zwei Sätze und ein Link für die Discord-Server, Gruppen und Diskussionen von [Tools for Autodarts](https://github.com/creazy231/tools-for-autodarts) und von [darts-hub](https://github.com/lbormann/darts-hub) mit darts-caller, neben deren Nutzern die Integration läuft.

```text title="Tools for Autodarts"
Du nutzt Tools for Autodarts und Home Assistant? HomeDarts for Autodarts macht aus der WLED-Funktion von Tools Ereignisse in Home Assistant für Online-Matches, etwa Überwerfen, gewonnene Legs und die Darts deiner Gegner, für Licht, einen Caller oder eine Benachrichtigung (experimentell): https://dennis-otto.github.io/homedarts-for-autodarts/de/online-matches.html
```

```text title="darts-hub"
Du nutzt darts-caller oder darts-wled mit darts-hub? HomeDarts for Autodarts kann direkt daneben laufen: Die Integration liest das Board lokal und bringt jeden Dart, jedes Überwerfen und jedes Leg in Home Assistant, für deine eigenen Automationen: https://dennis-otto.github.io/homedarts-for-autodarts/de/coming-from.html#darts-caller-und-darts-wled
```

## Kontakt

Fragen und Ideen gehören in die [GitHub Discussions](https://github.com/Dennis-Otto/homedarts-for-autodarts/discussions), damit jede Antwort allen hilft; Deutsch und Englisch sind willkommen. Du hast ein Video oder einen Artikel gemacht? Teile ihn unter [Show and tell](https://github.com/Dennis-Otto/homedarts-for-autodarts/discussions/categories/show-and-tell), dann verlinken wir ihn in der Dokumentation.
