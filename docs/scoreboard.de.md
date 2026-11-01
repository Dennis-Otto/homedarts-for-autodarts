---
description: "Eine Anzeigetafel auf Tablet oder Fernseher neben dem Board: der Rest vom Abwurf lesbar, Checkout-Wege, ein Caller, Turniere und eine Bestenliste."
---

# Anzeigetafel am Board

[← Dokumentation](README.de.md) · [English](scoreboard.md)

Ein Tablet oder Fernseher neben dem Board macht deinen Dartraum zur Bühne: der Rest groß genug, um ihn vom Abwurf zu lesen, der Checkout-Weg des Spielers am Board, das nächste Spiel oder ein ganzes Turnier direkt dort gewählt, ein Caller und zwischen den Spielen eine Bestenliste. Alles läuft in Home Assistant; der Bildschirm braucht nur einen Browser.

<img src="images/de/scoreboard.webp" alt="Animation: die Anzeigetafel in einem 501-Match; nach jeder Aufnahme wechselt der Wurf zwischen Alex und Sam, und Alex checkt 141 mit T20 T19 D12 zum Sieg" width="760">

**Auf dieser Seite:** [Was du brauchst](#was-du-brauchst) · [Den Bildschirm einrichten](#den-bildschirm-einrichten) · [Vollbild](#vollbild) · [Auf dem Fernseher mit Home Assistant Cast](#auf-dem-fernseher-mit-home-assistant-cast) · [Quer, hochkant und Fernseher](#quer-hochkant-und-fernseher) · [Das nächste Spiel wählen](#das-nächste-spiel-wählen) · [Während des Spiels](#während-des-spiels) · [Darts korrigieren und eingeben](#darts-korrigieren-und-eingeben) · [Turniere](#turniere) · [Der Caller](#der-caller) · [Zwischen den Spielen: Ruhemodus](#zwischen-den-spielen-ruhemodus) · [Stream-Overlay](#stream-overlay) · [Tipps](#tipps) · [Wenn etwas nicht passt](#wenn-etwas-nicht-passt)

## Was du brauchst

- **Einen Bildschirm mit Browser:** ein Tablet an der Wand, einen Fernseher mit Browser oder einem kleinen PC, ein altes Handy. Alles, was dein Home Assistant öffnet, funktioniert, und ein Fernseher mit Chromecast [über Home Assistant Cast](#auf-dem-fernseher-mit-home-assistant-cast).
- **Einen Home-Assistant-Benutzer für den Bildschirm.** Ein eigener Benutzer ohne Administratorrechte verhindert, dass am Bildschirm deine Einstellungen geändert werden. Der Bildschirm zeigt das Dashboard in der Sprache dieses Benutzers: Deutsch, Englisch, Niederländisch, Französisch oder Spanisch, andere [Sprachen](README.de.md#sprachen) auf Englisch.
- **Die Karten der Integration,** die sich von selbst laden. Auf dem Bildschirm musst du nichts installieren.

## Den Bildschirm einrichten

1. **Dashboard anlegen.** Öffne **Einstellungen → Dashboards → Dashboard hinzufügen → HomeDarts**. Das [automatische Dashboard](cards.de.md#automatisches-dashboard) hat eine Ansicht *Anzeigetafel*, die die [Anzeigetafel-Karte](cards.de.md#anzeigetafel) über den ganzen Bildschirm zeigt.
2. **Ansicht auf dem Bildschirm öffnen.** Melde dich als Benutzer des Bildschirms an und öffne die Ansicht *Anzeigetafel* des Dashboards. Ihre Adresse endet auf `/scoreboard`, bei mehreren Boards auf `/scoreboard-1`, `/scoreboard-2` und so weiter; lege ein Lesezeichen an oder setze sie auf den Startbildschirm des Tablets.
3. **Vollbild.** Tippe auf die Vollbild-Taste oben rechts auf der Anzeigetafel, die letzte ihrer oberen Leiste: Die Leisten des Browsers, die Kopfzeile von Home Assistant und seine Seitenleiste verschwinden, und der Bildschirm bleibt an, solange die Anzeigetafel ihn füllt. Die Taste, Escape oder zweimal Tippen beendet das Vollbild wieder. [Vollbild](#vollbild) sagt, welche Browser den Bildschirm anlassen und was in den anderen hilft.
4. **Einschalten, was dir gefällt.** Öffne das Menü des Dashboards (⋮) → **Dashboard bearbeiten**. Im Abschnitt *Ansicht Anzeigetafel* schaltest du den [Caller](#der-caller) und das [Tastenfeld](#darts-korrigieren-und-eingeben) ein und wählst die Spiele der [Spielauswahl](#das-nächste-spiel-wählen) und die Seiten des [Ruhemodus](#zwischen-den-spielen-ruhemodus); das Dashboard bleibt automatisch und bekommt die Ansichten späterer Versionen. Für jede andere Option baust du eine eigene Ansicht: eine Ansicht im Panel-Modus mit der Anzeigetafel und `full_height: true`, oder du wählst im Menü dieses Editors **Kontrolle übernehmen**, das aus dem Dashboard eines macht, das du selbst bearbeitest:

```yaml
type: custom:homedarts-scoreboard-card
full_height: true
caller: true
lobby_games: ["301", "501", cricket, killer, around_the_clock]
idle_after: 300
idle_panels: [leaderboard, today, last_match, clock]
```

Die [Anleitung zu den Karten](cards.de.md#anzeigetafel) nennt jede Option.

## Vollbild

Die Vollbild-Taste oben rechts auf der Anzeigetafel zeigt die Anzeigetafel allein auf dem Bildschirm, von Rand zu Rand: ohne die Leisten des Browsers, ohne Kopfzeile und Seitenleiste von Home Assistant. Die Spielstände nehmen die ganze Höhe ein, wie mit `full_height`, und die Taste bleibt gedrückt. Die Taste, Escape oder zweimal Tippen auf die Anzeigetafel beendet das Vollbild; ein Tipp auf eine ihrer Tasten, etwa die des Tastenfelds, zählt nie als halber Doppeltipp.

<img src="images/de/scoreboard-fullscreen.png" alt="Die Anzeigetafel im Vollbild auf einem Tablet im Querformat, ohne Kopfzeile und Seitenleiste von Home Assistant: Übungsspiel 501, Alex am Board mit 301 Rest nach einer T20, Sam mit 417, und oben rechts die gedrückte Vollbild-Taste. Unter dem Titel der Hinweis eines Browsers, der den Bildschirm unter einer http://-Adresse nicht anlassen kann, mit dem Link So bleibt er an" width="760">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/de/fullscreen-dark.png">
  <img src="images/de/fullscreen-light.png" alt="Wie die Anzeigetafel im Vollbild den Bildschirm eingeschaltet lässt: Ein Tipp auf die Vollbild-Taste zeigt die Anzeigetafel allein auf dem Bildschirm, ohne die Leisten des Browsers und ohne Kopfzeile und Seitenleiste von Home Assistant. Wo der Browser einer Seite erlaubt, den Bildschirm eingeschaltet zu lassen, unter einer https://-Adresse im Browser wie in der Companion-App, bleibt er an. Zeigt das Tablet eine andere App, lässt der Browser los, und die Anzeigetafel hält den Bildschirm wieder an, sobald die Seite wieder zu sehen ist. Wo der Browser es nicht kann, sagt ein Hinweis einmal, die automatische Bildschirmabschaltung des Tablets auszuschalten. Die Taste, Escape oder zweimal Tippen beendet das Vollbild, und der Bildschirm darf wieder ausgehen." width="560">
</picture>

- **Der Bildschirm bleibt an,** solange die Anzeigetafel ihn füllt: Die Karte bittet den Browser, den Bildschirm anzulassen (Screen Wake Lock), und bittet erneut, wenn das Tablet die Seite nach einer anderen App wieder zeigt. Browser erlauben das einer Seite nur unter einer Adresse, die mit `https://` beginnt, etwa der von Home Assistant Cloud; das gilt auch für die Companion-App von Home Assistant, die Home Assistant in einem eigenen Browser zeigt.
- **Wo der Browser es nicht kann,** etwa unter einer Adresse, die mit `http://` beginnt, sagt die Anzeigetafel das einmal, mit einem Link auf diesen Abschnitt. Schalte die automatische Bildschirmabschaltung in den Einstellungen des Tablets aus, zumindest am Ladegerät, oder öffne die Ansicht in einem Kiosk-Browser, der den Bildschirm anlässt. Die Android-Companion-App kann den Bildschirm auch selbst anlassen, mit einer Einstellung unter *Companion-App* in ihren Einstellungen.
- **Wo die Taste erscheint:** in jedem Browser, der eine Seite ins Vollbild lässt, etwa Chrome, Edge, Firefox und Samsung Internet auf einem Tablet, einem Computer oder einem Handy, und Safari auf einem iPad. Safari auf dem iPhone zeigt nur Videos auf dem ganzen Bildschirm, dort bleibt die Taste weg: Lege die Ansicht stattdessen auf den Home-Bildschirm, der sie ohne die Leisten von Safari öffnet. Der Fernseher mit [Home Assistant Cast](#auf-dem-fernseher-mit-home-assistant-cast) und das [Stream-Overlay](#stream-overlay) haben auch keine, sie füllen ihren Bildschirm ohnehin.
- **Deine Wahl:** `fullscreen_button: false` blendet die Taste aus, und `keep_awake: false` überlässt den Bildschirm den Einstellungen des Tablets. Beides steht im Karteneditor und im Abschnitt *Ansicht Anzeigetafel* des [automatischen Dashboards](cards.de.md#automatisches-dashboard).

## Auf dem Fernseher mit Home Assistant Cast

Ein Fernseher mit Chromecast oder ein Google Nest Hub zeigt die Anzeigetafel ohne eigenen Browser: [Home Assistant Cast](https://www.home-assistant.io/integrations/cast/#home-assistant-cast) bringt ein Dashboard darauf, und die Karten laden dort von selbst.

1. **Home Assistant über HTTPS erreichen.** Cast braucht eine Adresse von Home Assistant, die mit `https://` beginnt, etwa die von Home Assistant Cloud.
2. **Die Ansicht streamen.** Öffne [cast.home-assistant.io](https://cast.home-assistant.io) in Chrome auf einem Computer oder einem Android-Handy im Netzwerk des Fernsehers, verbinde dein Home Assistant, wähle den Fernseher, dann das HomeDarts-Dashboard und seine Ansicht *Anzeigetafel*. Oder lass eine Automation streamen, etwa wenn ein Spiel beginnt, mit der Aktion der Integration [Google Cast](https://www.home-assistant.io/integrations/cast/):

   ```yaml
   action: cast.show_lovelace_view
   data:
     entity_id: media_player.living_room_tv
     dashboard_path: dashboard-darts
     view_path: scoreboard
   ```

   `dashboard_path` ist der erste Teil der Adresse des Dashboards nach dem Host, `view_path` der letzte Teil der Adresse der Ansicht.
3. **Spielen wie immer.** Der Fernseher zeigt das Dashboard; Spiele startest du, Darts gibst du ein und das nächste Spiel wählst du am Board, auf einem Handy oder einem Tablet. Der [Caller](#der-caller) startet mit einem Tippen auf den Bildschirm und bleibt auf einem Fernseher deshalb stumm: Der [Übungs-Caller](automations.de.md#practice-caller) sagt das Spiel stattdessen über deine Lautsprecher an.

[Wie die Karten auf den Fernseher kommen](cards.de.md#home-assistant-cast), mit den Zeilen für Ressourcen in YAML.

## Quer, hochkant und Fernseher

Die Anzeigetafel passt sich der Form des Bildschirms an. Mit `full_height: true` ist sie genau der Bildschirm unter der Werkzeugleiste: Ein Banner, die Aufnahme oder das Tastenfeld machen Zahlen und Tabellen kleiner, statt die Seite über den Bildschirm hinauszuschieben, sodass nichts gescrollt werden muss, vom kleinen 800 × 480-Display bis zum Fernseher. Auf einem Handy lässt sie Platz für die Adressleiste des Browsers und in der Companion-App für die Statusleiste und den Home-Balken.

- **Tablet im Querformat oder Fernseher:** die beste Wahl für X01 und die Partyspiele, deren Spielerkacheln nebeneinander stehen.

  <img src="images/de/scoreboard-teams.png" alt="Die Anzeigetafel auf einem Tablet im Querformat: ein 501-Team-Match von Alex und Kim mit Rest 45 gegen Sam und Lea mit Rest 216" width="760">

- **Tablet im Hochformat:** gut für Cricket, dessen Kreidetafel hoch ist, und für X01: Zwei Spieler stehen übereinander, drei oder vier zu zweit nebeneinander, und die Punkte nutzen die Höhe des Bildschirms.

  <img src="images/de/scoreboard-portrait.png" alt="Die Anzeigetafel auf einem Tablet im Hochformat: die Cricket-Kreidetafel von Alex und Sam mit T19 als nächstem Ziel und der aktuellen Aufnahme am unteren Rand" width="400">

- **Handy:** Alles passt auf einen Bildschirm, hochkant wie quer. Mit dem Tastenfeld oder der Scheibe zum Antippen wird der Punktestand jedes Spielers zu einer Zeile, sodass alle Punktestände sichtbar bleiben; quer nimmt das Tastenfeld die rechte Bildschirmhälfte von oben bis unten ein. Zum [Korrigieren eines Darts](#darts-korrigieren-und-eingeben) öffnet sich die Scheibe vergrößert, mit einer Lupe unter dem Finger.
- **Touch-Monitor:** Auf einem 24- oder 27-Zoll-Touchscreen neben dem Board ist jede Taste groß genug für einen Finger, auch mit angeschlossener Maus, und die Scheibe zum Antippen hat die Lupe und den Zwei-Finger-Zoom eines Handys.
- **Entfernung:** Der Rest ist der größte Text auf dem Bildschirm und wächst mit ihm. Je größer der Bildschirm, desto weiter weg ist er lesbar; ein Fernseher bedient also auch die Zuschauer.

## Das nächste Spiel wählen

Tippe zwischen den Spielen auf **Neues Spiel** unter dem Punktestand, während eines Spiels oben rechts. Einige Sekunden nach dem Ende eines Matches oder Trainingsspiels öffnet sich die Auswahl auch von selbst, mit der letzten Wahl für eine Revanche; ein stattdessen geworfener Dart schließt sie wieder.

Neben **Neues Spiel** startet ein Tippen den [Plan des Tages](games.de.md#trainingspläne). Während ein Plan läuft, nennt die Kopfzeile den aktuellen Schritt, und **Überspringen** und **Stoppen** unter dem Punktestand verlassen den Schritt oder beenden den Plan, jeweils nach einem zweiten Tippen.

<img src="images/de/lobby.webp" alt="Animation: Auf dem Tablet öffnet Neues Spiel die Spielauswahl, Cricket wird gewählt, Sam kommt zu Alex dazu, die Legs pro Satz steigen auf drei und das Spiel startet auf der Anzeigetafel" width="760">

1. **Spiel:** X01, die Cricket-Spiele, die Partyspiele und die Trainingsspiele, in Gruppen. `lobby_games` beschränkt die Auswahl auf die Spiele, die ihr spielt. Unter den Spielen erklärt *So wird gespielt* das gewählte Spiel in ein, zwei Sätzen, für Gäste, die es noch nie gespielt haben, und *Alle Regeln* öffnet seine Regeln auf der Dokumentations-Website.
2. **Spieler:** Tippe auf einen Namen, um den Spieler hinzuzufügen, auf ▲ und ▼, um die Reihenfolge zu ändern, und auf ✕, um ihn zu entfernen. Spieler, die mit einer [Person verknüpft](statistics.de.md#spieler-und-personen) sind, die zu Hause ist, stehen vorn, mit ihrem Bild. Tippe einen neuen Namen ein oder füge einen Gast ohne Namen hinzu. Bei X01 setzen − und + neben einem Spieler [eigene Startpunkte](games.de.md#startpunkte-handicap), und **Fairer Start** unter den Optionen rechnet sie aus den [Averages](games.de.md#fairer-start) aus. Bei X01 und den Cricket-Spielen setzt **+ Bot** den [Bot](games.de.md#gegen-den-bot-spielen) nach den Spielern dazu; − und + daneben ändern seine Stärke, und *Auf meinem Niveau* stellt sie auf den Average der Spieler.
3. **Format und Optionen:** Legs pro Satz und Sätze zum Sieg; Double-Out und Double-In für X01; das [Ausbullen](games.de.md#ausbullen); *Teams* für vier Spieler bei X01 oder Cricket; *Three in a Bed* für [Wild Mouse](games.de.md#wild-mouse).
4. **Starten.** Die Anzeigetafel zeigt das Spiel sofort. Ist die Erkennung gestoppt, schaltet der Start sie ein, und die Auswahl sagt es vorher über der Taste. Die Starttaste bleibt am unteren Bildschirmrand, während die Seite scrollt. Während eines Spiels beendet *Spiel beenden* es nach einem zweiten Tippen.

<img src="images/de/scoreboard-lobby.png" alt="Die Spielauswahl auf einem Tablet im Querformat: die Spiele nach Gruppen mit 501 gewählt, Alex und Sam mit ihren Bildern, Sam ab 301, drei Legs pro Satz, Double-Out und die Start-Taste" width="760">

Die Auswahl startet das Spiel mit [`homedarts.start_game`](entities.de.md#übungsspiel-starten-homedartsstart_game), genau wie eine Automation oder ein Sprachbefehl. Die [Anleitung zu Spielen](games.de.md#ein-spiel-starten) zeigt die anderen Wege.

## Während des Spiels

Die Anzeigetafel zeigt immer, was gespielt wird, und der Spieler am Board ist hervorgehoben:

| Spiel | Die Anzeigetafel zeigt |
| --- | --- |
| X01 | Rest, Legs, Sätze und Average jedes Spielers oder Teams; Checkout-Weg, Überwerfen oder Game shot des Spielers am Board und, wo kein Checkout möglich ist, der [Stellwurf](games.de.md#x01) mit dem Rest, den er stellt |
| Cricket-Spiele | Eine große Kreidetafel mit den Marks jedes Spielers oder Teams, den Punkten und den Marks pro Runde; die nächste offene Zahl oben links und [Rahmen](games.de.md#cricket-spiele), wo der Spieler am Board punktet oder besser schließt |
| Partyspiele | Runde und Ziel, die Punkte jedes Spielers, bei Killer Zahl und Leben, bei Golf und Baseball eine Scorekarte jedes Lochs oder Innings |
| Ausbullen | Das Feld des Darts jedes Spielers und seinen Abstand zur Mitte, den führenden Dart und *Gleichstand – noch einmal werfen*, wenn ein Gleichstand neu wirft |
| Trainingsspiele | Das Ziel in großer Schrift mit Runde, Punkten oder Trefferquote |

Am unteren Rand stehen die drei Darts der aktuellen Aufnahme und ihre Punkte, und solange das Board leer ist, die letzte Aufnahme; ein Tipp auf einen Dart [korrigiert ihn](#darts-korrigieren-und-eingeben). Beim Spielen bewegt sich nichts: Die Kacheln behalten ihre Höhe vom ersten Dart bis zum Game Shot. Große Momente werden darüber gefeiert, ohne etwas zu verschieben und nach zweieinhalb Sekunden wieder weg: Konfetti und ein goldenes Leuchten bei einer 180, Konfetti beim Game Shot und beim Match, ein Leuchten bei einer Aufnahme ab 100 und bei neun Marks in Cricket; `celebrations: false` schaltet sie ab, und mit reduzierter Bewegung im System bleiben sie aus. Ist ein Match entschieden, nennt ein Banner den Sieger mit dem Ergebnis, etwa *Alex gewinnt das Match 3 : 2!*, und nach einem X01- oder Cricket-Match tritt die [Match-Zusammenfassung](games.de.md#match-zusammenfassung) an die Stelle der Spieler: Averages, Checkout-Quote, höchster Checkout, 180er und das beste Leg aller Spieler.

<img src="images/de/celebration.webp" alt="Animation: eine 180 auf der Anzeigetafel. Alex wirft drei Triple 20, ein goldenes Leuchten erhellt die Anzeigetafel und Konfetti fliegt aus ihrer Mitte, dann zeigt die Anzeigetafel 321 wie zuvor" width="760">

<img src="images/de/match-summary.png" alt="Anzeigetafel, nachdem Alex Sam in 301 mit 2 : 1 geschlagen hat: die Match-Zusammenfassung mit Legs, 3-Dart-Average, First 9, Checkout-Quote, höchstem Checkout, 180ern, 140+, 100+, bestem Leg, Darts aufs Double und Darts beider Spieler" width="760">

Jedes Spiel hat seinen eigenen Bildschirm:

- **Killer:** die Leben jedes Spielers als Herzen, mit seiner Zahl und ob er Killer ist, bis nur noch einer übrig ist.

  <img src="images/de/killer.webp" alt="Animation: Killer für Alex, Sam und Kim auf der Anzeigetafel. Jeder wirft um eine Zahl, Alex wird Killer und nimmt Sam die Leben, Kim wird ebenfalls Killer, und Alex nimmt das letzte Leben zum Sieg" width="760">

- **Cricket:** die Kreidetafel mit den Marks, den Punkten und den Marks pro Runde und das nächste Ziel oben links.

  <img src="images/de/scoreboard-cricket.png" alt="Anzeigetafel bei Cricket zwischen Alex und Sam: die Kreidetafel mit Marks, Punkten und Marks pro Runde, T19 als nächstes Ziel" width="760">

- **Golf:** das Loch, das gespielt wird, und die Schläge jedes Spielers.

  <img src="images/de/golf.webp" alt="Animation: Golf für Alex und Sam auf der Anzeigetafel. Nach jeder Aufnahme füllt sich die Scorekarte: Alex spielt 2, 3 und 1, Sam 4, 5 und 5, und das vierte Loch läuft" width="760">

- **Catch 40:** der Rest zum Checken in großer Schrift, mit dem Weg, der Runde und den bisherigen Punkten.

  <img src="images/de/scoreboard-catch-40.png" alt="Catch 40 auf der Anzeigetafel: In der zweiten Runde lässt ein Single 12 von 62 noch 50 übrig, der Weg ist das Bull, und der erste Checkout brachte 3 Punkte" width="760">

## Darts korrigieren und eingeben

<img src="images/de/correct-dart.webp" alt="Animation: Die Anzeigetafel zeigt T20, S20 und T20 für 140; ein Tipp auf den zweiten Dart öffnet das Tastenfeld, ein Tipp auf T und auf 20 korrigiert ihn, und die Aufnahme zeigt 180" width="760">

- **Ein falsch erkannter Dart:** Tippe ihn in der Aufnahme am unteren Rand an. Ein Tastenfeld öffnet sich mit S, D und T, den Zahlen 1 bis 20, 25, Bull und Fehlwurf; tippe den Multiplikator und die Zahl, und das Spiel zählt den Dart dort. Ein zweiter Tipp auf den Dart oder *Abbrechen* schließt das Tastenfeld.
- **Wo er wirklich steckt:** Wähle oben im Tastenfeld *Scheibe* und tippe auf die Stelle der Scheibe, an der der Dart steckt. Das Feld ergibt sich aus der Stelle, und der Dart zählt dort für die [Dart-Positionen](statistics.de.md#trefferbild-und-dart-positionen). Ein gestrichelter Ring zeigt, wo das Board ihn gesehen hat. Mit den Tasten korrigiert, hat der Dart keine Position, damit eine falsch erkannte Stelle nie die Streuung verfälscht.

  <img src="images/de/correct-dart-board.webp" alt="Animation: Das Board hat den zweiten Dart als T20 erkannt, 180 Punkte; ein Tipp darauf öffnet das Tastenfeld, Scheibe zeigt die Scheibe mit einem gestrichelten Ring, wo das Board den Dart gesehen hat, und ein Tipp auf das Single 20 darüber korrigiert die Aufnahme auf 140" width="760">

- **Auf dem Handy:** Die Scheibe öffnet sich vergrößert um die Stelle, an der das Board den Dart gesehen hat, damit die Fingerkuppe das richtige Feld trifft. Halte einen Finger auf die Scheibe und schiebe ihn: Eine Lupe über dem Finger zeigt die Stelle vergrößert mit einem Kreuz, und der Dart landet dort, wo du loslässt. Mit zwei Fingern zoomst du weiter und verschiebst die Scheibe; die runde Lupen-Taste in der Ecke der Scheibe zeigt sie mit ihrem Minus ganz und vergrößert mit ihrem Plus wieder.

  <img src="images/de/correct-dart-loupe.webp" alt="Animation auf einem Handy: Das Board hat den zweiten Dart als T20 erkannt, 180 Punkte; ein Tipp darauf und auf Scheibe öffnet die Scheibe vergrößert um den gestrichelten Ring, wo das Board ihn gesehen hat; ein Finger schiebt vom Ring nach oben, die Lupe darüber zeigt das Single 20 unter einem Kreuz, und wo der Finger loslässt, wird die Aufnahme zu 140" width="360">

- **Zu spät bemerkt:** Nach der Entnahme zeigt die Kachel *Zuletzt* neben den Darts die letzte Aufnahme mit einem gebogenen Pfeil; ein Tipp darauf und ein zweiter auf das rote *Zurück?* nehmen sie zurück. Korrigiere ihre Darts und beende sie dann mit *Nächster Spieler*.
- **Von Hand eingegebene Darts:** Für Darts, die das Board übersehen hat, oder einen Spieler ohne Kameras schaltest du *Übungsspiel manuelle Eingabe* und die Option `keypad` der Karte ein. Das Tastenfeld gibt jedes angetippte Feld als Dart ein; *Nächster Spieler* beendet die Aufnahme. Im Querformat stehen Korrektur und Tastenfeld neben den Punkten, sodass beides auf den Bildschirm passt. Eine [Dartscheibe ohne Autodarts](without-autodarts.de.md) hat das Tastenfeld ohne beides.
- **Die Punkte einer Aufnahme:** In X01 nimmt *Punkte* oben im Tastenfeld eine Aufnahme mit ihrer Punktzahl, etwa 140, mit **OK**; ein Checkout fragt nach seinen Darts und den Darts auf ein Doppel. Mit einer Tastatur tippst du die Punkte und drückst Enter, und eine Ziffer beantwortet eine Frage; das Tastenfeld behält die Tasten für die nächste Aufnahme. [Wie sie zählt](without-autodarts.de.md#darts-eingeben).
- **Was du siehst:** Ein Stift zeigt jeden Dart, den ein Tipp korrigiert; von Hand eingegebene oder korrigierte Darts haben einen gestrichelten Rahmen, die Darts des Bots eine Tönung in der Akzentfarbe.

<img src="images/de/scoreboard-keypad.png" alt="Die Anzeigetafel mit dem Tastenfeld: Alex hat T20 und S19 von Hand eingegeben, gestrichelt umrandet; darunter S, D und T, die Zahlen 1 bis 20, 25, Bull, Miss und Nächster Spieler" width="760">

Was eine Korrektur ändert, erklärt die [Anleitung zu Spielen](games.de.md#korrekturen-und-von-hand-eingegebene-darts), [alle Details](cards.de.md#darts-korrigieren-und-eingeben) stehen in der Anleitung zu den Karten.

## Turniere

Für ein [Turnier](games.de.md#turniere) mit drei bis 32 Spielern führt der Bildschirm am Board durch den Abend:

1. **Hier starten:** Tippe auf **Neues Spiel**, dann auf **Turnier**. Wähle die Spieler mit Namen, bis zu acht bei jeder gegen jeden und 32 in den anderen Formaten, X01 mit Startpunkten als Handicap oder ein Cricket-Spiel, jeder gegen jeden, K.-o.-System, Doppel-K.-o.-System oder Gruppen und K.-o.-System, Legs und Sätze, die Regeln, das Spiel um Platz 3 und eine zufällige Auslosung, und tippe auf **Turnier starten**.
2. **Während eines Matches** nennt die Titelzeile Runde und Match, etwa *Turnier · Halbfinale · Match 5 von 7* oder *Turnier · Gruppe B · Runde 2 · Match 6 von 63*.
3. **Zwischen den Matches** bleibt die Zusammenfassung des Matches einige Sekunden stehen, dann erscheint die Tabelle (jeder gegen jeden), die Tabellen der Gruppen oder der Turnierbaum, im Doppel-K.-o.-System mit der Verliererrunde darunter, mit dem nächsten Match und einem Countdown. **Jetzt starten** startet es sofort; sonst beginnt es von selbst, sobald die Darts aus dem Board sind.
4. **Am Ende** nennt ein Banner den Turniersieger, und Tabelle oder Turnierbaum bleiben stehen, bis ein neues Match beginnt. *Turnier beenden* in der Spielauswahl beendet ein Turnier vorzeitig. Ein neues Turnier, das während eines laufenden startet, beendet zuerst das laufende, nach einem zweiten Tipp.
5. **Auf mehreren Boards** zeigt die Anzeigetafel jedes Boards ihr eigenes Match und zwischen den Matches über Tabelle oder Turnierbaum einen Kasten je Board: was es spielt oder wann sein nächstes Match beginnt, der eigene Kasten hervorgehoben, und das voraussichtliche Ende des Turniers. [Ein Turnier auf mehreren Boards](games.de.md#ein-turnier-auf-mehreren-boards).

**Turnier** in der Spielauswahl legt Spieler, Spiel, Format und Regeln fest:

<img src="images/de/tournament-lobby.png" alt="Die Spielauswahl im Turniermodus: X01 und die Cricket-Spiele, sechs Spieler mit ihren Startpunkten, K.-o.-System mit Spiel um Platz 3 und die Starttaste" width="560">

Zwischen zwei Matches wartet das nächste Match mit seinem Countdown über der Tabelle des Turniers jeder gegen jeden:

<img src="images/de/tournament-table.png" alt="Das Turnier jeder gegen jeden mit vier Spielern auf der Anzeigetafel zwischen zwei Matches: als Nächstes Lea gegen Sam mit Countdown und die Tabelle mit Alex vorn mit 4 Punkten" width="760">

Die Tabelle ordnet nach Punkten, zwei für einen Sieg, dann nach der Entscheidung bei Gleichstand aus den [Turnierregeln](games.de.md#turnierregeln). Im Turnierbaum gleitet, wer weiterkommt, in die nächste Runde. [Alle Details](cards.de.md#turniere).

## Der Caller

Mit `caller: true` sagt der Bildschirm am Board das Spiel selbst an, über den Lautsprecher des Tablets oder Fernsehers. Er braucht keine Lautsprecher und keine Sprachausgabe in Home Assistant.

1. Schalte `caller` im Editor der Karte ein, oder beim automatischen Dashboard in seinen Einstellungen: Menü (⋮) → **Dashboard bearbeiten** → *Ansicht Anzeigetafel*.
2. Browser spielen Ton erst nach einem Tippen ab: Tippe einmal auf **Caller** auf der Anzeigetafel. Lautsprechersymbol und gedrückte Taste zeigen, dass er an ist; ein weiteres Tippen schaltet ihn stumm.

Er sagt nur an, was zählt, in der Sprache des Benutzers am Bildschirm: Deutsch, Englisch, Niederländisch, Französisch oder Spanisch.

- **X01:** die Punkte einer Aufnahme, „Überworfen“ beim Überwerfen, „Keine Punkte“ vor dem öffnenden Double, „du brauchst 81“, sobald der Rest checkbar ist, „stell dir die 32“, wenn nur ein Stellwurf möglich ist, den Game shot eines Legs und des Matches und eine Fanfare bei einer 180. Der Bot heißt *Bot*.
- **Cricket-Spiele:** die Marks einer Aufnahme, etwa „5 Marks“; bei [Random Cricket](games.de.md#random-cricket) die Zahlen jedes Legs, wenn es beginnt, etwa „Die Zahlen 18, 14, 11, 7, 5, 2 und das Bull“, und bei [Hidden Cricket](games.de.md#hidden-cricket) eine Zahl, sobald ein Dart sie aufdeckt, etwa „Die 17 ist im Spiel“. **Shanghai**, **Halve-It** und **Bermuda:** die Punkte auf das Ziel; **Count-Up** und **Round the World:** die Punkte der Aufnahme; **Gotcha:** die Punkte der Aufnahme oder „Überworfen“ für eine Aufnahme, die zu weit ging; **Baseball:** die Runs.
- **Checkout-Training, 121-Checkout und Catch 40:** was der nächste Versuch braucht.
- **Turniere:** jedes Match beim Start, „Nächstes Match: Alex gegen Sam“, und den Sieger des Turniers.
- Darts nach dem Überwerfen oder einem Game shot werden nicht angesagt. Killer, Golf und die anderen Trainingsspiele bekommen keine Punktansagen.
- **Für blinde und sehbehinderte Spieler**, wenn du es einschaltest: jeden Dart, den Checkout-Weg und das nächste Ziel ([Details](#für-blinde-und-sehbehinderte-spieler)).

Ein Bildschirm, der weg war, auf einer anderen Ansicht oder ohne seine Verbindung zu Home Assistant, sagt nichts an und feiert nichts, was in der Zwischenzeit geschah, etwa ein Match, das in den Minuten davor endete; ab seiner Rückkehr sagt er das Spiel wieder an.

`call_scores`, `call_checkouts`, `call_results` und `call_sounds` schalten jede Art von Ansage ein oder aus. Welche Stimme spricht, hängt von Browser und Betriebssystem ab: Offline-Stimmen des Betriebssystems behalten die Ansagen bei dir zu Hause; manche Browser nutzen Online-Stimmen, die den Text an ihren Anbieter schicken. Ein [Voice-Pack](#voice-packs) gibt dem Caller stattdessen eine echte Stimme. Für Lautsprecher im Raum nutzt du die [Blueprints Dart caller und Practice caller](automations.de.md#welcher-caller), die ebenfalls Voice-Packs abspielen.

### Für blinde und sehbehinderte Spieler

Drei Optionen machen das Board spielbar, ohne es zu sehen: Der Caller sagt jeden Dart an, wohin ein Checkout geht und worauf du als Nächstes zielst. Sie sind anfangs aus. Schalte sie in den Caller-Optionen im Editor der Karte ein, oder beim automatischen Dashboard in seinen Einstellungen, *Ansicht Anzeigetafel*:

```yaml
type: custom:homedarts-scoreboard-card
caller: true
call_darts: bed
call_route: true
call_target: true
```

| Option | Was der Caller sagt |
| --- | --- |
| `call_darts: bed` | Jeden Dart, sobald er steckt, in jedem Spiel, mit seinem Feld: „Triple 20“, „Doppel 16“, „5“ für ein Single, „25“, „Bull“ für das Bullseye oder „Fehlwurf“. `call_darts: score` sagt stattdessen seine Punkte, etwa „60“ oder „50“. Ein Dart, den du korrigierst, wird noch einmal angesagt. |
| `call_route: true` | In X01, im Checkout-Training, im 121-Checkout und in Catch 40: den Weg eines Checkouts nach dem, was der Spieler braucht, etwa „Triple 19, Doppel 12“, und nach jedem Dart, der für die übrigen Darts einen anderen Checkout lässt, mit dem Rest, den er checkt: „62: Triple 10, Doppel 16“. |
| `call_target: true` | In Around the Clock, im Doppeltraining und im Singles-Training, in Bob's 27, in der JDC Challenge und in den Partyspielen mit einem Ziel, etwa Shanghai, Halve-It, Bermuda, Round the World, Golf und Baseball: das nächste Ziel, etwa „Ziel: Doppel 16“, „Ziel: Beliebiges Double“ oder „Ziel: Bull“, sobald es weitergeht und immer dann, wenn ein Spieler an der Reihe ist. |

Eine Aufnahme von Sam bei 81 in einem Match, mit allen dreien:

| Am Board | Der Caller sagt |
| --- | --- |
| Sam ist dran | „Sam, du brauchst 81“, „Triple 19, Doppel 12“ |
| Der erste Dart in die Single 19 | „19“, „62: Triple 10, Doppel 16“ |
| Der zweite Dart in die Triple 10 | „Triple 10“, „32: Doppel 16“ |
| Der dritte Dart in die Doppel 16 | „Doppel 16“, „Game shot, und das Leg!“ |

Die Aufnahmen des Bots bekommen die Darts, aber keinen Weg und kein Ziel. Mit einem [Voice-Pack](#voice-packs) spielen die Darts, Wege und Ziele die Dateien ihrer Felder, und die Stimme des Browsers sagt eine Ansage, für die dem Pack eine Datei fehlt.

### Voice-Packs

Die Stimme des Browsers klingt auf jedem Gerät anders und auf vielen wie ein Roboter. Ein Voice-Pack gibt dem Caller eine eigene Stimme: aufgenommene Ansagen im Medienordner von Home Assistant, die der Bildschirm über seinen Lautsprecher abspielt. Seine Dateien heißen wie in den Voice-Packs von [darts-caller](https://github.com/lbormann/darts-caller), daher funktioniert ein Pack von darts-caller so, wie es ist, und die Aktion [`homedarts.generate_voice_pack`](entities.de.md#ein-voice-pack-aufnehmen-homedartsgenerate_voice_pack) nimmt eines mit einer Text-to-Speech-Engine von Home Assistant auf, etwa mit [Piper](https://www.home-assistant.io/integrations/piper/) für eine Stimme, die dein Zuhause nie verlässt.

1. Lege das Pack in einen Ordner in `homedarts/voices` des Medienordners, etwa `/media/homedarts/voices/russ-bray/` unter Home Assistant OS, mit der App *Samba share* oder *File editor*. Oder nimm eines auf: **Entwicklerwerkzeuge → Aktionen**, *HomeDarts for Autodarts: Voice-Pack erzeugen*, mit deiner Engine, ihrer Sprache und einem Namen wie `piper-de`; das dauert einige Minuten.
2. Trage den Namen des Ordners als *Voice-Pack* in den Caller-Optionen im Editor der Karte ein, `caller_voice: russ-bray`, oder beim automatischen Dashboard in seinen Einstellungen, *Ansicht Anzeigetafel*.
3. Tippe auf **Caller**. Jedes Tippen, das ihn einschaltet, fragt das Pack neu ab, sodass Dateien, die du inzwischen hinzugefügt hast, ab dann zählen.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/de/voice-packs-dark.png">
  <img src="images/de/voice-packs-light.png" alt="So spricht der Caller mit einem Voice-Pack: Ein in den Medienordner kopiertes Pack von darts-caller oder eines, das homedarts.generate_voice_pack mit Piper aufgenommen hat, ist ein Ordner in homedarts/voices. Hat das Pack die Dateien einer Ansage, etwa 180, busted, gameshot, matchshot oder yr_40, lädt der Bildschirm sie mit seiner Anmeldung und spielt sie nacheinander ab, einen Namen ohne Datei mit der Stimme des Browsers. Fehlt dem Pack die Ansage oder lädt eine Datei nicht, sagt die Stimme des Browsers die ganze Ansage. Die nächste Ansage wartet, bis diese zu Ende ist" width="560">
</picture>

| Ansage | Dateien des Packs |
| --- | --- |
| Die Punkte einer Aufnahme | `0` bis `180`; `0` ist „Keine Punkte“ |
| Überworfen | `busted` |
| Der Game shot eines Legs | `gameshot` |
| Das Match | `matchshot`, dann der Name des Siegers |
| Was ein Spieler braucht | `yr_40`, oder `you_require` und dann `c_40` oder `40`; im Match zuerst der Name des Spielers |
| Der Name eines Spielers | Eine Datei, die wie der Spieler in Kleinbuchstaben heißt, etwa `alex.mp3`; ohne sie sagt die Stimme des Browsers den Namen |
| [Jeder Dart](#für-blinde-und-sehbehinderte-spieler) | Mit seinem Feld `t20`, `d16`, `s5` oder `5`, `bull` für die 25 und `bullseye`, mit seinen Punkten `1` bis `60`, und `outside` für einen Fehlwurf |
| Der Weg eines Checkouts | Die Dateien seiner Felder; mit dem Rest zuerst `c_62` oder `62` |
| Das nächste Ziel | `bs_target_is`, dann das Ziel: `20` oder `s20`, `d16`, `t20`, `bs_any_double` für ein beliebiges Double, `bull` für das Bull und `bullseye` für das Bullseye allein |

Die Dateien sind `.mp3`, `.wav`, `.ogg` oder `.flac`, auch in Ordnern des Packs. Eine Ansage mit mehreren Dateien, etwa `gameshot.mp3` und `gameshot+2.mp3`, spielt eine davon nach Zufall, wie bei darts-caller. Jede Ansage, für die das Pack keine Datei hat, etwa die Marks einer Cricket-Aufnahme oder das nächste Match eines Turniers, sagt die Stimme des Browsers, ebenso eine Ansage, deren Datei nicht lädt. Jede Ansage wartet, bis die davor zu Ende ist, sodass sich Ansagen nie überlagern. Der Bildschirm lädt die Dateien mit seiner eigenen Anmeldung aus Home Assistant, und nur die, die Home Assistant für das Pack nennt.

## Zwischen den Spielen: Ruhemodus

Läuft kein Spiel oder ist ein Match oder Trainingsspiel entschieden und wirft oder tippt `idle_after` Sekunden lang niemand (standardmäßig 3 Minuten), zeigt die Anzeigetafel ihre Seiten im Wechsel: Tabelle oder Turnierbaum eines Turniers, die Bestenliste, die Bestleistungen des Boards, die Darts von heute zum Tagesziel, das letzte Match und eine Uhr.

<img src="images/de/scoreboard-idle.png" alt="Ruhemodus der Anzeigetafel: die Bestenliste mit Alex, Sam und Kim, ihren Bildern, 3-Dart-Averages und gewonnenen Legs" width="760">

Ein Dart, ein neues Spiel oder ein Tippen irgendwohin beendet den Ruhemodus; eine Spielauswahl, die du geöffnet hattest, kommt so zurück, wie du sie verlassen hast. `idle_panels` wählt die Seiten und ihre Reihenfolge, `idle_interval`, wie lange jede zu sehen ist. Auf Geräten, die reduzierte Bewegung wünschen, wechseln die Seiten ohne Überblendung. [Alle Seiten](cards.de.md#ruhemodus).

## Stream-Overlay

Streame deine Spiele: Die Anzeigetafel allein, ohne ihre Karte, liegt über dem Bild deines Streams in OBS Studio, Streamlabs oder jeder anderen Software mit einer Browserquelle. Sie zeigt das Spiel und sein Format, die Punkte jedes Spielers, den Checkout-Weg des Spielers am Board, die Darts der Aufnahme, den Sieger und das Konfetti der großen Momente, und zwischen den Spielen gar nichts.

<img src="images/de/scoreboard-overlay.png" alt="Das Stream-Overlay am unteren Rand des Bildes vom Board: Übungsspiel 501 mit drei Legs pro Satz, Alex am Board mit 84 Rest und dem Weg T20 D12, Sam mit 375, und daneben die Aufnahme mit T20 und 60 Punkten" width="760">

1. **Ein Benutzer für OBS.** Lege unter **Einstellungen → Personen** eine Person mit *Anmelden erlauben* an, ohne Administratorrechte und mit *Kann sich nur aus dem lokalen Netzwerk anmelden*, damit OBS deine Einstellungen nicht ändern kann.
2. **Die Ansicht.** Das [automatische Dashboard](cards.de.md#automatisches-dashboard) hat eine Ansicht *Stream-Overlay*, die bei seinen Tabs nicht steht. Ihre Adresse ist die des Dashboards mit `/overlay` am Ende, etwa `http://homeassistant.local:8123/dashboard-homedarts/overlay`; bei mehreren Boards `/overlay-1`, `/overlay-2` und so weiter.
3. **Die Browserquelle.** Füge in OBS eine Quelle **Browser** mit dieser Adresse hinzu, mit einer Breite von 1920 und einer Höhe von 1080, und schalte *Quelle herunterfahren, wenn nicht sichtbar* aus, damit sie angemeldet bleibt. Klicke die Quelle mit der rechten Maustaste an, wähle **Interagieren** und melde dich einmal als Benutzer für OBS an.
4. **Platzieren.** Lege die Quelle in der Szene über die Kamera deines Streams. Das Overlay ist durchsichtig: Wo es nichts zeigt, zeigt OBS deine Kamera.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/de/stream-overlay-dark.png">
  <img src="images/de/stream-overlay-light.png" alt="Wie die Anzeigetafel in einen Stream mit OBS kommt: Ein Dart landet im Board, und Home Assistant zeigt ihn auf der Anzeigetafel-Karte der Ansicht, deren Adresse auf /overlay endet. OBS öffnet diese Adresse als Browserquelle mit 1920 mal 1080 Pixeln, angemeldet als eigener Benutzer. Ein durchsichtiges Overlay geht direkt in die Szene; auf einer Keyfarbe nimmt der Chroma-Key-Filter von OBS die Farbe vorher heraus. Die Szene legt das Overlay über die Kamera des Streams, und der Stream zeigt Punkte, Weg und Aufnahme" width="480">
</picture>

In den Einstellungen des Dashboards wählt der Abschnitt *Ansicht Stream-Overlay* den Rest:

| Einstellung | Auswahl |
| --- | --- |
| *Overlay* (`overlay`) | `transparent`, durchsichtig, für eine Browserquelle; oder `chroma`, auf einer Keyfarbe, für Software, die keine durchsichtigen Seiten zeigen kann, etwa die Aufnahme eines Fensters. Füge der Quelle in OBS den Filter **Chroma Key** hinzu, mit *Schlüsselfarbtyp* *Benutzerdefiniert* und der Keyfarbe. |
| *Platz im Bild* (`overlay_layout`) | `lower_third`, die Spieler nebeneinander am unteren Rand mit der Aufnahme daneben; `corner`, ein Kasten in der Ecke oben links mit einer Zeile für jeden von bis zu vier Spielern; oder `full`, das ganze Bild, für eine eigene Szene, mit der [Match-Zusammenfassung](cards.de.md#match-zusammenfassung) und zwischen den Matches der Tabelle oder dem Turnierbaum eines [Turniers](#turniere). |
| *Keyfarbe* (`overlay_color`) | Die Farbe unter einem `chroma`-Overlay, standardmäßig `#00FF00`. Nimm `#FF00FF`, wenn dein Raum grün ist. |

<img src="images/de/scoreboard-overlay-corner.png" alt="Das Stream-Overlay in der Ecke oben links auf der Keyfarbe, bevor der Chroma-Key-Filter von OBS das Grün herausnimmt: Übungsspiel 501, Alex mit 84 Rest und dem Weg T20 D12, Sam mit 375, und darunter die Aufnahme mit T20" width="760">

Für eine eigene Ansicht setzt du die [Anzeigetafel-Karte](cards.de.md#anzeigetafel) mit `overlay` in eine Ansicht im Panel-Modus, am besten eine Unteransicht, aber nie die erste Ansicht eines Dashboards: Wer das Overlay verlässt, landet wieder in der ersten Ansicht.

Die Karte:

```yaml
type: custom:homedarts-scoreboard-card
overlay: chroma
overlay_layout: corner
overlay_color: "#FF00FF"
```

- **Auf dem Dashboard nimmt das Overlay das ganze Fenster ein** und verbirgt Home Assistant drumherum, auch die Kopfzeile und die Seitenleiste. **Escape** oder ein Doppelklick verlässt es, zur Seite davor oder zur ersten Ansicht des Dashboards. Im Karteneditor und im Bearbeitungsmodus eines Dashboards zeigt sich das Overlay in der Karte, auf seiner Keyfarbe oder, durchsichtig, auf einem Schachbrett.
- **Einen Stream tippt niemand an:** Das Overlay hat keinen Bildschirm für ein neues Spiel, keinen Ruhemodus, kein Tastenfeld und keine Korrekturen; starte Spiele am Board, auf dem Handy oder auf dem Tablet am Board. Sein Caller bleibt still; der [Dart caller](automations.de.md#dart-caller) oder der [Practice caller](automations.de.md#practice-caller) ruft das Spiel stattdessen über deine Lautsprecher aus.
- **Eigene Farben:** Das Overlay behält helle Schrift auf dunklen Tafeln, über jedem Bild und mit jedem Theme, in der Akzentfarbe der Karte für den Spieler am Board und in Gold für den Sieger. Auf einer Keyfarbe lässt es das Leuchten eines großen Moments weg, das ein Chroma Key als Rand stehen ließe; das Konfetti bleibt.
- **Clips deiner Highlights:** Mit einer *Clip camera* nimmt das [Highlight-Foto](automations.de.md#highlight-photo) jeden großen Moment auch als Clip auf, ab ein paar Sekunden vor dem Dart, den die [Highlight-Galerie](automations.de.md#highlight-galerie) abspielt.

## Tipps

- **Die Live-Karte auf einem zweiten Bildschirm:** Ein Handy oder zweites Tablet mit der [Live-Karte](cards.de.md#live-karte) zeigt die Scheibe mit jedem Dart dort, wo er gelandet ist, neben der Anzeigetafel.
- **Bilder der Spieler:** [Verknüpfe die Spieler mit Personen](statistics.de.md#spieler-und-personen) von Home Assistant; Anzeigetafel, Spielauswahl und Ruhemodus zeigen ihre Bilder, und Spieler, die zu Hause sind, stehen vorn.
- **Licht und Ton:** Die [Lichtshow](automations.de.md#light-show) und der [Übungs-Caller](automations.de.md#practice-caller) reagieren auf dasselbe Spiel, mit den Lampen und Lautsprechern deines Zuhauses.
- **Mehrere Boards:** Jedes Board bekommt im automatischen Dashboard eine eigene Ansicht *Anzeigetafel*; für eine eigene Ansicht wählst du das Board im Editor der Karte.
- **Barrierefreiheit:** Die Anzeigetafel folgt deinem Theme mit Text, der in seinen Farben lesbar bleibt, meldet Screenreadern den Sieger, markiert den Spieler am Board, liest die Cricket-Marks als Wörter und die Herzen im Killer als Leben vor, behält den Fokus auf der Taste, die du gedrückt hast, und wünscht das Gerät reduzierte Bewegung, füllt sie den Turnierbaum ohne Gleiten und wechselt die Seiten des Ruhemodus ohne Überblendung. [Barrierefreiheit](cards.de.md#barrierefreiheit).

## Wenn etwas nicht passt

| Was du siehst | Was hilft |
| --- | --- |
| Darts werden nicht gezählt | Die Erkennung ist gestoppt: Der Status oben rechts zeigt *Erkennung gestoppt*. Der Start in der Spielauswahl schaltet sie ein; sonst schaltest du sie im [Board-Status](cards.de.md#board-status) oder in der Live-Karte ein. Prüfe außerdem, dass *Übungsspiel* nicht auf *Aus* steht und kein [Online-Match](online-matches.de.md) das Board belegt. |
| Der Bildschirm geht während eines Spiels aus | Im Vollbild lässt die Anzeigetafel den Bildschirm nur unter einer `https://`-Adresse an, im Browser wie in der Companion-App; sonst sagt sie das einmal. Schalte die automatische Bildschirmabschaltung des Tablets aus; siehe [Vollbild](#vollbild). |
| Der Caller bleibt stumm | Tippe nach jedem Neuladen der Seite einmal auf **Caller**: Browser spielen Ton erst nach einem Tippen ab. Prüfe die Lautstärke des Geräts. |
| Der Caller spricht trotz Voice-Pack mit der Stimme des Browsers | Der Name des Packs ist der Name seines Ordners in `homedarts/voices` des Medienordners, in derselben Groß- und Kleinschreibung. Ansagen, für die das Pack keine Datei hat, spricht immer der Browser; siehe die [Dateien eines Packs](#voice-packs). Dateien, die nach dem Einschalten des Callers kopiert wurden, zählen nach dem nächsten Tippen auf **Caller**. |
| Die Spielauswahl öffnet sich nicht | Sie öffnet sich nie in der Vorschau des Karteneditors und nicht mit `lobby: false`. |
| Nach einem Update zeigt der Bildschirm eine alte Version der Karte | Lade die Seite neu. In der Home-Assistant-App nutzt du *Einstellungen → Companion-App → Fehlerbehebung → Frontend-Cache zurücksetzen*. |
| Der Ruhemodus beginnt während eines Spiels | Der Ruhemodus wartet `idle_after` Sekunden ohne Darts und Tippen, und nur, wenn kein Spiel läuft oder das Spiel entschieden ist. Erhöhe `idle_after` oder setze `idle: false`. |
| Ein Tipp auf einen Dart bewirkt nichts | Der Dart gehört dem Bot, die Karte hat `corrections: false`, oder es ist die Vorschau des Karteneditors. |
| Das Tastenfeld erscheint nicht | Es braucht `keypad: true` in der Karte (im automatischen Dashboard: seine Einstellungen, *Ansicht Anzeigetafel*) und eingeschaltete *Übungsspiel manuelle Eingabe*, und es wartet, solange der Bot am Board ist. An einer [Dartscheibe ohne Autodarts](without-autodarts.de.md) erscheint es immer, außer die Karte setzt `keypad: false`. |
| OBS zeigt die Anmeldeseite von Home Assistant | Klicke die Browserquelle mit der rechten Maustaste an, wähle **Interagieren** und melde dich als Benutzer für OBS an; lass *Quelle herunterfahren, wenn nicht sichtbar* aus, damit sie angemeldet bleibt. |
| Das Overlay zeigt sich auf grünem Grund | Es steht auf `chroma`: Füge der Quelle in OBS den Filter **Chroma Key** mit der Keyfarbe hinzu, oder stelle es auf `transparent`. |
| OBS zeigt Home Assistant rund um das Overlay | Die Browserquelle von OBS vor Version 31 ist zu alt, um das Overlay über die Seite zu legen, die es dann in der Karte zeigt: Aktualisiere OBS. |
| Das Overlay verdeckt das Dashboard, und *Dashboard bearbeiten* ist nicht erreichbar | Öffne die Adresse der Ansicht mit `?edit=1` am Ende, etwa `http://homeassistant.local:8123/darts/overlay?edit=1`: Im Bearbeitungsmodus zeigt sich das Overlay in der Karte, die du dann bearbeiten oder löschen kannst. |
| Das Overlay zeigt nichts | Es läuft kein Spiel: Zwischen den Spielen überlässt das Overlay das Bild dem Stream. Starte ein Spiel, und das Board erscheint. |
| Kein Bild neben einem Namen | Der Spieler ist mit keiner Person verknüpft, oder die Person hat kein Bild. Siehe [Spieler und Personen](statistics.de.md#spieler-und-personen). |

Mehr Hilfe: [Fehlerbehebung](troubleshooting.de.md).
