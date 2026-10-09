import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { createServer } from "node:http";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

// Static template verification: no app.py, live APIs, database or background services.
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const require = createRequire(import.meta.url);
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || "playwright");
const html = execFileSync(process.env.PYTHON || "python", ["-c", `
from jinja2 import Environment, FileSystemLoader
from monolith.devices import devices
from monolith.sensors import sensors
from urllib.parse import urlencode
rooms = list(dict.fromkeys(device['room'] for device in devices.values()))
env = Environment(loader=FileSystemLoader('templates'), autoescape=True)
def url_for(endpoint, filename, **params):
    return '/static/' + filename + ('?' + urlencode(params) if params else '')
print(env.get_template('dashboard.html').render(url_for=url_for, devices=devices, rooms=rooms, sensors=sensors))
`], { cwd: root, encoding: "utf8", env: { ...process.env, PYTHONIOENCODING: "utf-8" } })
  .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, "")
  .replace(/<link\b[^>]*href="https:[^>]*>/gi, "");

const server = createServer((request, response) => {
  const pathname = new URL(request.url, "http://localhost").pathname;
  if (pathname === "/") {
    response.setHeader("Content-Type", "text/html; charset=utf-8");
    response.end(html);
  } else if (pathname.startsWith("/api/")) {
    response.setHeader("Content-Type", "application/json");
    response.end("{}");
  } else if (pathname.startsWith("/static/")) {
    const filename = path.resolve(root, `.${decodeURIComponent(pathname)}`);
    if (!filename.startsWith(path.join(root, "static") + path.sep)) {
      response.writeHead(403).end();
      return;
    }
    try {
      response.setHeader("Content-Type", filename.endsWith(".css") ? "text/css" : filename.endsWith(".woff2") ? "font/woff2" : "application/octet-stream");
      response.end(readFileSync(filename));
    } catch { response.writeHead(404).end(); }
  } else { response.writeHead(404).end(); }
});
await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
let browser;
try {
  browser = await chromium.launch({ channel: process.env.BROWSER_CHANNEL || "msedge", headless: true });
  const page = await browser.newPage({ reducedMotion: "reduce" });
  const fontRequests = [];
  page.on("request", request => { if (request.url().includes(".woff2")) fontRequests.push(request.url()); });
  await page.goto(`http://127.0.0.1:${server.address().port}/`);
  await page.evaluate(async () => {
    for (const weight of [200, 400, 600, 800]) {
      const faces = await document.fonts.load(`${weight} 14px Manrope`, "Übersicht Größe Łódź 0123456789 €");
      if (faces.length !== 2 || faces.some(face => face.status !== "loaded")) throw new Error("Manrope subsets did not load");
    }
    // Isolate the dashboard's Chart.js font configuration from external scripts.
    window.Chart = { defaults: { font: {} }, instances: {} };
  });
  await page.addScriptTag({ content: readFileSync(path.join(root, "static/app.js"), "utf8") });
  await page.evaluate(() => setupDashboardTabs());
  assert.equal(await page.evaluate(() => Chart.defaults.font.family), await page.evaluate(() => getComputedStyle(document.body).fontFamily));

  const tabs = await page.locator("[data-dashboard-tab]").evaluateAll(elements => elements.map(el => el.dataset.dashboardTab));
  assert.equal(tabs.length, 15);
  for (const width of [1440, 390]) {
    await page.setViewportSize({ width, height: 1000 });
    for (const key of tabs) {
      await page.evaluate(key => activateDashboardTab(key, false), key);
      assert.equal(await page.locator(".main-layout").getAttribute("data-active-dashboard-tab"), key);
      const result = await page.evaluate(key => {
        const panels = [...document.querySelectorAll(`[data-dashboard-panel="${key}"]`)];
        const elements = [...document.querySelectorAll("body, header *, input, textarea, select, button"),
          ...panels.flatMap(panel => [panel, ...panel.querySelectorAll("*")])];
        const mismatches = elements.filter(el => !el.matches("i, script, style, canvas, svg, svg *")
          && getComputedStyle(el).fontFamily.split(",")[0].replaceAll('"', "") !== "Manrope"
        ).map(el => ({ tag: el.tagName, class: el.className, font: getComputedStyle(el).fontFamily }));
        const tiny = elements.filter(el => !el.matches("i, script, style, canvas, svg, svg *")
          && [...el.childNodes].some(node => node.nodeType === Node.TEXT_NODE && node.textContent.trim())
          && parseFloat(getComputedStyle(el).fontSize) < 11
        ).map(el => ({ class: el.className, size: getComputedStyle(el).fontSize }));
        return { panels: panels.length, visible: panels.every(panel => !panel.hidden), mismatches, tiny };
      }, key);
      assert.ok(result.panels > 0 && result.visible, `${key}: panel must be active`);
      assert.deepEqual(result.mismatches, [], `${key} at ${width}px has incorrect fonts`);
      if (key !== "overview") assert.deepEqual(result.tiny, [], `${key} at ${width}px has text smaller than the overview captions`);
    }
  }
  assert.equal(new Set(fontRequests).size, 2, "Both local font subsets must load");
  assert.ok(fontRequests.every(url => new URL(url).origin === new URL(page.url()).origin));
  const css = readFileSync(path.join(root, "static/style.css"), "utf8");
  assert.ok(!/SFMono-Regular|Consolas|Liberation Mono|\bInter\b/.test(css), "No previous text font stacks may remain");
  const worker = readFileSync(path.join(root, "static/service-worker.js"), "utf8");
  for (const subset of ["Latin", "LatinExt"]) assert.ok(worker.includes(`/static/fonts/manrope/Manrope-${subset}-Variable.woff2`));
  console.log("PASS: Manrope loaded locally at weights 200/400/600/800; all text, numbers, clock and controls in 15 tabs verified at 1440px and 390px; matching Chart.js defaults and offline font assets verified.");
} finally {
  if (browser) await browser.close();
  await new Promise(resolve => server.close(resolve));
}
