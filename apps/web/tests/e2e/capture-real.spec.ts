import { test, expect } from "@playwright/test";

test.describe("Screenshots avec données réelles", () => {
  test("Capturer les 4 écrans réels de ClipFarm", async ({ page }) => {
    // 1. Liste des projets (avec le projet réel 8c8cf38238)
    await page.goto("http://localhost:3000/");
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: "screenshot_01_projets.png", fullPage: true });

    // 2. Écran Nouveau projet
    await page.goto("http://localhost:3000/projects/new");
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: "screenshot_02_nouveau_projet.png", fullPage: true });

    // 3. Page du projet réel (8c8cf38238) avec le clip généré
    await page.goto("http://localhost:3000/projects/8c8cf38238");
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: "screenshot_03_projet_detail.png", fullPage: true });

    // 4. Page du clip réel (8c8cf38238_1) avec éditeur mot à mot
    await page.goto("http://localhost:3000/clips/8c8cf38238_1");
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: "screenshot_04_clip_detail.png", fullPage: true });
  });
});
