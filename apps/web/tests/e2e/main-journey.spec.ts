import { test, expect } from "@playwright/test";

test.describe("ClipFarm Parcours Utilisateur Principal", () => {
  test("1. Écran Accueil : affiche la liste des projets", async ({ page }) => {
    // Intercepter uniquement les appels vers l'API backend (port 8000)
    await page.route("http://localhost:8000/projects", async (route) => {
      if (route.request().method() === "GET") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify([
            {
              id: "test12345",
              source_url: "https://www.youtube.com/watch?v=sample",
              status: "ready",
              progress: 1.0,
              step: "done",
              settings_json: { layout: "facecam_top", format: "9:16" },
              created_at: new Date().toISOString(),
              clips_count: 2,
            },
          ]),
        });
      } else {
        await route.continue();
      }
    });

    await page.goto("/");
    await expect(page.getByRole("heading", { name: "Vos Projets" })).toBeVisible();
    await expect(page.getByText("#test12345")).toBeVisible();
    await expect(page.getByText("Prêt")).toBeVisible();
    await expect(page.getByRole("link", { name: "Nouveau projet" }).first()).toBeVisible();
  });

  test("2. Écran Nouveau Projet : formulaire et sélecteur Facecam", async ({ page }) => {
    await page.goto("/projects/new");
    await expect(page.getByRole("heading", { name: "Nouveau Projet" })).toBeVisible();

    // Vérifier les onglets Lien et Fichier
    await expect(page.getByText("Lien web")).toBeVisible();
    await expect(page.getByText("Fichier local")).toBeVisible();

    // Basculer sur Fichier local
    await page.getByText("Fichier local").click();
    await expect(page.getByText("Glissez votre vidéo ici")).toBeVisible();
    await expect(page.getByText("Zone Facecam")).toBeVisible();
    await expect(page.getByText("Haut Droite")).toBeVisible();

    // Revenir sur Lien web
    await page.getByText("Lien web").click();
    await expect(page.getByPlaceholder("https://www.youtube.com/watch?v=...")).toBeVisible();
    await expect(page.getByText(/Cadrage Facecam sur lien/)).toBeVisible();
  });

  test("3. Écran Projet : affichage de la grille des clips et progression", async ({ page }) => {
    await page.route("http://localhost:8000/projects/test12345", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "test12345",
          source_url: "https://www.youtube.com/watch?v=sample",
          status: "ready",
          progress: 1.0,
          step: "done",
          settings_json: { layout: "facecam_top", format: "9:16" },
          created_at: new Date().toISOString(),
          clips: [
            {
              id: "test12345_1",
              project_id: "test12345",
              index: 1,
              start: 10.0,
              end: 25.0,
              title: "Moment Épique",
              hook: "Regardez ça !",
              reason: "Forte intensité vocale",
              final_score: 0.88,
              file_path: "sample.mp4",
              scores: { hook: 9.0, emotion: 8.5 },
            },
          ],
        }),
      });
    });

    await page.route("http://localhost:8000/projects/test12345/events", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "text/event-stream",
        body: "event: ping\ndata: keep-alive\n\n",
      });
    });

    await page.goto("/projects/test12345");
    await expect(page.getByRole("heading", { name: /Clips Détectés & Générés/ })).toBeVisible();
    await expect(page.getByText("Moment Épique")).toBeVisible();
    await expect(page.getByText('🎯 Accroche : "Regardez ça !"')).toBeVisible();
    await expect(page.getByRole("link", { name: "Éditer" })).toBeVisible();
  });

  test("4. Écran Clip : lecteur, trim et éditeur de sous-titres mot à mot", async ({ page }) => {
    await page.route(/8000\/clips\/test12345_1$/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "test12345_1",
          project_id: "test12345",
          index: 1,
          start: 10.0,
          end: 25.0,
          title: "Moment Épique",
          hook: "Regardez ça !",
          final_score: 0.88,
          layout: { name: "facecam_top", fmt: "9:16" },
          captions: { preset: "punchy" },
          file_path: "sample.mp4",
        }),
      });
    });

    await page.route(/8000\/clips\/test12345_1\/words$/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          { text: "C'est", start: 10.2, end: 10.6, prob: 0.95 },
          { text: "incroyable", start: 10.7, end: 11.4, prob: 0.98 },
        ]),
      });
    });

    await page.goto("/clips/test12345_1");
    await expect(page.getByRole("heading", { name: /Édition du Clip #1/ })).toBeVisible();
    await expect(page.getByText("Titre & Coupe (Trim)")).toBeVisible();
    await expect(page.getByRole("button", { name: "Re-rendre le clip" })).toBeVisible();
    await expect(page.getByRole("link", { name: "Télécharger MP4" })).toBeVisible();

    // Vérifier que les mots des sous-titres sont affichés et éditables
    await expect(page.locator("input[value='incroyable']")).toBeVisible();
  });
});
