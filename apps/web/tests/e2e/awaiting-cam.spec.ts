import { test, expect } from "@playwright/test";

test.describe("Parcours awaiting_cam et Facecam absente", () => {
  test("Page projet awaiting_cam : affichage sélecteur et validation", async ({ page }) => {
    // 1. Navigation vers le projet en attente de cadrage facecam
    await page.goto("http://localhost:3000/projects/demo_awaiting");

    // Attendre que le sélecteur Facecam soit visible (en laissant le temps à useQuery)
    const titleLocator = page.locator("text=Vidéo importée : Ajustez le cadrage Facecam");
    await expect(titleLocator).toBeVisible({ timeout: 15000 });

    const validateButton = page.getByRole("button", { name: "Valider et continuer" });
    await expect(validateButton).toBeVisible();

    // Capture d'écran demandée : la page projet en statut awaiting_cam
    await page.screenshot({ path: "screenshot_awaiting_cam.png", fullPage: true });

    // 2. Clic sur le bouton de validation
    await expect(validateButton).toBeEnabled();
    await validateButton.click();

    // Attendre la prise en compte
    await page.waitForTimeout(1500);
  });

  test("Affichage du clip avec facecam absente (rendu centré automatiquement)", async ({ page }) => {
    // Intercepter uniquement l'appel API sur le port 8000
    await page.route(/8000\/projects\/demo_fallback_test$/, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          id: "demo_fallback_test",
          source_path: "data/projects/demo_fallback_test/source.mp4",
          status: "ready",
          progress: 1.0,
          step: "done",
          clips: [
            {
              id: "demo_fallback_test_1",
              project_id: "demo_fallback_test",
              index: 1,
              start: 10.0,
              end: 45.0,
              title: "Moment d'action sans caméra",
              hook: "Regardez ce gameplay époustouflant",
              reason: "Score d'action élevé",
              final_score: 0.92,
              scores: { action: 0.95 },
              layout: {
                name: "center",
                fmt: "9:16",
                face_fallback: true,
              },
              captions: { preset: "punchy" },
              file_path: "data/projects/demo_fallback_test/clips/01.mp4",
              status: "ready",
            },
          ],
        }),
      });
    });

    // Navigation vers le projet mocké
    await page.goto("/projects/demo_fallback_test");

    // Attendre le chargement des clips
    const centerBadge = page.locator("text=Cadré au centre").first();
    await expect(centerBadge).toBeVisible({ timeout: 15000 });

    const fallbackNotice = page.locator("text=Visage absent : rendu centré automatiquement").first();
    await expect(fallbackNotice).toBeVisible();

    // Capture d'écran demandée : clip où la facecam a été remplacée par le centrage
    await page.screenshot({ path: "screenshot_face_fallback.png", fullPage: true });
  });
});
