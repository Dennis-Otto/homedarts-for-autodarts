---
description: "HomeDarts for Autodarts amène chaque fléchette dans Home Assistant : parties, tableau des scores, statistiques et automatisations. Local et gratuit, sans cloud."
hide:
  - navigation
  - toc
# The headline of the preview card of a shared link, under the name of the website
# (in one line, which markdownlint doesn't take for the title of the page).
social: { cards_layout_options: { title: "Votre cible Autodarts en direct dans Home Assistant" } }
---

# HomeDarts for Autodarts

![L'icône de l'intégration : une maison avec une cible de fléchettes](branding/icon.svg){ width="96" align="right" }

**Votre cible Autodarts en direct dans Home Assistant : locale, en temps réel et prête pour les automatisations.**

HomeDarts for Autodarts amène votre cible Autodarts dans Home Assistant : une fléchette apparaît une fraction de seconde après avoir touché la cible, directement depuis le Board Manager de votre réseau. Toute autre cible joue aussi, avec ses fléchettes saisies à la main ou envoyées par une Granboard. Jouez et entraînez-vous, placez un tableau des scores à côté de la cible, suivez vos statistiques et faites participer votre maison. Pas de compte, pas de cloud, pas d'identifiant client.

HomeDarts for Autodarts est un projet communautaire non officiel, sans lien avec Autodarts. Jusqu'à la version 1.18, il s'appelait Autodarts : [From Autodarts to HomeDarts](new-name.md) explique le nouveau nom et comment HomeDarts reprend vos cibles.

[:material-download: Installer avec HACS](https://my.home-assistant.io/redirect/hacs_repository/?owner=Dennis-Otto&repository=homedarts-for-autodarts&category=integration){ .md-button .md-button--primary } [:material-rocket-launch: Premiers pas](getting-started.fr.md){ .md-button } <a href="demo/index.html?lang=fr" class="md-button">:material-play-circle: Essayer en direct</a>

<picture>
  <source media="(max-width: 600px)" srcset="images/en/hero-mobile.webp">
  <img class="off-glb" src="images/en/hero.webp" alt="Animation : un match de 301 sur la carte en direct et le tableau des scores. Alex lance trois triples 20, les segments s'allument et le tableau des scores descend à 121 ; Sam marque 85 ; Alex finit 121 avec T20, bull extérieur et D18 pour le game shot">
</picture>

## Ce qu'elle fait

<div class="grid cards pictures" markdown>

- ![La carte en direct sur le tableau de bord de Home Assistant : la volée en cours, ses trois fléchettes, les dernières volées, la séance d'entraînement et la cible](images/en/dashboard-live.png){ loading=lazy }

    :material-lan-connect:{ .lg .middle } **Locale et en temps réel**

    ---

    Détectée automatiquement avec Board Manager 2 ; Board Manager 1 fonctionne aussi. Rien ne quitte votre réseau, sauf si vous utilisez la recherche de cibles ou le pont en ligne, et les secrets de la cible ne sont jamais enregistrés.

    [:octicons-arrow-right-24: How it works](how-it-works.md)

- ![Animation : un 180 sur le tableau des scores, avec une lueur dorée et des confettis](images/en/celebration.webp){ loading=lazy }

    :material-bullseye-arrow:{ .lg .middle } **Jeux**

    ---

    X01 de 101 à 1001 avec le chemin de finish après chaque fléchette, Cricket, Cut-Throat Cricket, Tactics, Wild Mouse, Random et Hidden Cricket, et neuf jeux de fête jusqu'à huit joueurs, seul ou en match jusqu'à quatre avec manches, sets, équipes et handicaps.

    [:octicons-arrow-right-24: Games and rules](games.md)

- ![Animation : Around the Clock sur la carte en direct ; chaque touche fait avancer la cible et entoure les segments du numéro suivant](images/en/training-game.webp){ loading=lazy }

    :material-target:{ .lg .middle } **Entraînement**

    ---

    Des séances d'entraînement qui commencent avec la première fléchette, huit jeux d'entraînement d'Around the Clock au JDC Challenge, un objectif quotidien, une série d'entraînement et des records personnels.

    [:octicons-arrow-right-24: Training games](games.md#training-games)

- ![Animation : une partie est choisie sur l'écran de nouvelle partie de la tablette à côté de la cible et commence sur le tableau des scores](images/en/lobby.webp){ loading=lazy }

    :material-monitor-dashboard:{ .lg .middle } **Tableau des scores et cartes**

    ---

    Un tableau des scores pour une tablette ou une télévision, aussi via Chromecast, lisible depuis la ligne de lancer, avec un écran de nouvelle partie, un annonceur et un mode veille. Sept cartes de tableau de bord et un tableau de bord automatique, en anglais, allemand, néerlandais, français et espagnol.

    [:octicons-arrow-right-24: Scoreboard at the board](scoreboard.md) · [Dashboard cards](cards.md)

- ![Animation : la carte de chaleur passe des segments aux numéros et aux positions réelles des fléchettes, puis aux fléchettes d'un seul joueur](images/en/heatmap-modes.webp){ loading=lazy }

    :material-chart-line:{ .lg .middle } **Statistiques avec cartes de chaleur**

    ---

    Moyenne sur 3 fléchettes, moyenne des 9 premières, taux de finish et de doubles, une carte de chaleur de chaque segment ou des positions réelles des fléchettes, et l'endroit où chaque joueur marque le plus par fléchette. Des profils de joueurs avec badges, des tendances hebdomadaires, un classement, un rapport hebdomadaire et un calendrier d'entraînement.

    [:octicons-arrow-right-24: Statistics and players](statistics.md)

- ![La galerie des meilleurs moments dans le navigateur multimédia de Home Assistant, avec des photos d'un finish et de deux grosses volées](images/en/media-gallery.png){ loading=lazy }

    :material-home-automation:{ .lg .middle } **Automatisations et blueprints**

    ---

    Des événements de la cible pour chaque fléchette, volée, retrait, bust, manche et match gagnés, le début et la fin de chaque partie. Seize blueprints : spectacle de lumière, musique d'entrée, affichage du score, annonceurs des fléchettes et de l'entraînement, photos des meilleurs moments, rapports, alertes, routines, parties lancées et fléchettes saisies à la voix, et réponses d'Assist sur vos fléchettes.

    [:octicons-arrow-right-24: Automations](automations.md)

- ![Animation : le tableau à élimination directe de cinq joueurs sur le tableau des scores, jusqu'à ce qu'Alex gagne la finale](images/en/tournament-bracket.webp){ loading=lazy }

    :material-tournament:{ .lg .middle } **Tournois et un bot**

    ---

    Des tournois de trois à 32 joueurs, en poule avec un classement, en élimination directe, en double élimination ou en groupes suivis d'une élimination directe, sur une cible ou sur plusieurs cibles à la fois, et un bot du niveau 20 au niveau 120 contre qui jouer au X01 et au Cricket.

    [:octicons-arrow-right-24: Tournaments](games.md#tournaments) · [The bot](games.md#playing-against-the-bot)

- ![Animation : des fléchettes saisies à la voix, avec Assist ouvert au-dessus du tableau des scores, qui répond avec le score restant](images/en/manual-voice.webp){ loading=lazy }

    :material-microphone:{ .lg .middle } **Voix**

    ---

    Dites « Lance 501 pour Alex et Sam » à Assist, en français, anglais, allemand, espagnol ou néerlandais, et la partie commence ; ensuite « Alex a fait 140 » ou « Triple 20 » saisit les fléchettes, comme sur une machine de fléchettes, et « Quelle est ma moyenne cette semaine ? » obtient sa réponse des statistiques de la cible. Toute partie démarre aussi avec une seule action d'une automatisation.

    [:octicons-arrow-right-24: Start a game by voice](automations.md#start-a-game-by-voice)

    [:octicons-arrow-right-24: Enter darts by voice](automations.md#enter-darts-by-voice)

    [:octicons-arrow-right-24: Ask Assist about your darts](automations.md#ask-assist-about-your-darts)

</div>

## De la fléchette à votre maison

Tout se passe dans votre réseau, en moins d'une seconde : le Board Manager nomme le segment, et Home Assistant l'affiche sur les cartes et le transmet à vos automatisations.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/en/dart-journey-dark.png">
  <img src="images/en/dart-journey-light.png" alt="Le parcours d'une fléchette : une fléchette se plante dans le triple 20. Les caméras de la cible la voient, et le Board Manager sur le PC de la cible nomme le segment. Un message en temps réel le transmet par votre réseau à HomeDarts dans Home Assistant, qui met à jour les entités, envoie les événements de la cible et allume le segment sur les cartes et le tableau des scores. Votre automatisation réagit aux événements, par exemple avec des lumières qui clignotent pour un 180 ou un annonceur. Le tout prend moins d'une seconde et n'a pas besoin du cloud" width="560">
</picture>

[:octicons-arrow-right-24: How it works](how-it-works.md)

## En comparaison

Par rapport à l'application Autodarts avec l'extension Tools for Autodarts, à darts-caller et darts-wled, et aux autres intégrations Home Assistant pour Autodarts :

- **Sans cloud :** HomeDarts parle à l'interface locale du Board Manager et n'a besoin d'aucun compte Autodarts.
- **Entités et événements dans Home Assistant :** un événement pour chaque fléchette, volée, retrait, bust, manche et match, et seize blueprints qui en font quelque chose tout de suite.
- **Statistiques à la maison :** moyennes, cartes de chaleur, profils et un an d'historique, enregistrés dans Home Assistant.
- **Même sans cible Autodarts :** sur un pavé numérique ou avec une Granboard via Bluetooth *(expérimental)*.
- **Gratuit :** open source sous licence MIT, sans version payante.

[Coming from another tool](coming-from.md) compare tout, avec les sources, et montre comment changer *(en anglais)*.

## Guides

- :material-rocket-launch: [**De zéro au tableau des scores**](getting-started.fr.md) : Home Assistant, HACS, l'intégration et la première partie, pour les joueurs d'Autodarts qui découvrent Home Assistant
- :material-download: [**Installation et configuration**](installation.fr.md) : la configuration requise, HACS ou à la main, et les façons d'ajouter une cible
- :material-frequently-asked-questions: [**Questions fréquentes**](faq.fr.md) : le compte, les appareils, le jeu en ligne, la confidentialité, plusieurs cibles, les écrans, les langues et les mises à jour

En anglais :

- :material-pencil: [**Play without Autodarts**](without-autodarts.md) : n'importe quelle cible, avec tous les jeux, l'entraînement et les statistiques, les fléchettes saisies sur un pavé numérique
- :material-bluetooth: [**Granboard over Bluetooth**](granboard.md) : les fléchettes d'une Granboard via le Bluetooth de Home Assistant et les proxys ESPHome *(expérimental)*
- :material-swap-horizontal: [**Coming from another tool**](coming-from.md) : les autres intégrations, les ponts MQTT, darts-caller, darts-wled et Tools for Autodarts comparés, et comment changer
- :material-rename-box: [**From Autodarts to HomeDarts**](new-name.md) : le nouveau nom depuis la version 2.0, et comment HomeDarts reprend vos cibles
- :material-bullseye-arrow: [**Games and rules**](games.md) : chaque jeu en un coup d'œil, quatre façons d'en lancer un, les matchs, les équipes, les handicaps, le bull-off et les tournois
- :material-television: [**Scoreboard at the board**](scoreboard.md) : une tablette ou une télévision à côté de la cible, en paysage et en portrait, l'écran de nouvelle partie, l'annonceur et le mode veille
- :material-chart-line: [**Statistics and players**](statistics.md) : les séances, les records personnels, les cartes de chaleur, où viser, les progrès, les profils, les succès et le classement
- :material-home-automation: [**Automations**](automations.md) : seize blueprints, leurs réglages, les événements de la cible et des exemples prêts à l'emploi
- :material-play-network: [**Online matches**](online-matches.md) : les busts, manches et matchs gagnés des matchs en ligne comme événements de la cible, avec Tools for Autodarts *(expérimental)*

## Référence

<div class="grid cards" markdown>

- :material-view-dashboard:{ .lg .middle } [**Dashboard cards**](cards.md)

    ---

    Les sept cartes et le tableau de bord automatique, avec chaque option et l'accessibilité.

- :material-format-list-bulleted:{ .lg .middle } [**Entities and events**](entities.md)

    ---

    Chaque entité, événement de la cible, état, attribut et action, et la génération du Board Manager qui les fournit.

- :material-cog-transfer:{ .lg .middle } [**How it works**](how-it-works.md)

    ---

    L'architecture, les intervalles de mise à jour, le comportement de la connexion, l'entraînement et les records, les données enregistrées et la confidentialité.

- :material-lifebuoy:{ .lg .middle } [**Troubleshooting**](troubleshooting.md)

    ---

    Les messages de configuration, les réparations, les entités indisponibles, les actions qui échouent, les diagnostics et les journaux.

- :material-shield-lock:{ .lg .middle } [**Security design**](security.md)

    ---

    Ce qui est protégé, les limites de confiance, les menaces et les contre-mesures.

- :material-book-alphabet:{ .lg .middle } [**Glossary**](glossary.md)

    ---

    Les mots des fléchettes et de cette intégration.

</div>

Ce que chaque version a apporté se trouve dans le [journal des modifications](changelog.md), ce qui vient ensuite dans la [feuille de route](roadmap.md). Pour les vidéos, les articles et les publications, le [kit des créateurs](creator-kit.md) contient des faits, des textes prêts à publier, des vidéos et des images, libres d'utilisation.

## Appareils pris en charge

- **Board Manager 2 :** Autodarts 2 sans écran (headless), testé jusqu'à la version 2.0.2 et détecté automatiquement.
- **Board Manager 1 :** l'application classique, testée avec la version 1.0.7.
- **Autodarts Desktop** sous Linux fonctionne, selon un joueur ; Autodarts Desktop sous Windows et les appareils de Winmau comme Autodarts X n'ont pas encore été testés.
- **Home Assistant** 2026.8 ou plus récent.
- **Sans Autodarts :** n'importe quelle cible, avec les fléchettes saisies sur un pavé numérique.

Tout matériel qui fait tourner le Board Manager d'Autodarts fonctionne, car l'intégration parle au Board Manager et non aux caméras. [Supported devices](README.md#supported-devices) contient le tableau complet. Votre installation n'y figure pas ? Un [rapport de compatibilité](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new?template=board_compatibility.yml) nous aide, même quand tout fonctionne.

## Langues

L'intégration parle français, anglais, allemand, néerlandais et espagnol : la configuration, les options, les entités et leurs états, les actions, les messages et les réparations, les cartes avec leurs éditeurs et l'annonceur du tableau des scores. Elle suit la langue de Home Assistant ; une variante régionale comme `fr-CA` compte comme sa langue.

Ce site est en anglais et en allemand, et l'accueil, le démarrage rapide, l'installation et les questions fréquentes existent aussi en néerlandais, en français et en espagnol. Il montre les autres pages en anglais. Vous parlez français ? [Aidez-nous à traduire](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/481) : corrigez une phrase ou traduisez une page qui vous manque, directement sur GitHub, sans programmer.
