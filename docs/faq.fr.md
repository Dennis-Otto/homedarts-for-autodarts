---
description: "Réponses courtes sur HomeDarts for Autodarts : compte, appareils, jeu en ligne, confidentialité, plusieurs cibles, écrans, langues, mises à jour et migration."
---

# Questions fréquentes

[← Documentation](README.md) · [English](faq.md)

Des réponses courtes, chacune avec la page qui donne les détails ; ces pages sont le plus souvent en anglais. Votre question manque ? Posez-la dans les [GitHub Discussions](https://github.com/Dennis-Otto/homedarts-for-autodarts/discussions).

**Aller à :** [Avant de commencer](#avant-de-commencer) · [Jouer](#jouer) · [Écrans et langues](#écrans-et-langues) · [Confidentialité](#confidentialité) · [Mises à jour et migration](#mises-à-jour-et-migration)

## Avant de commencer

### Ai-je besoin d'un compte Autodarts ou d'un abonnement ?

Non. L'intégration parle au Board Manager sur le PC de votre cible, via votre propre réseau, sur le port TCP 3180. Elle n'a besoin d'aucun identifiant Autodarts, mot de passe ni clé d'API, ni d'aucun abonnement comme Autodarts Plus, et elle ne modifie jamais l'enregistrement de votre cible auprès d'Autodarts. Une cible sans Autodarts n'a besoin de rien d'Autodarts. [Configuration requise](installation.fr.md#configuration-requise)

### De quoi ai-je besoin ?

Home Assistant 2026.8 ou plus récent avec [HACS](https://hacs.xyz), et une cible Autodarts sur votre réseau ou n'importe quelle cible dont vous saisissez les fléchettes sur un pavé numérique. Vous découvrez Home Assistant ? [De zéro au tableau des scores](getting-started.fr.md) vous mène de zéro jusqu'à la première partie sur le tableau des scores.

### Est-ce que cela fonctionne avec Autodarts Desktop, Autodarts X ou Lens ?

L'intégration a besoin d'un Board Manager que Home Assistant atteint sur votre réseau. Board Manager 2 est testé jusqu'à la version 2.1.0, le Board Manager 1 classique fonctionne aussi, et un joueur signale qu'Autodarts Desktop 2.0.2 sous Linux fonctionne. Autodarts Desktop sous Windows et Autodarts X n'ont pas encore été testés. Un [rapport de compatibilité](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new?template=board_compatibility.yml) nous dit comment cela se passe avec le vôtre, que cela fonctionne ou non. [Appareils pris en charge](index.fr.md#appareils-pris-en-charge)

Lens compte les points avec la caméra d'un téléphone ou d'une tablette dans l'application Autodarts, sans Board Manager sur votre réseau, donc l'intégration ne peut pas lire ses fléchettes. Saisissez-les plutôt sur le pavé numérique. Un lien via le cloud d'Autodarts ne viendra pas non plus : Autodarts ne délivre pas d'identifiants client aux intégrations tierces ([décision 0025](decisions/0025-no-cloud-link.md)). [Play without Autodarts](without-autodarts.md)

### Est-ce que cela coûte quelque chose ?

Non. L'intégration est gratuite et open source sous [licence MIT](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/LICENSE) : il n'y a rien à payer et pas de version payante. [Le parrainage](https://github.com/sponsors/Dennis-Otto) aide le projet et reste entièrement facultatif.

### Est-ce une intégration officielle d'Autodarts ?

Non. HomeDarts for Autodarts est un projet communautaire non officiel, sans lien avec Autodarts, maintenu par [@Dennis-Otto](https://github.com/Dennis-Otto). Il utilise l'interface locale du Board Manager, que l'équipe d'Autodarts laisse ouverte. Jusqu'à la version 1.18, il s'appelait Autodarts ; Autodarts a ensuite demandé au projet de prendre un autre nom. [From Autodarts to HomeDarts](new-name.md) · [Credits and license](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/README.md#credits-and-license)

## Jouer

### Je n'ai pas de cible Autodarts. Puis-je l'utiliser ?

Oui. Configurez une cible sans Autodarts et saisissez chaque fléchette sur le pavé numérique du tableau des scores, ou à la voix. Tous les jeux, l'entraînement et les statistiques fonctionnent. Si votre cible reçoit Autodarts plus tard, elle garde les parties, les joueurs et les statistiques. [Play without Autodarts](without-autodarts.md)

### Puis-je jouer des matchs en ligne ?

Oui, sur play.autodarts.io comme avant. L'intégration voit alors les fléchettes de votre propre cible : `dart_detected`, `visit_thrown` et le retrait arrivent comme d'habitude. Les busts, les manches et les matchs gagnés se passent dans le navigateur ; la passerelle en ligne facultative les amène dans Home Assistant avec l'extension de navigateur Tools for Autodarts *(expérimental)*. [Online matches](online-matches.md)

### Plusieurs joueurs avec leur propre compte Autodarts sur un seul écran ?

Oui, en ligne sur play.autodarts.io : l'extension Chrome [Player Switch for Autodarts](https://dennis-otto.github.io/player-switch-for-autodarts/), de l'auteur de cette intégration, garde le compte de chacun prêt, et un appui sur une tuile change de joueur, sans se connecter. Elle n'a pas besoin de Home Assistant, et l'intégration voit les fléchettes de votre cible, quel que soit le compte connecté. [Online matches](online-matches.md#several-accounts-at-one-display)

### La cible a mal lu une fléchette. Comment la corriger ?

Touchez la fléchette sur le tableau des scores et choisissez où elle s'est plantée, sur les touches ou sur une image de la cible. Dans les automatisations, `homedarts.correct_dart` fait la même chose, et `homedarts.undo_visit` annule la dernière volée. [Correct and enter darts](scoreboard.md#correct-and-enter-darts)

### Puis-je utiliser plusieurs cibles ?

Oui. Chaque cible est une entrée et un appareil à part, avec ses propres entités, parties et statistiques, et le tableau de bord automatique donne à chaque cible ses vues, comme `/scoreboard-1` et `/scoreboard-2`. Les actions de l'intégration ont alors besoin du `config_entry_id` de la cible. [Several boards](without-autodarts.md#several-boards)

Lors d'une soirée de club, vous pouvez aussi jouer [un tournoi sur plusieurs cibles à la fois](games.md#a-tournament-on-several-boards), chaque cible avec son propre match.

Un joueur qui lance sur deux cibles a un profil sur chacune. [`homedarts.restore`](entities.md#restore-a-backup-homedartsrestore) avec `mode: merge` ajoute la sauvegarde d'une cible à l'autre, et les chiffres du joueur s'additionnent. [Backups](statistics.md#backups)

## Écrans et langues

### Puis-je afficher le tableau des scores sur une télévision ou une tablette Fire ?

Oui : sur n'importe quel écran dont le navigateur ouvre votre Home Assistant, comme une tablette au mur, une tablette Fire comprise, une télévision avec un navigateur, un petit PC ou un vieux téléphone. Il n'y a rien à installer dessus. Donnez à l'écran son propre utilisateur Home Assistant et ouvrez la vue *Tableau des scores* du tableau de bord automatique, en plein écran ou dans un navigateur kiosque. Une télévision avec un Chromecast ou un Google Nest Hub l'affiche par Home Assistant Cast, sans navigateur propre. [Set up the screen](scoreboard.md#set-up-the-screen) · [Home Assistant Cast](scoreboard.md#on-a-tv-with-home-assistant-cast)

### Quelles langues parle-t-elle, et quelles voix a l'annonceur ?

Le français, l'anglais, l'allemand, le néerlandais et l'espagnol, selon la langue de Home Assistant : la configuration, les entités, les cartes et l'annonceur. L'annonceur du tableau des scores parle avec une voix du navigateur de l'écran pour cette langue, ou avec les sons enregistrés d'un pack de voix, comme un pack de darts-caller ou un pack que vous enregistrez avec Piper. Les blueprints de l'annonceur des fléchettes et de l'annonceur d'entraînement parlent dans la langue de Home Assistant, par la synthèse vocale et les haut-parleurs de votre Home Assistant. [Langues](index.fr.md#langues) · [Which caller?](automations.md#which-caller)

## Confidentialité

### Qu'est-ce qui quitte mon réseau ?

Rien, en mode local. Seul ce que vous choisissez communique avec internet : la recherche de cibles interroge une fois le service de découverte public d'Autodarts, et la passerelle en ligne ne reçoit que les appels de Tools for Autodarts. Les secrets de la cible ne sont jamais enregistrés, et les diagnostics masquent les identifiants de cible, les adresses et les noms des joueurs. Certains navigateurs prononcent les annonces du tableau des scores avec des voix en ligne ; une voix hors ligne de l'appareil les garde à la maison. [Privacy](how-it-works.md#privacy) · [Security design](security.md)

### Où sont gardées mes statistiques ?

Dans le stockage propre de Home Assistant, jamais dans le cloud : les sessions d'entraînement, la partie, les records personnels, les profils des joueurs avec leurs matchs, et le calendrier d'entraînement avec un an de sessions et de matchs. Supprimer la cible les supprime, après une [sauvegarde](statistics.md#backups), et [`homedarts.export`](entities.md#export-training-data-homedartsexport) les exporte pour un tableur. [Stored data](how-it-works.md#stored-data)

### J'ai supprimé ma cible. Mes statistiques ont-elles disparu ?

Non. Avant qu'une cible soit supprimée, HomeDarts écrit une sauvegarde de tout ce qu'il a enregistré dans `homedarts/backups` du dossier multimédia. Ajoutez la cible à nouveau, et la réparation *Une sauvegarde de … est disponible* ramène tout ; [`homedarts.restore`](entities.md#restore-a-backup-homedartsrestore) restaure n'importe quelle sauvegarde. [Backups](statistics.md#backups)

## Mises à jour et migration

### Comment mettre à jour le Board Manager ?

Sur le PC de la cible, comme Autodarts le décrit. Home Assistant vous prévient quand une mise à jour est disponible : avec Board Manager 2, l'entité de mise à jour *Logiciel* affiche la version installée et la dernière, et une cible sous Board Manager 1 reçoit un avis de réparation pour passer à Board Manager 2. L'intégration elle-même se met à jour par HACS. [Update to Board Manager 2](installation.md#update-from-board-manager-1-to-board-manager-2) · [Health and connections](entities.md#health-and-connections)

### L'intégration s'appelait Autodarts. Qu'est-ce qui change pour moi ?

Depuis la version 2.0, elle s'appelle HomeDarts for Autodarts, avec le domaine `homedarts`. Après la mise à jour, ajoutez **HomeDarts for Autodarts** et choisissez **Reprendre les cibles de l'intégration Autodarts** : vos cibles gardent leurs entités, leur historique, leurs statistiques et leurs tableaux de bord. Les automatisations et les scripts qui appellent les anciennes actions, comme `autodarts.start_game`, ont besoin des nouveaux noms, comme `homedarts.start_game` ; une réparation les liste. [From Autodarts to HomeDarts](new-name.md)

### J'utilise le HACSAutodarts d'origine. Comment passer à HomeDarts ?

Installez HomeDarts à côté : l'original a le domaine `autodarts`, HomeDarts le domaine `homedarts`, donc les deux tournent en même temps. Ajoutez votre cible à HomeDarts, déplacez vos automatisations, puis supprimez l'entrée de HACSAutodarts et retirez-le dans HACS. HomeDarts ne reprend pas cette entrée. [Switch from the original integration](installation.md#switch-from-the-original-integration)

### J'utilise un autre outil pour Autodarts. Comment passer à HomeDarts ?

[Coming from another tool](coming-from.md) couvre Autodarts Local, les autres intégrations Home Assistant, les passerelles MQTT, darts-caller et darts-wled, et Tools for Autodarts : ce que chacun offre, les entités, les événements et les blueprints qui prennent sa place, et comment passer à HomeDarts pendant qu'il reste installé. HomeDarts a son propre domaine, donc inutile d'en retirer un d'abord.

### Quelque chose ne fonctionne pas. Où trouver de l'aide ?

[Troubleshooting](troubleshooting.md) explique les messages, les réparations et les diagnostics. Posez vos questions dans les [GitHub Discussions](https://github.com/Dennis-Otto/homedarts-for-autodarts/discussions) et signalez les bogues dans un [ticket](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new/choose), avec les diagnostics de votre cible ; [SUPPORT.md](https://github.com/Dennis-Otto/homedarts-for-autodarts/blob/main/SUPPORT.md) explique où poser quelle question.
