---
description: "Kurze Antworten zu HomeDarts for Autodarts: Konto, Geräte, Online-Spiel, Datenschutz, mehrere Boards, Bildschirme, Sprachen, Updates, neuer Name und Umstieg."
---

# Häufige Fragen

[← Dokumentation](README.de.md) · [English](faq.md)

Kurze Antworten, jede mit der Seite, die die Einzelheiten hat. Deine Frage fehlt? Stell sie in den [GitHub Discussions](https://github.com/Dennis-Otto/homedarts-for-autodarts/discussions), gern auf Deutsch.

**Schnell zu:** [Bevor du anfängst](#bevor-du-anfängst) · [Spielen](#spielen) · [Bildschirme und Sprachen](#bildschirme-und-sprachen) · [Datenschutz](#datenschutz) · [Updates und Umstieg](#updates-und-umstieg)

## Bevor du anfängst

### Brauche ich ein Autodarts-Konto oder ein Abo?

Nein. Die Integration spricht über dein eigenes Netzwerk mit dem Board Manager auf deinem Board-PC, auf TCP-Port 3180. Sie braucht keine Autodarts-Anmeldung, kein Passwort, keinen API-Schlüssel und kein Abo wie Autodarts Plus, und sie ändert nie die Registrierung deines Boards bei Autodarts. Eine Dartscheibe ohne Autodarts braucht gar nichts von Autodarts. [Voraussetzungen](installation.de.md#voraussetzungen)

### Was brauche ich?

Home Assistant ab 2026.8 mit [HACS](https://hacs.xyz) und ein Autodarts-Board in deinem Netzwerk oder eine beliebige Dartscheibe, deren Darts du auf einem Tastenfeld eingibst. Neu bei Home Assistant? [Von null bis zur Anzeigetafel](getting-started.de.md) führt dich vom Nichts zum ersten Spiel auf der Anzeigetafel.

### Funktioniert es mit Autodarts Desktop, Autodarts X oder Lens?

Die Integration braucht einen Board Manager, den Home Assistant in deinem Netzwerk erreicht. Board Manager 2 ist bis 2.0.2 getestet, der klassische Board Manager 1 funktioniert auch, und laut dem Bericht eines Spielers läuft Autodarts Desktop 2.0.2 unter Linux. Autodarts Desktop unter Windows und Autodarts X sind noch nicht getestet. Ein [Kompatibilitätsbericht](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new?template=board_compatibility.yml) sagt uns, wie es mit deinem läuft, ob es klappt oder nicht. [Unterstützte Geräte](README.de.md#unterstützte-geräte)

Lens zählt mit der Kamera eines Handys oder Tablets in der Autodarts-App, ohne Board Manager in deinem Netzwerk, deshalb kann die Integration seine Darts nicht lesen. Gib sie stattdessen auf dem Tastenfeld ein. Eine Verbindung über die Autodarts-Cloud kommt auch nicht: Autodarts vergibt keine Client-IDs an Integrationen von Dritten ([Entscheidung 0025](decisions/0025-no-cloud-link.md), auf Englisch). [Spielen ohne Autodarts](without-autodarts.de.md)

### Kostet es etwas?

Nein. Die Integration ist kostenlos und quelloffen unter der [MIT-Lizenz](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/LICENSE), ohne etwas zu bezahlen und ohne kostenpflichtige Version. [Sponsoring](https://github.com/sponsors/Dennis-Otto) hilft dem Projekt und ist ganz freiwillig.

### Ist das eine offizielle Autodarts-Integration?

Nein. HomeDarts for Autodarts ist ein inoffizielles Community-Projekt ohne Verbindung zu Autodarts, gepflegt von [@Dennis-Otto](https://github.com/Dennis-Otto). Es nutzt die lokale Schnittstelle des Board Managers, die das Autodarts-Team offen hält. Bis Version 1.18 hieß es Autodarts, bis Autodarts um einen eigenen Namen gebeten hat. [Von Autodarts zu HomeDarts](new-name.de.md) · [Herkunft und Lizenz](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/docs/README.de.md#herkunft-und-lizenz)

## Spielen

### Ich habe kein Autodarts-Board. Kann ich sie nutzen?

Ja. Richte eine Dartscheibe ohne Autodarts ein und gib jeden Dart auf dem Tastenfeld der Anzeigetafel oder per Sprache ein. Alle Spiele, das Training und die Statistik funktionieren. Bekommt deine Dartscheibe später Autodarts, behält sie die Spiele, die Spieler und die Statistik. [Spielen ohne Autodarts](without-autodarts.de.md)

### Kann ich online spielen?

Ja, wie bisher auf play.autodarts.io. Die Integration sieht dabei die Darts auf deinem eigenen Board: `dart_detected`, `visit_thrown` und die Entnahme kommen wie gewohnt an. Überwerfen, gewonnene Legs und Matches passieren im Browser; die optionale Online-Brücke bringt sie mit der Browser-Erweiterung Tools for Autodarts nach Home Assistant *(experimentell)*. [Online-Matches](online-matches.de.md)

### Das Board hat einen Dart falsch erkannt. Wie korrigiere ich ihn?

Tippe den Dart auf der Anzeigetafel an und wähle, wo er gelandet ist, auf den Tasten oder auf einem Bild des Boards. In Automationen macht `homedarts.correct_dart` dasselbe, und `homedarts.undo_visit` nimmt die letzte Aufnahme zurück. [Darts korrigieren und eingeben](scoreboard.de.md#darts-korrigieren-und-eingeben)

### Kann ich mehrere Boards nutzen?

Ja. Jedes Board ist ein eigener Eintrag und ein eigenes Gerät, mit eigenen Entitäten, Spielen und Statistiken, und das automatische Dashboard gibt jedem Board seine Ansichten, etwa `/scoreboard-1` und `/scoreboard-2`. Die Aktionen der Integration brauchen dann die `config_entry_id` des Boards. [Mehrere Boards](without-autodarts.de.md#mehrere-boards)

Ein Vereinsabend kann auch [ein Turnier auf mehreren Boards zugleich](games.de.md#ein-turnier-auf-mehreren-boards) spielen, jedes Board mit einem eigenen Match.

Wer auf zwei Boards wirft, hat auf jedem ein Profil. [`homedarts.restore`](entities.de.md#backup-wiederherstellen-homedartsrestore) mit `mode: merge` fügt das Backup eines Boards dem anderen hinzu, und die Zahlen des Spielers addieren sich. [Backups](statistics.de.md#backups)

## Bildschirme und Sprachen

### Kann ich die Anzeigetafel auf einem Fernseher oder einem Fire-Tablet zeigen?

Ja: auf jedem Bildschirm, dessen Browser dein Home Assistant öffnet, etwa einem Tablet an der Wand, auch einem Fire-Tablet, einem Fernseher mit Browser, einem kleinen PC oder einem alten Handy. Installieren musst du darauf nichts. Gib dem Bildschirm einen eigenen Home-Assistant-Benutzer und öffne die Ansicht *Anzeigetafel* des automatischen Dashboards, im Vollbild oder in einem Kiosk-Browser. Ein Fernseher mit Chromecast oder ein Google Nest Hub zeigt sie über Home Assistant Cast, ohne eigenen Browser. [Den Bildschirm einrichten](scoreboard.de.md#den-bildschirm-einrichten) · [Home Assistant Cast](scoreboard.de.md#auf-dem-fernseher-mit-home-assistant-cast)

### Welche Sprachen spricht sie, und welche Stimmen hat der Caller?

Englisch, Deutsch, Niederländisch, Französisch und Spanisch, in der Sprache von Home Assistant: Einrichtung, Entitäten, Karten und Caller. Der Caller der Anzeigetafel spricht mit einer Stimme des Browsers am Bildschirm für diese Sprache oder mit den aufgenommenen Sounds eines Voice-Packs, etwa eines von darts-caller oder eines, das du mit Piper aufnimmst. Die Blueprints Dart caller und Practice caller sprechen in der Sprache von Home Assistant, über die Sprachausgabe und die Lautsprecher deines Home Assistant. [Sprachen](README.de.md#sprachen) · [Welcher Caller?](automations.de.md#welcher-caller)

## Datenschutz

### Was verlässt mein Netzwerk?

Im lokalen Betrieb nichts. Nur was du wählst, spricht mit dem Internet: Die Board-Suche fragt einmal den öffentlichen Suchdienst von Autodarts, und die Online-Brücke nimmt nur die Aufrufe von Tools for Autodarts an. Geheimnisse des Boards werden nie gespeichert, und die Diagnosedaten schwärzen Board-IDs, Adressen und Spielernamen. Manche Browser sprechen die Ansagen der Anzeigetafel mit Online-Stimmen; eine Offline-Stimme des Geräts hält sie zu Hause. [Datenschutz](how-it-works.de.md#datenschutz) · [Sicherheit](security.de.md)

### Wo liegt meine Statistik?

Im eigenen Speicher von Home Assistant, nie in der Cloud: die Trainingssessions, das Übungsspiel, die Bestleistungen, die Spielerprofile mit ihren Matches und der Trainingskalender mit einem Jahr an Sessions und Matches. Löschst du das Board, wird all das nach einem [Backup](statistics.de.md#backups) gelöscht, und [`homedarts.export`](entities.de.md#trainingsdaten-exportieren-homedartsexport) schreibt es für eine Tabellenkalkulation heraus. [Gespeicherte Daten](how-it-works.de.md#gespeicherte-daten)

### Ich habe mein Board gelöscht. Ist meine Statistik weg?

Nein. Bevor ein Board gelöscht wird, schreibt HomeDarts ein Backup von allem, was es gespeichert hat, nach `homedarts/backups` im Medienordner. Füge das Board wieder hinzu, und die Reparatur *Ein Backup von … ist vorhanden* holt alles zurück; [`homedarts.restore`](entities.de.md#backup-wiederherstellen-homedartsrestore) stellt jedes Backup wieder her. [Backups](statistics.de.md#backups)

## Updates und Umstieg

### Wie aktualisiere ich den Board Manager?

Auf dem Board-PC, wie Autodarts es beschreibt. Home Assistant sagt dir, wann ein Update ansteht: Mit Board Manager 2 zeigt die Update-Entität *Software* die installierte und die neueste Version, und ein Board mit Board Manager 1 bekommt eine Reparaturmeldung für den Umstieg auf Board Manager 2. Die Integration selbst aktualisierst du über HACS. [Auf Board Manager 2 umsteigen](installation.de.md#von-board-manager-1-auf-board-manager-2-umsteigen) · [Zustand und Verbindungen](entities.de.md#zustand-und-verbindungen)

### Die Integration hieß Autodarts. Was ändert sich für mich?

Seit Version 2.0 heißt sie HomeDarts for Autodarts, mit der Domain `homedarts`. Füge nach dem Update **HomeDarts for Autodarts** hinzu und wähle **Boards der Integration Autodarts übernehmen**: Deine Boards behalten ihre Entitäten, ihren Verlauf, ihre Statistiken und Dashboards. Automationen und Skripte, die die alten Aktionen aufrufen, etwa `autodarts.start_game`, brauchen die neuen Namen, etwa `homedarts.start_game`; eine Reparatur listet sie auf. [Von Autodarts zu HomeDarts](new-name.de.md)

### Ich nutze das ursprüngliche HACSAutodarts. Wie steige ich um?

Installiere HomeDarts daneben: HACSAutodarts hat die Domain `autodarts`, HomeDarts die Domain `homedarts`, deshalb laufen beide gleichzeitig. Füge dein Board in HomeDarts hinzu, stell deine Automationen um, lösche dann den Eintrag von HACSAutodarts und entferne es in HACS. HomeDarts übernimmt diesen Eintrag nicht. [Von der ursprünglichen Integration umsteigen](installation.de.md#von-der-ursprünglichen-integration-umsteigen)

### Ich nutze ein anderes Autodarts-Werkzeug. Wie steige ich um?

[Umstieg von anderen Werkzeugen](coming-from.de.md) behandelt Autodarts Local, die anderen Home-Assistant-Integrationen, MQTT-Brücken, darts-caller und darts-wled sowie Tools for Autodarts: was jedes bietet, welche Entitäten, Ereignisse und Blueprints seinen Platz einnehmen und wie du umsteigst, während es installiert bleibt. HomeDarts hat eine eigene Domain, deshalb muss keines davon vorher gehen.

### Etwas funktioniert nicht. Wo bekomme ich Hilfe?

Die [Fehlerbehebung](troubleshooting.de.md) erklärt die Meldungen, Reparaturen und Diagnosedaten. Fragen stellst du in den [GitHub Discussions](https://github.com/Dennis-Otto/homedarts-for-autodarts/discussions), gern auf Deutsch, und Fehler meldest du als [Issue](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new/choose), mit den Diagnosedaten deines Boards; [SUPPORT.md](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/SUPPORT.md) erklärt, wo du was fragst.
