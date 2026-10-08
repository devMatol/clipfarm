import { test } from "@playwright/test";

test("Générer les captures d'écran pour vérification visuelle", async ({ page }) => {
  // 1. Home
  await page.route("http://localhost:8000/projects", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        {
          id: "e7aa59f18f",
          source_url: "GTA 6 GAMEPLAY REVEAL (Skyrroz)",
          status: "ready",
          progress: 1.0,
          step: "done",
          settings_json: { layout: "facecam_top", format: "9:16" },
          created_at: new Date().toISOString(),
          clips_count: 2,
        },
      ]),
    });
  });

  await page.setViewportSize({ width: 1280, height: 800 });
  await page.goto("/");
  await page.screenshot({ path: "screenshot_01_home.png", fullPage: true });

  // 2. Nouveau projet
  await page.goto("/projects/new");
  await page.screenshot({ path: "screenshot_02_new_project.png", fullPage: true });

  // 3. Projet avec grille des clips
  await page.route("http://localhost:8000/projects/e7aa59f18f", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        id: "e7aa59f18f",
        source_url: "GTA 6 GAMEPLAY REVEAL (Skyrroz)",
        status: "ready",
        progress: 1.0,
        step: "done",
        settings_json: { layout: "facecam_top", format: "9:16" },
        created_at: new Date().toISOString(),
        clips: [
          {
            id: "e7aa59f18f_1",
            project_id: "e7aa59f18f",
            index: 1,
            start: 259.0,
            end: 274.3,
            title: "La manette en jeu !",
            hook: "Manette en jeu !",
            reason: "Un moment de tension et de surprise avec la réaction du joueur.",
            final_score: 0.84,
            scores: { hook: 9.0, emotion: 10.0, payoff: 9.0 },
            file_path: "clips/01.mp4",
          },
          {
            id: "e7aa59f18f_2",
            project_id: "e7aa59f18f",
            index: 2,
            start: 1004.2,
            end: 1022.3,
            title: "Incroyable la ville",
            hook: "Incroyable la ville",
            reason: "Un moment de surprise et d'admiration avec une description visuelle de la ville.",
            final_score: 0.82,
            scores: { hook: 9.0, emotion: 9.0, payoff: 10.0 },
            file_path: "clips/02.mp4",
          },
        ],
      }),
    });
  });

  await page.route("http://localhost:8000/projects/e7aa59f18f/events", async (route) => {
    await route.fulfill({ status: 200, contentType: "text/event-stream", body: "event: ping\ndata: ok\n\n" });
  });

  await page.goto("/projects/e7aa59f18f");
  await page.screenshot({ path: "screenshot_03_project.png", fullPage: true });

  // 4. Éditeur de clip
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
      }),
    });
  });

  await page.route("http://localhost:8000/clips/e7aa59f18f_1/words", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify([
        { word: "PRENDRE", start: 259.2, end: 259.8 },
        { word: "LA", start: 259.9, end: 260.1 },
        { word: "MANETTE", start: 260.2, end: 260.9 },
        { word: "EN", start: 261.0, end: 261.2 },
        { word: "JEU", start: 261.3, end: 261.8 },
      ]),
    });
  });

  await page.goto("/clips/e7aa59f18f_1");
  await page.screenshot({ path: "screenshot_04_clip_editor.png", fullPage: true });

  // 5. Version mobile de l'éditeur
  await page.setViewportSize({ width: 390, height: 844 });
  await page.screenshot({ path: "screenshot_05_mobile.png", fullPage: true });
});
