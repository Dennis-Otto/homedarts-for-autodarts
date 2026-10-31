---
description: "Installez HomeDarts for Autodarts avec HACS et ajoutez votre cible par son adresse dans votre réseau. Sans identifiant Autodarts, mot de passe ni clé d'API."
---

# Installation et configuration

[← Documentation](README.md) · [English](installation.md)

Cette page décrit l'installation et l'ajout d'une cible. La reconfiguration, le passage à Board Manager 2, la mise à jour depuis la version 1.x, le passage depuis l'intégration d'origine et la suppression sont sur la [page en anglais](installation.md#reconfigure).

## Configuration requise

| Élément | Détails |
| --- | --- |
| Home Assistant | **2026.8** ou plus récent ([pourquoi 2026.8](decisions/0022-home-assistant-2026-8-as-the-oldest-release.md), en anglais) |
| Cible Autodarts | Installée et en état de marche dans le Board Manager d'Autodarts : **Board Manager 2**, Autodarts 2 sans écran (headless, recommandé, testé jusqu'à la version 2.0.2), ou le **Board Manager 1** classique. Selon un joueur, **Autodarts Desktop** 2.0.2 sous Linux fonctionne aussi. Autodarts Desktop sous Windows et les **appareils de Winmau** comme Autodarts X ou Lens n'ont pas encore été testés ; [dites-nous](https://github.com/Dennis-Otto/homedarts-for-autodarts/issues/new?template=board_compatibility.yml) comment cela se passe avec le vôtre |
| Réseau | Home Assistant atteint le PC de la cible sur le réseau local, par défaut sur le port TCP **3180** |
| Sans Autodarts | N'importe quelle cible : vous saisissez les fléchettes sur un pavé numérique, voir [Play without Autodarts](without-autodarts.md) ; il ne faut alors ni PC pour la cible ni réseau jusqu'à elle |

L'intégration n'a besoin d'**aucun identifiant Autodarts, mot de passe ni clé d'API**. Elle ne modifie jamais l'enregistrement de votre cible auprès d'Autodarts. Elle n'a pas non plus de lien avec le cloud d'Autodarts : Autodarts ne délivre pas d'identifiants client aux intégrations tierces ([décision 0025](decisions/0025-no-cloud-link.md), en anglais).

## Installer

### Avec HACS (recommandé)

[![Ouvrez votre Home Assistant et affichez ce dépôt dans HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=Dennis-Otto&repository=homedarts-for-autodarts&category=integration)

1. Sélectionnez le bouton ci-dessus, ou ouvrez **HACS** dans Home Assistant, recherchez **HomeDarts** et ouvrez-la.
2. Sélectionnez **Download**.
3. Redémarrez Home Assistant.

HACS présente les nouvelles versions comme une mise à jour dans **Paramètres → Mises à jour**. La fenêtre de mise à jour affiche les notes de version. HACS installe le paquet de version signé `homedarts.zip`, le même fichier que pour une [installation manuelle](#manuellement).

L'intégration fait partie des dépôts par défaut de HACS depuis le 20 octobre 2026 ([hacs/default#11306](https://github.com/hacs/default/pull/11306)). Si vous l'aviez ajoutée avant comme dépôt personnalisé, vous n'avez rien à faire : HACS ne la liste plus parmi les dépôts personnalisés et garde votre installation et ses mises à jour.

Vous voulez tester les bêtas ? [Betas for testers](installation.md#betas-for-testers) explique comment HACS les propose.

### Manuellement

1. Téléchargez `homedarts.zip` de la dernière version sur [GitHub](https://github.com/Dennis-Otto/homedarts-for-autodarts/releases). Il contient les fichiers de l'intégration, sans dossier autour.
2. Créez le dossier `custom_components/homedarts` dans votre configuration de Home Assistant et décompressez-y le fichier. Le résultat est `config/custom_components/homedarts/manifest.json`.
3. Redémarrez Home Assistant.

Le workflow de publication signe chaque paquet : `gh attestation verify homedarts.zip --repo Dennis-Otto/homedarts-for-autodarts` vérifie avec la GitHub CLI qu'il a été construit à partir de ce dépôt, voir [signed release packages](releases.md#signed-release-packages).

## Ajouter votre cible

[![Ouvrez votre Home Assistant et commencez à configurer HomeDarts for Autodarts.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=homedarts)

Il y a trois façons d'ajouter une cible Autodarts. Toutes aboutissent à la même cible, entièrement locale. Une quatrième ajoute une [cible sans Autodarts](#4-une-cible-sans-autodarts).

Quelle façon convient à votre cible :

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="images/en/add-board-dark.png">
  <img src="images/en/add-board-light.png" alt="Which way to add a board: a dartboard without Autodarts gets the fourth way, Dartboard without Autodarts, and its darts are entered on the keypad. An Autodarts board with Board Manager 2 usually appears by itself as Autodarts board found under Discovered: select Add and confirm. Otherwise, enter the address of the board PC if you know it, or search for boards on this network, which opens the address form when it finds no board. Every way with Autodarts ends with the same local board, one device with all its entities" lang="en" width="480">
</picture>

<img src="images/en/setup-menu.png" alt="Le menu de configuration de HomeDarts : rechercher des cibles sur ce réseau, saisir l'adresse d'une cible, ou une cible sans Autodarts" width="520">

### 1. Détection automatique (Board Manager 2)

Board Manager 2 s'annonce sur le réseau (mDNS, `_autodarts-board._tcp`). Home Assistant affiche alors **Cible Autodarts détectée** sous **Paramètres → Appareils et services → Découvertes**. Sélectionnez **Ajouter** et confirmez. La fenêtre indique l'adresse, la version du Board Manager et le nombre de caméras.

Si la cible reçoit plus tard une nouvelle adresse IP, l'annonce met à jour automatiquement l'adresse configurée.

### 2. Rechercher des cibles sur ce réseau

Choisissez **Rechercher des cibles sur ce réseau**. L'intégration demande au service de découverte public d'Autodarts, que l'application Board Manager utilise aussi, quelles cibles sont enregistrées depuis votre connexion internet. Choisissez votre cible, et l'intégration s'y connecte en local. L'entrée et l'appareil prennent le nom que la cible porte chez Autodarts.

> Le service de découverte voit votre adresse IP publique, comme n'importe quel site web. Rien d'autre n'est envoyé. Si le service n'est pas disponible ou ne trouve aucune nouvelle cible, le formulaire d'adresse s'ouvre à la place.

### 3. Saisir l'adresse de la cible

Choisissez **Saisir l'adresse de la cible** et saisissez l'adresse IP ou le nom d'hôte du PC de la cible, par exemple `192.0.2.10` ou `autodarts.local`, sans `http://` et sans port. Le port est normalement **3180**.

<img src="images/en/setup-local.png" alt="Le formulaire pour saisir l'adresse et le port du Board Manager" width="520">

L'intégration lit l'identifiant de la cible dans le Board Manager. Elle refuse les adresses injoignables ou sans cible configurée.

> **Astuce :** donnez au PC de la cible une adresse IP fixe dans votre routeur. Avec Board Manager 2, la détection garde de toute façon l'adresse à jour.

### 4. Une cible sans Autodarts

Choisissez **Cible sans Autodarts : saisir soi-même chaque fléchette** et donnez un nom à la cible, comme *Garage*. Vous saisissez ses fléchettes sur le pavé numérique de la carte en direct et du tableau des scores, et les jeux, l'entraînement et les statistiques fonctionnent comme avec Autodarts ; [Play without Autodarts](without-autodarts.md) explique tout. Vous pouvez en avoir plusieurs, à côté de cibles Autodarts, et chacune peut [recevoir plus tard sa cible Autodarts](without-autodarts.md#autodarts-later).

<img src="images/en/setup-manual.png" alt="Le formulaire d'une cible sans Autodarts, avec le nom Dartboard rempli" width="520">

### Après la configuration

Home Assistant crée un appareil, nommé d'après votre cible, avec toutes les [entités](entities.md). Pour un tableau de bord complet, allez dans **Paramètres → Tableaux de bord → Ajouter un tableau de bord → HomeDarts**, comme l'indique la fenêtre à la fin de la configuration : le [tableau de bord automatique](cards.md#automatic-dashboard) construit ses vues à partir de vos cibles. Sur votre propre tableau de bord, **Ajouter une carte** trouve les cartes quand vous recherchez *HomeDarts* ; voir le [guide des cartes](cards.md).

[De zéro au tableau des scores](getting-started.fr.md) continue avec le tableau des scores sur une tablette et votre première partie.
