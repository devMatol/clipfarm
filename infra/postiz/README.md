# Intégration Postiz pour ClipFarm

Postiz est une application libre d'ordonnancement de réseaux sociaux (TikTok, Instagram, YouTube, X, LinkedIn).
Elle tourne en tant que service autonome (AGPL-3.0) et ClipFarm communique avec elle uniquement via son API REST standard.

## Démarrage rapide

1. Lancez la pile Docker :
```bash
docker compose -f infra/postiz/docker-compose.yml up -d
```

2. Ouvrez l'interface Postiz :
👉 [http://localhost:4200](http://localhost:4200)

3. Créez un compte administrateur local dans Postiz, puis allez dans **Settings > API Key** pour copier votre clé API.

4. Connectez votre compte TikTok (ou Instagram, etc.) dans Postiz sous **Integrations**.

5. Ajoutez vos identifiants dans le `.env` de ClipFarm :
```env
POSTIZ_API_URL=http://localhost:4200
POSTIZ_API_KEY=votre_cle_api_postiz
```

6. Rendez-vous sur la page **Comptes & Réseaux Sociaux** de ClipFarm : cliquez sur **Synchroniser Postiz**. Vos chaînes TikTok apparaîtront automatiquement prêtes pour la publication et la planification !
