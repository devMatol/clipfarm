---
trigger: glob
globs: apps/web/**
description: Regles du front Next.js
---

# Front (Next.js)

- App Router, TypeScript strict, Tailwind, composants shadcn/ui, donnees via TanStack Query.
- Interface en francais, theme sombre par defaut, utilisable sur mobile (le proprietaire valide souvent depuis son telephone).
- Aucune logique metier dans le front : tout passe par l'API (`NEXT_PUBLIC_API_URL`).
- Progression des jobs en SSE (`/projects/{id}/events`), avec reprise apres rechargement de la page.
- Videos lues avec la balise `<video>` native, miniatures servies par l'API.
- Tests Playwright pour chaque parcours, API simulee. Verifier chaque ecran dans le navigateur d'Antigravity avant de rendre la main.
