import { writeFileSync } from "node:fs";

const base = process.argv[2];
const outDir = process.argv[3];
if (!base || !outDir) {
  console.error("usage: lighthouse_probe.mjs BASE_URL OUT_DIR");
  process.exit(2);
}

const lighthouse = (await import("/tmp/sandboxops-ui-tools/node_modules/lighthouse/core/index.js")).default;
const chromeLauncher = await import("/tmp/sandboxops-ui-tools/node_modules/chrome-launcher/dist/index.js");

const chrome = await chromeLauncher.launch({
  chromePath: "/usr/bin/google-chrome",
  chromeFlags: ["--headless=new", "--no-sandbox", "--disable-dev-shm-usage"],
});
try {
  const runner = await lighthouse(
    base + "/",
    {
      port: chrome.port,
      output: "json",
      logLevel: "error",
      onlyCategories: ["accessibility", "best-practices", "seo"],
    },
  );
  const lhr = runner.lhr;
  const slim = {
    lighthouseVersion: lhr.lighthouseVersion,
    requestedUrl: lhr.requestedUrl,
    finalUrl: lhr.finalUrl,
    categories: Object.fromEntries(
      Object.entries(lhr.categories).map(([k, v]) => [k, { score: v.score, title: v.title }]),
    ),
    failingAudits: Object.values(lhr.audits)
      .filter((a) => a.score !== null && a.score < 1 && (a.scoreDisplayMode === "binary" || a.scoreDisplayMode === "numeric"))
      .map((a) => ({ id: a.id, title: a.title, score: a.score, displayValue: a.displayValue || null }))
      .slice(0, 40),
  };
  writeFileSync(`${outDir}/lighthouse-summary.json`, JSON.stringify(slim, null, 2));
  writeFileSync(`${outDir}/lighthouse.report.json`, runner.report);
  console.log(JSON.stringify(slim.categories));
} finally {
  await chrome.kill();
}
