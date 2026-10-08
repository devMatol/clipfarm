# Module de Publication ClipFarm : Documentation & Spécifications Officielles

Ce document synthétise les spécifications techniques officielles des plateformes cibles (YouTube Shorts, TikTok, Instagram Reels, et Postiz), ainsi que l'architecture et les procédures de test manuel sécurisé.

---

## 1. Spécifications officielles des plateformes

### 1.1 YouTube Data API v3 (Shorts)
*Documentation officielle :* [YouTube Data API - Videos: insert](https://developers.google.com/youtube/v3/docs/videos/insert) | [Using OAuth 2.0 for Installed Applications](https://developers.google.com/identity/protocols/oauth2/native-app)

* **Scopes OAuth 2.0 requis** :
  * `https://www.googleapis.com/auth/youtube.upload` (permet l'envoi de vidéos)
  * `https://www.googleapis.com/auth/youtube.readonly` (récupération des informations de la chaîne et de l'avatar)
* **Quotas & Limites** :
  * Quota global par défaut : 10 000 unités / jour par projet Google Cloud.
  * Un appel `videos.insert` consomme **1 600 unités** (soit environ 6 uploads complets par jour avec le quota de base).
  * Les projets créés récemment disposent également d'un seau d'environ 100 uploads/jour maximum.
* **Critères YouTube Shorts** :
  * **Ratio d'aspect** : Vertical (9:16) ou carré (1:1).
  * **Durée** : Maximum 60 secondes (les vidéos jusqu'à 3 minutes au ratio 9:16 sont désormais éligibles selon les dernières spécifications YouTube).
  * **Hashtag** : `#Shorts` vivement recommandé dans le titre ou la description pour faciliter l'indexation dans le flux Shorts.
* **Champs obligatoires** :
  * `snippet.title` : Obligatoire, max **100 caractères**.
  * `snippet.description` : Max **5 000 caractères**.
  * `snippet.tags` : Max **500 caractères** combinés.
  * `snippet.categoryId` : Obligatoire (par défaut `22` pour Divertissement ou `20` pour Jeux vidéo).
  * `status.privacyStatus` : `private`, `unlisted` ou `public`.
  * `status.selfDeclaredMadeForKids` : Booléen **obligatoire** (`false` par défaut pour nos clips).
  * `status.publishAt` : Date ISO 8601 UTC. Permet la **planification native YouTube** même si le PC est éteint (impose `privacyStatus: private`).
* **Restrictions des apps non auditées** :
  * Tant que l'application Google Cloud n'a pas validé la vérification OAuth par Google, les vidéos envoyées via l'API sont automatiquement verrouillées en **Privé** (`private`) ou limitées aux comptes de test autorisés dans la console Google Cloud.

---

### 1.2 TikTok Content Posting API (Direct Post)
*Documentation officielle :* [TikTok Content Posting API](https://developers.tiktok.com/doc/content-posting-api-get-started) | [Direct Post Reference](https://developers.tiktok.com/doc/content-posting-api-reference-direct-post)

* **Scopes OAuth 2.0 requis** :
  * `video.upload`
  * `video.publish`
  * `user.info.basic` (lecture avatar et nom du créateur)
* **Quotas & Limites** :
  * Limite créateur : environ 15 publications par fenêtre de 24h par compte créateur (partagée entre toutes les applications).
  * Débit API : 6 requêtes / minute pour l'initiation d'upload, 30 requêtes / minute pour l'interrogation du statut.
* **Critères Vidéo** :
  * **Ratio d'aspect** : 9:16 (recommandé), 1:1, 16:9.
  * **Format** : MP4 (H.264), AAC, 30/60 fps, min 540p, max 4 Go.
  * **Durée** : Minimum 3 secondes, max 10 minutes.
  * **Envoi** : Protocole `FILE_UPLOAD` par morceaux (chunks de min 5 Mo à 64 Mo).
* **Restrictions des apps non auditées** :
  * Max 5 comptes créateurs autorisés par 24h.
  * Visibilité **strictement verrouillée sur `SELF_ONLY` (Privé)** jusqu'au passage de l'audit formel.
* **Exigences d'audit strictes pour l'UI** :
  * Interrogation obligatoire de l'endpoint `creator_info` avant publication.
  * Affichage clair du nom et avatar du compte créateur publiant la vidéo.
  * Aucun niveau de confidentialité pré-sélectionné par défaut (choix actif requis de l'utilisateur).
  * Toggles commentaires, duo, stitch désactivés par défaut.
  * Mention commerciale et divulgation de contenu généré par IA (case à cocher).

---

### 1.3 Instagram Graph API (Reels)
*Documentation officielle :* [Instagram Reels Publishing API](https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/content-publishing)

* **Scopes OAuth 2.0 requis** :
  * `instagram_basic`
  * `instagram_content_publish`
  * `pages_show_list`
* **Quotas & Limites** :
  * Quota strict de **25 publications par 24 heures** par compte Instagram (partagé avec les Stories et posts classiques).
  * Vérifiable via l'endpoint `/{ig-user-id}/content_publishing_limit`.
* **Modèle à Conteneur (2 étapes)** :
  1. Création d'un conteneur média (`POST /{ig-user-id}/media?media_type=REELS&video_url=...`). Le fichier vidéo doit être accessible sur une URL HTTPS publique valide.
  2. Scrutation du statut (`GET /{container-id}?fields=status_code`) toutes les minutes jusqu'à `FINISHED`.
  3. Publication du conteneur (`POST /{ig-user-id}/media_publish?creation_id=...`).
* **Critères Vidéo** :
  * Format MP4 ou MOV, H.264 + AAC, 9:16, max 90 secondes pour les Reels, max 1 Go.

---

### 1.4 Adaptateur optionnel Postiz
*Documentation officielle :* [Postiz Docs](https://docs.postiz.com/)
* Postiz est une application auto-hébergée (licence AGPL-3.0).
* **Aucun code Postiz n'est importé dans ClipFarm**. ClipFarm communique avec Postiz uniquement via des requêtes HTTP REST standards sur son API publique (`/api/v1/posts`).
* L'adaptateur reste désactivé tant que `POSTIZ_API_URL` et `POSTIZ_API_KEY` ne sont pas renseignés dans `.env`.

---

## 2. Sécurité et Gestion des Jetons

1. **Chiffrement symétrique Fernet (AES-128-CBC + HMAC-SHA256)** :
   * Tous les jetons d'accès et de rafraîchissement (`access_token`, `refresh_token`) sont chiffrés avant écriture dans la table PostgreSQL `accounts`.
   * La clé de chiffrement est issue de la variable d'environnement `CLIPFARM_SECRET_KEY` dans `.env`. Si absente au premier lancement, une clé valide est générée automatiquement.
2. **Étanchéité des logs et de l'API** :
   * Aucun jeton brut ni déchiffré n'apparaît dans les réponses HTTP de l'API, dans les logs serveur ou dans l'interface web.
   * Le DTO public `AccountOut` n'expose que le nom, l'avatar, le statut de connexion et la date d'expiration.
3. **Révocation** :
   * La suppression d'un compte via l'interface supprime immédiatement l'enregistrement et purge les jetons chiffrés de la base de données.

---

## 3. Guide de Test Réel Manuel (`scripts/test-publish.ps1`)

Un script PowerShell dédié permet de valider manuellement l'envoi d'une vidéo réelle sur YouTube en toute sécurité (mode privé ou non répertorié), sans jamais risquer de publication publique involontaire :

```powershell
# Exécuter depuis la racine de clipfarm
.\scripts\test-publish.ps1 -Platform youtube -ClipId "<PROJECT_ID>_1" -Privacy unlisted
```

Le script vérifie la présence du compte connecté, contrôle le fichier vidéo avec `ffprobe`, nettoie les métadonnées techniques, et soumet la publication en mode `unlisted` avec validation explicite de l'utilisateur.
