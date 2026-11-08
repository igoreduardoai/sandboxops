import { createRequire } from "node:module";
import { writeFileSync } from "node:fs";

const require = createRequire("/tmp/sandboxops-ui-tools/package.json");
const { chromium } = require("playwright-core");
const axe = require("axe-core");

const base = process.argv[2];
const outDir = process.argv[3];
if (!base || !outDir) {
  console.error("usage: ui_probe.mjs BASE_URL OUT_DIR");
  process.exit(2);
}

const result = { ok: false, errors: [] };
const browser = await chromium.launch({
  executablePath: "/usr/bin/google-chrome",
  headless: true,
  args: ["--no-sandbox", "--disable-dev-shm-usage"],
});
try {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const consoleErrors = [];
  page.on("pageerror", (err) => consoleErrors.push(String(err)));
  page.on("console", (msg) => {
    if (msg.type() === "error") consoleErrors.push(msg.text());
  });
  await page.goto(base + "/", { waitUntil: "networkidle" });
  await page.waitForSelector("#tasks button");
  await page.screenshot({ path: `${outDir}/ui-home.png`, fullPage: true });

  await page.evaluate(axe.source);
  const axeResult = await page.evaluate(async () => {
    const r = await axe.run(document);
    return {
      violations: r.violations.map((v) => ({
        id: v.id,
        impact: v.impact,
        help: v.help,
        nodes: v.nodes.slice(0, 5).map((n) => ({ target: n.target, html: (n.html || "").slice(0, 180) })),
      })),
      violationCount: r.violations.length,
      passes: r.passes.length,
      incomplete: r.incomplete.length,
    };
  });

  await page.locator("body").click({ position: { x: 2, y: 2 } });
  const tabOrder = [];
  for (let i = 0; i < 6; i++) {
    await page.keyboard.press("Tab");
    tabOrder.push(
      await page.evaluate(() => {
        const e = document.activeElement;
        return {
          tag: e?.tagName || "",
          id: e?.id || "",
          text: (e?.innerText || e?.getAttribute?.("placeholder") || "").slice(0, 60),
        };
      }),
    );
  }

  const networkBtn = page.locator("#tasks button", { hasText: "network_attempt" });
  await networkBtn.focus();
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => (document.querySelector("#banner")?.textContent || "").includes("CONTAINED"), null, {
    timeout: 15000,
  });
  const containedText = await page.locator("#banner").innerText();
  await page.screenshot({ path: `${outDir}/ui-contained-keyboard.png`, fullPage: true });

  await page.locator("#p").focus();
  await page.keyboard.press("Control+A");
  await page.keyboard.type("offline adversarial prompt should not execute");
  await page.locator("button", { hasText: "Plan & run" }).focus();
  await page.keyboard.press("Enter");
  await page.waitForFunction(() => (document.querySelector("#banner")?.textContent || "").includes("LLM planner offline"), null, {
    timeout: 10000,
  });
  const offlineText = await page.locator("#banner").innerText();
  await page.screenshot({ path: `${outDir}/ui-planner-offline-keyboard.png`, fullPage: true });

  result.ok = true;
  result.axe = axeResult;
  result.tabOrder = tabOrder;
  result.containedText = containedText;
  result.offlineText = offlineText;
  result.consoleErrors = consoleErrors;
  result.title = await page.title();
} catch (err) {
  result.errors.push(String(err && err.stack ? err.stack : err));
} finally {
  await browser.close();
}
writeFileSync(`${outDir}/ui-probe.json`, JSON.stringify(result, null, 2));
process.exit(result.ok ? 0 : 1);
