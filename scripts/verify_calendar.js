const { chromium } = require('@playwright/test');
const path = require('path');

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();

  console.log("Navigation vers http://localhost:3000/calendar...");
  await page.goto("http://localhost:3000/calendar", { waitUntil: "networkidle" });
  await page.waitForTimeout(2000);

  // 1. Screenshot de la vue principale du calendrier
  const calendarScreenshotPath = path.resolve(__dirname, "../../.gemini/antigravity/brain/0eb7efe6-6388-43a9-9033-392283dc7921/screenshot_calendar_view.png");
  await page.screenshot({ path: calendarScreenshotPath, fullPage: true });
  console.log("Screenshot calendrier sauvé :", calendarScreenshotPath);

  // 2. Cliquer sur le bouton "Planification IA Prédictive"
  const aiButton = page.locator('button:has-text("Planification IA Prédictive")').first();
  await aiButton.click();
  await page.waitForTimeout(1000);

  // Screenshot du modal de configuration
  const modalSetupScreenshot = path.resolve(__dirname, "../../.gemini/antigravity/brain/0eb7efe6-6388-43a9-9033-392283dc7921/screenshot_calendar_ai_setup.png");
  await page.screenshot({ path: modalSetupScreenshot });
  console.log("Screenshot modal setup sauvé :", modalSetupScreenshot);

  // 3. Cliquer sur "Calculer la planification optimale"
  console.log("Lancement de la prédiction Gemini...");
  const calcButton = page.locator('button:has-text("Calculer la planification optimale")');
  await calcButton.click();

  // Attendre la fin du calcul (max 30s)
  await page.waitForSelector('text=Score IA', { timeout: 30000 });
  await page.waitForTimeout(1500);

  // Screenshot des résultats de prédiction IA
  const modalResultScreenshot = path.resolve(__dirname, "../../.gemini/antigravity/brain/0eb7efe6-6388-43a9-9033-392283dc7921/screenshot_calendar_ai_predicted.png");
  await page.screenshot({ path: modalResultScreenshot });
  console.log("Screenshot prédictions Gemini sauvé :", modalResultScreenshot);

  // 4. Cocher la case des droits et valider la programmation
  console.log("Validation de la programmation...");
  const rightsCheckbox = page.locator('input[type="checkbox"]').last();
  await rightsCheckbox.check();

  const validateButton = page.locator('button:has-text("Valider et Programmer")');
  await validateButton.click();

  await page.waitForTimeout(3000);

  // 5. Screenshot final du calendrier mis à jour avec les clips programmés
  const finalCalendarScreenshot = path.resolve(__dirname, "../../.gemini/antigravity/brain/0eb7efe6-6388-43a9-9033-392283dc7921/screenshot_calendar_scheduled_final.png");
  await page.screenshot({ path: finalCalendarScreenshot, fullPage: true });
  console.log("Screenshot calendrier final sauvé :", finalCalendarScreenshot);

  await browser.close();
  console.log("Test calendrier terminé avec succès !");
})();
