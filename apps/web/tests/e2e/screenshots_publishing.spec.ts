import { test } from "@playwright/test";

test("Captures d'écran module de publication (Phase 6a)", async ({ page }) => {
  // Mock des comptes
  await page.route("http://localhost:8000/accounts", async (route) => {
    if (route.request().method() === "GET") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify([
          {
            id: "yt_acc_1",
            platform: "youtube",
            platform_account_id: "UC_ClipFarmDemo",
            name: "ClipFarm Studio (YouTube)",
            avatar_url: null,
            status: "connected",
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          },
        ]),
      });
    } else {
      await route.continue();
    }
  });

  // 1. Page Comptes
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.goto("/accounts");
  await page.waitForTimeout(1000);
  await page.screenshot({ path: "screenshot_accounts.png", fullPage: true });

  // Mock du clip
  await page.route("http://localhost:8000/clips/e7aa59f18f_1", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "e7aa59f18f_1",
        project_id: "e7aa59f18f",
        index: 1,
        start: 259.0,
        end: 274.3,
        title: "La manette en jeu !",
        hook: "Manette en jeu !",
        reason: "Un moment de tension",
        final_score: 0.84,
        layout: { name: "facecam_top", fmt: "9:16" },
        captions: { preset: "punchy" },
        file_path: "clips/01.mp4",
        status: "ready",
      }),
    });
  });

  await page.route("http://localhost:8000/clips/e7aa59f18f_1/words", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { text: "PRENDRE", start: 259.2, end: 259.8 },
        { text: "LA", start: 259.9, end: 260.1 },
        { text: "MANETTE", start: 260.2, end: 260.9 },
        { text: "EN", start: 261.0, end: 261.2 },
        { text: "JEU", start: 261.3, end: 261.8 },
      ]),
    });
  });

  // 2. Page Clip avec Modal de publication
  await page.goto("/clips/e7aa59f18f_1");
  await page.waitForTimeout(1000);

  // Cliquer sur le bouton "Publier"
  await page.click("text=Publier");
  await page.waitForTimeout(500);

  // Capture du modal de publication ouvert
  await page.screenshot({ path: "screenshot_publish_modal.png" });

  // Cocher la certification des droits
  await page.check("input#rights_confirm");
  await page.waitForTimeout(300);

  // Cliquer sur Vérifier & Récapituler
  await page.click("text=Vérifier & Récapituler");
  await page.waitForTimeout(500);

  // Capture de l'étape de confirmation obligatoire
  await page.screenshot({ path: "screenshot_publish_confirm.png" });

  // Mock de la liste des publications
  await page.route("http://localhost:8000/publications", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: "pub_demo_1",
          clip_id: "e7aa59f18f_1",
          account_id: "yt_acc_1",
          platform: "youtube",
          metadata_json: { title: "La manette en jeu ! #Shorts" },
          scheduled_at: null,
          status: "published",
          external_id: "dQw4w9WgXcQ",
          url: "https://youtube.com/shorts/dQw4w9WgXcQ",
          error: null,
          attempts: 1,
          rights_confirmed: true,
          published_at: new Date().toISOString(),
          created_at: new Date().toISOString(),
        },
      ]),
    });
  });

  // 3. Page Publications
  await page.goto("/publications");
  await page.waitForTimeout(1000);
  await page.screenshot({ path: "screenshot_publications.png", fullPage: true });
});
